"""文字起こしセグメントと話者ラベルを結合し、ポストフィルタを掛ける。"""
from __future__ import annotations

from dataclasses import dataclass

from .transcribe import TranscriptSegment


@dataclass
class LabeledSegment:
    start: float
    end: float
    text: str
    speaker_id: int


def combine(
    segments: list[TranscriptSegment], speaker_ids: list[int]
) -> list[LabeledSegment]:
    if len(segments) != len(speaker_ids):
        raise ValueError(
            f"segments ({len(segments)}) と speaker_ids ({len(speaker_ids)}) の数が一致しません"
        )

    result: list[LabeledSegment] = []
    prev_text: str | None = None
    for seg, sid in zip(segments, speaker_ids):
        text = seg.text.strip()
        if not text:
            continue
        # Whisperのhallucination対策: 直前と全く同じテキストは除去
        if text == prev_text:
            continue
        result.append(
            LabeledSegment(start=seg.start, end=seg.end, text=text, speaker_id=sid)
        )
        prev_text = text
    return result


def cluster_summary(labeled: list[LabeledSegment]) -> dict[int, list[str]]:
    """話者IDごとの代表セリフ（先頭3件）を返す。"""
    summary: dict[int, list[str]] = {}
    for seg in labeled:
        bucket = summary.setdefault(seg.speaker_id, [])
        if len(bucket) < 3:
            bucket.append(seg.text)
    return summary


def cluster_counts(labeled: list[LabeledSegment]) -> dict[int, int]:
    counts: dict[int, int] = {}
    for seg in labeled:
        counts[seg.speaker_id] = counts.get(seg.speaker_id, 0) + 1
    return counts
