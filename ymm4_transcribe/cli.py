"""CLIエントリポイント。

使い方:
    python -m ymm4_transcribe input.mp3
    python -m ymm4_transcribe input.mp3 -o output.csv --num-speakers 3
    python -m ymm4_transcribe input.mp3 --mapping 0=A,1=B,2=C
"""
from __future__ import annotations

import argparse
import json
import string
import sys
from dataclasses import asdict
from pathlib import Path

from . import audio_prep, diarize, merge, transcribe
from .csv_export import ScriptLine, write_ymm4_csv


def _parse_mapping(arg: str) -> dict[int, str]:
    mapping: dict[int, str] = {}
    for pair in arg.split(","):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            raise ValueError(f"--mapping の書式が不正: '{pair}' (例: 0=A,1=B,2=C)")
        k, v = pair.split("=", 1)
        mapping[int(k.strip())] = v.strip()
    return mapping


def _interactive_mapping(labeled: list[merge.LabeledSegment]) -> dict[int, str]:
    counts = merge.cluster_counts(labeled)
    samples = merge.cluster_summary(labeled)
    speaker_ids = sorted(counts.keys())

    print()
    print("=" * 60)
    print("話者の自動分離が完了しました。各クラスタにキャラクター名を割り当ててください。")
    print("空欄でEnterするとそのクラスタはスキップ（出力しない）します。")
    print("=" * 60)

    default_names = list(string.ascii_uppercase)  # A, B, C, ...
    mapping: dict[int, str] = {}
    for idx, sid in enumerate(speaker_ids):
        examples = samples.get(sid, [])
        print()
        print(f"speaker_{sid}  ({counts[sid]}発言)")
        for ex in examples:
            preview = ex if len(ex) <= 40 else ex[:40] + "…"
            print(f"  例: 「{preview}」")
        suggestion = default_names[idx] if idx < len(default_names) else ""
        prompt = f"  → キャラクター名 [Enterで '{suggestion}']: " if suggestion else "  → キャラクター名: "
        try:
            user_input = input(prompt).strip()
        except EOFError:
            user_input = ""
        chosen = user_input or suggestion
        if chosen:
            mapping[sid] = chosen
    return mapping


def _build_lines(
    labeled: list[merge.LabeledSegment], mapping: dict[int, str]
) -> list[ScriptLine]:
    lines: list[ScriptLine] = []
    for seg in labeled:
        name = mapping.get(seg.speaker_id)
        if not name:
            continue
        lines.append(ScriptLine(speaker=name, text=seg.text))
    return lines


def _write_debug_json(
    path: Path, labeled: list[merge.LabeledSegment], mapping: dict[int, str]
) -> None:
    payload = {
        "mapping": {str(k): v for k, v in mapping.items()},
        "segments": [asdict(s) for s in labeled],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m ymm4_transcribe",
        description="音声ファイルを文字起こし＋話者分離してYMM4台本CSVを生成する",
    )
    parser.add_argument("input", help="入力音声ファイル (mp3/wav/m4a等)")
    parser.add_argument(
        "-o", "--output", help="出力CSVパス (省略時は入力と同じ場所に .csv で保存)"
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="話者数を固定 (未指定なら自動推定)",
    )
    parser.add_argument(
        "--distance-threshold",
        type=float,
        default=0.55,
        help="自動推定時のクラスタリング閾値 (cosine距離、既定0.55)",
    )
    parser.add_argument(
        "--mapping",
        default=None,
        help="クラスタ→キャラクター名の対応 (例: 0=A,1=B,2=C)。指定すると非対話モード",
    )
    parser.add_argument(
        "--language",
        default="ja",
        help="Whisperに渡す言語コード (既定: ja)",
    )
    parser.add_argument(
        "--debug-json",
        default=None,
        help="中間結果をJSONで保存 (デバッグ用)",
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"入力ファイルが見つかりません: {input_path}", file=sys.stderr)
        return 1

    output_path = (
        Path(args.output) if args.output else input_path.with_suffix(".csv")
    )

    print(f"[1/5] 音声を準備中: {input_path}")
    prepared = audio_prep.prepare(input_path)
    print(f"      長さ: {prepared.duration_seconds:.1f}秒")

    try:
        print("[2/5] Whisper large-v3 (faster-whisper, ローカル) で文字起こし中...")
        print("      初回はモデル(約3GB)のダウンロードがあります")
        segments = transcribe.transcribe_audio(prepared.full_wav, language=args.language)
        print(f"      {len(segments)} セグメントを検出")

        if not segments:
            print("文字起こし結果が空です。音声を確認してください。", file=sys.stderr)
            return 2

        print("[3/5] 話者分離 (Resemblyzer + clustering) 中...")
        speaker_ids = diarize.diarize(
            prepared.full_wav,
            segments,
            num_speakers=args.num_speakers,
            distance_threshold=args.distance_threshold,
        )
        labeled = merge.combine(segments, speaker_ids)
        cluster_count = len(set(s.speaker_id for s in labeled))
        print(f"      {cluster_count} クラスタを検出 (有効セグメント: {len(labeled)})")

        print("[4/5] 話者→キャラクター名の割り当て")
        if args.mapping:
            mapping = _parse_mapping(args.mapping)
        else:
            mapping = _interactive_mapping(labeled)

        if not mapping:
            print("マッピングが空のため出力をスキップしました。", file=sys.stderr)
            return 3

        lines = _build_lines(labeled, mapping)
        if not lines:
            print("出力対象のセリフがありません。", file=sys.stderr)
            return 3

        print(f"[5/5] CSVを書き出し中: {output_path}")
        write_ymm4_csv(lines, output_path)
        print(f"      {len(lines)} 行を書き出しました")

        if args.debug_json:
            _write_debug_json(Path(args.debug_json), labeled, mapping)
            print(f"      デバッグJSON: {args.debug_json}")

        print("完了。YMM4の台本読み込み機能から読み込んでください。")
        return 0
    finally:
        audio_prep.cleanup(prepared)


if __name__ == "__main__":
    raise SystemExit(main())
