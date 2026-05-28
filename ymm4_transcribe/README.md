# ymm4_transcribe

音声ファイルから YMM4 の「台本読み込み」機能で読めるCSVを自動生成するツール。
**完全ローカル動作**（OpenAI API不要・課金なし・オフライン可）。

## 仕組み

1. ffmpeg で 16kHz モノラル WAV に変換
2. **faster-whisper (Whisper large-v3)** でセグメント単位の文字起こし (日本語、ローカル実行)
3. Resemblyzer + scikit-learn で各セグメントの声紋を埋め込み、Agglomerative Clustering で話者IDを推定
4. 各クラスタにキャラクター名(A/B/C/...)を割り当てる対話プロンプト
5. UTF-8 BOM CSV を書き出し → YMM4 で「台本読み込み」

## セットアップ

```powershell
cd "E:\文字起こしシステム"
.venv\Scripts\Activate.ps1
pip install -r ymm4_transcribe\requirements.txt

# ffmpeg をインストール (PATHを通す) ※既に入っていれば不要
winget install Gyan.FFmpeg
# winget 直後は新しいターミナルを開かないと PATH に反映されません
ffmpeg -version  # 動作確認
```

> **メモ**: webrtcvad は Windows でビルドエラーになるので、`requirements.txt` に追加する前に
> `pip install webrtcvad-wheels` を先に実行する必要があります。
> その後 `pip install --no-deps resemblyzer` で resemblyzer 単体を入れ、最後に他依存を入れます。

## 使い方

```powershell
# 基本: input.mp3 → input.csv
python -m ymm4_transcribe input.mp3

# 出力先指定
python -m ymm4_transcribe input.mp3 -o "output\台本.csv"

# 話者数を固定 (3人と分かっているとき)
python -m ymm4_transcribe input.mp3 --num-speakers 3

# マッピングをCLIで渡す (非対話モード)
python -m ymm4_transcribe input.mp3 --mapping 0=A,1=B,2=C

# クラスタリング閾値の調整 (話者を1つに統合しすぎる/しすぎないとき)
python -m ymm4_transcribe input.mp3 --distance-threshold 0.50

# 中間結果のデバッグJSONを保存
python -m ymm4_transcribe input.mp3 --debug-json input.debug.json
```

## 初回実行時の注意

初回のみ、Whisper large-v3 モデル (約 3GB) を HuggingFace から自動ダウンロードします。
- 保存先: `C:\Users\<ユーザ名>\.cache\huggingface\hub\models--Systran--faster-whisper-large-v3`
- 2回目以降はキャッシュから読み込むだけなので、ロード時間は数秒
- C ドライブが手狭なら、環境変数 `HF_HOME` を `E:\hf_cache` 等に変更すれば E に保存可能

## 処理時間の目安 (CPU・int8量子化)

| 音声長 | 推論時間目安 |
|---|---|
| 1分 | 約 60〜90秒 |
| 5分 | 約 5〜8分 |
| 10分 | 約 10〜15分 |
| 30分 | 約 30〜45分 |

GPU (NVIDIA CUDA) が使えれば 5〜10倍速になります。`transcribe.py` の `DEFAULT_DEVICE = "cuda"` に変更してください。

## YMM4側の準備

CSVのA列に書かれるキャラクター名（`A`/`B`/`C` 等）が、YMM4の登録キャラクター名と
**完全一致**している必要があります。事前にYMM4で対応するキャラクターを登録するか、
`--mapping 0=ゆっくり霊夢,1=ゆっくり魔理沙` のように既存のキャラクター名を指定してください。

## チューニング

- 話者の分離が甘い (別人を同じクラスタに統合) → `--distance-threshold` を下げる (例: 0.45)
- 同じ話者が複数クラスタに分かれる → `--distance-threshold` を上げる (例: 0.65)、または `--num-speakers` で固定
- 短い相槌が変な話者に割り当たる → 後で手動修正するか、`--debug-json` で確認

## 既知の限界

- Resemblyzer は重複発話に弱い。同時発話が多い音声では精度が落ちる
- ゆっくり/合成音声は声質がResemblyzer的に近く、分離精度が出にくい
- Whisper large-v3 は無音や音楽部分でも文字を生成することがある (hallucination)。VADフィルタで抑制するが完全には防げない
- 0.6秒未満の超短セグメントは声紋抽出をスキップし、隣接セグメントの話者を継承する

## ファイル

| ファイル | 役割 |
|---|---|
| `audio_prep.py` | ffmpeg呼出、形式変換 |
| `transcribe.py` | faster-whisper (large-v3) ローカル文字起こし |
| `diarize.py` | Resemblyzer + クラスタリング |
| `merge.py` | 文字起こしと話者IDの結合、ポストフィルタ |
| `csv_export.py` | UTF-8 BOM CSV書き出し |
| `cli.py` | CLI、対話マッピング |
| `__main__.py` | `python -m ymm4_transcribe` のエントリ |
