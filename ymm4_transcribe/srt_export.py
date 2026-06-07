"""YMM4 字幕ファイル(.srt) 書き出し。

YMM4 v4.25.0.0+ で「ファイル → インポート → 字幕ファイルをインポート」、または
タイムラインへの D&D により、開始/終了時刻そのままに配置できる。

書式ルール:
- 内容行を ">> キャラクター名: セリフ" とするとボイスアイテムとして追加される。
  キャラクター名が YMM4 側のキャラに登録済みなら、声・立ち絵・字幕デザインが自動適用される。
- それ以外の書式はテキストアイテム（字幕のみ）として配置される。
- タイムスタンプ書式: HH:MM:SS,mmm --> HH:MM:SS,mmm
- 文字コードは UTF-8 (BOMなし)
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .merge import LabeledSegment


def _format_timestamp(seconds: float) -> str:
    """秒を SRT のタイムスタンプ HH:MM:SS,mmm に整形する。"""
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000))
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def write_ymm4_srt(
    labeled: Iterable[LabeledSegment],
    mapping: dict[int, str],
    output_path: str | Path,
) -> int:
    """LabeledSegment + speaker_id→キャラ名 マッピング を SRT に書き出す。

    mapping に含まれない speaker_id のセグメントはスキップする。
    返り値は実際に書き出したエントリ数。
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    count = 0
    with output_path.open("w", encoding="utf-8", newline="\n") as f:
        for seg in labeled:
            name = mapping.get(seg.speaker_id)
            if not name:
                continue
            text = seg.text.strip()
            if not text:
                continue
            count += 1
            start = _format_timestamp(seg.start)
            end = _format_timestamp(seg.end)
            f.write(f"{count}\n")
            f.write(f"{start} --> {end}\n")
            f.write(f">> {name}: {text}\n")
            f.write("\n")
    return count
