"""Resemblyzerで各セグメントの声紋埋め込みを得て、クラスタリングで話者IDを割り当てる。

Resemblyzerは内部で 16kHz/mono にリサンプリングするため、入力WAVは事前に
16kHzに揃えておく前提（audio_prep.to_mono_wav が処理済）。
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from resemblyzer import VoiceEncoder, preprocess_wav
from sklearn.cluster import AgglomerativeClustering

from .transcribe import TranscriptSegment

RESEMBLYZER_SR = 16000
MIN_EMBED_SECONDS = 0.6  # これ未満のセグメントは埋め込みを諦め、隣から継承


def _embed_segments(
    wav: np.ndarray, segments: list[TranscriptSegment]
) -> tuple[list[int], np.ndarray]:
    """各セグメントの埋め込みを計算し、(埋め込みあり indices, 埋め込み行列) を返す。"""
    encoder = VoiceEncoder(verbose=False)
    valid_idx: list[int] = []
    embeddings: list[np.ndarray] = []
    total = len(wav)

    for i, seg in enumerate(segments):
        start_sample = max(0, int(seg.start * RESEMBLYZER_SR))
        end_sample = min(total, int(seg.end * RESEMBLYZER_SR))
        if (end_sample - start_sample) < int(MIN_EMBED_SECONDS * RESEMBLYZER_SR):
            continue
        clip = wav[start_sample:end_sample]
        try:
            emb = encoder.embed_utterance(clip)
        except Exception:
            continue
        valid_idx.append(i)
        embeddings.append(emb)

    if not embeddings:
        return [], np.zeros((0, 256), dtype=np.float32)
    return valid_idx, np.stack(embeddings)


def _cluster(
    matrix: np.ndarray, num_speakers: int | None, distance_threshold: float
) -> np.ndarray:
    if matrix.shape[0] == 0:
        return np.array([], dtype=int)
    if matrix.shape[0] == 1:
        return np.array([0], dtype=int)

    if num_speakers is not None:
        n_clusters = min(num_speakers, matrix.shape[0])
        clusterer = AgglomerativeClustering(
            n_clusters=n_clusters, metric="cosine", linkage="average"
        )
    else:
        clusterer = AgglomerativeClustering(
            n_clusters=None,
            distance_threshold=distance_threshold,
            metric="cosine",
            linkage="average",
        )
    return clusterer.fit_predict(matrix)


def _fill_missing(labels: list[int | None]) -> list[int]:
    """埋め込みが取れなかったセグメントを近傍ラベルで埋める。"""
    n = len(labels)
    result: list[int] = [0] * n

    for i in range(n):
        if labels[i] is not None:
            result[i] = labels[i]  # type: ignore[assignment]
            continue
        # 後方の最も近い有効ラベル
        forward: int | None = None
        for j in range(i + 1, n):
            if labels[j] is not None:
                forward = labels[j]  # type: ignore[assignment]
                break
        # 前方の最も近い有効ラベル
        backward: int | None = None
        for j in range(i - 1, -1, -1):
            if labels[j] is not None:
                backward = labels[j]  # type: ignore[assignment]
                break
        if backward is not None:
            result[i] = backward
        elif forward is not None:
            result[i] = forward
        else:
            result[i] = 0
    return result


def diarize(
    wav_path: Path,
    segments: list[TranscriptSegment],
    num_speakers: int | None = None,
    distance_threshold: float = 0.55,
) -> list[int]:
    """各 TranscriptSegment に対応する話者ID（0始まり整数）のリストを返す。"""
    if not segments:
        return []

    wav = preprocess_wav(wav_path)
    valid_idx, matrix = _embed_segments(wav, segments)
    cluster_labels = _cluster(matrix, num_speakers, distance_threshold)

    sparse: list[int | None] = [None] * len(segments)
    for idx, lbl in zip(valid_idx, cluster_labels):
        sparse[idx] = int(lbl)

    return _fill_missing(sparse)
