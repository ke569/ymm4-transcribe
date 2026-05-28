"""YMM4 台本読み込み機能向けのCSV書き出し。

YMM4の仕様:
- A列: キャラクター名 (YMM4側に登録されているキャラクター名と一致が必要)
- B列: セリフ
- 文字コード: UTF-8 (BOM付)
- 区切り文字: カンマ
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class ScriptLine:
    speaker: str
    text: str


def write_ymm4_csv(lines: Iterable[ScriptLine], output_path: str | Path) -> None:
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with output_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        for line in lines:
            text = line.text.strip()
            if not text:
                continue
            writer.writerow([line.speaker, text])
