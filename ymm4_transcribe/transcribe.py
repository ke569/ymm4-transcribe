"""faster-whisper (large-v3) で日本語音声を文字起こし、セグメント単位のタイムスタンプを得る。

ローカルで完結するため OpenAI API は不要 (キー・課金なし)。
初回実行時に約3GBのモデルをダウンロードする。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from faster_whisper import WhisperModel


DEFAULT_MODEL = "large-v3"
DEFAULT_DEVICE = "cpu"
DEFAULT_COMPUTE_TYPE = "int8"


@dataclass
class TranscriptSegment:
    start: float  # 秒（元音声基準）
    end: float
    text: str


_model_cache: dict[str, WhisperModel] = {}


def _get_model(
    model_name: str = DEFAULT_MODEL,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
) -> WhisperModel:
    key = f"{model_name}|{device}|{compute_type}"
    if key not in _model_cache:
        _model_cache[key] = WhisperModel(
            model_name, device=device, compute_type=compute_type
        )
    return _model_cache[key]


def transcribe_audio(
    wav_path: Path,
    language: str = "ja",
    model_name: str = DEFAULT_MODEL,
    device: str = DEFAULT_DEVICE,
    compute_type: str = DEFAULT_COMPUTE_TYPE,
) -> list[TranscriptSegment]:
    model = _get_model(model_name, device, compute_type)
    segments_iter, _info = model.transcribe(
        str(wav_path),
        language=language,
        beam_size=5,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=500),
    )
    result: list[TranscriptSegment] = []
    for s in segments_iter:
        text = (s.text or "").strip()
        if not text:
            continue
        # 認識したセグメントを1行ずつ表示(進捗が画面で分かるように)
        try:
            print(f"      {s.start:6.1f}s  {text}", flush=True)
        except Exception:
            pass
        result.append(
            TranscriptSegment(start=float(s.start), end=float(s.end), text=text)
        )
    return result
