#Requires -Version 5.1
<#
.SYNOPSIS
  ymm4_transcribe を新しい Windows PC で動かすための自動セットアップスクリプト。

.DESCRIPTION
  - Python 3.12 / ffmpeg を winget で導入（既に入っていればスキップ）
  - .venv を作り直して依存パッケージを正しい順序で導入
    （webrtcvad のソースビルドエラーを回避するため、resemblyzer は --no-deps で入れる）
  - 主要ライブラリの import 動作確認まで実施
  ※ Whisper モデル(約3GB) は初回の文字起こし実行時に HuggingFace から自動DLされる。

.EXAMPLE
  PowerShell -ExecutionPolicy Bypass -File .\setup.ps1
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"

function Write-Step([string]$msg) {
  Write-Host ""
  Write-Host "==== $msg ====" -ForegroundColor Cyan
}

function Refresh-Path {
  $env:Path =
    [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
    [System.Environment]::GetEnvironmentVariable("Path", "User")
}

function Test-Command([string]$name) {
  return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

# ---- 開始 ----
$projectRoot = Split-Path -Parent $PSCommandPath
Set-Location $projectRoot
Write-Host "プロジェクトルート: $projectRoot" -ForegroundColor Green

# 入力ソースの sanity check
if (-not (Test-Path (Join-Path $projectRoot "ymm4_transcribe\__main__.py"))) {
  Write-Error "ymm4_transcribe フォルダが見つかりません。リポジトリのルートで実行してください。"
  exit 1
}

# ---- 0. 前提: winget ----
Write-Step "0. winget の確認"
if (-not (Test-Command winget)) {
  Write-Error "winget が見つかりません。Windows 10/11 の『App Installer』を最新にしてください。"
  exit 1
}
Write-Host "winget OK"

# ---- 1. Python 3.12 ----
Write-Step "1. Python 3.12 の確認 / 導入"
Refresh-Path
$pythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe"
if (Test-Path $pythonExe) {
  Write-Host "Python 3.12 既存"
}
else {
  Write-Host "Python 3.12 を winget で導入します（数分かかります）..."
  winget install --id Python.Python.3.12 `
    --accept-source-agreements --accept-package-agreements --silent
  Refresh-Path
  if (-not (Test-Path $pythonExe)) {
    Write-Error "Python 3.12 の導入後に $pythonExe が見つかりません。手動で確認してください。"
    exit 1
  }
}
& $pythonExe --version

# ---- 2. ffmpeg ----
Write-Step "2. ffmpeg の確認 / 導入"
Refresh-Path
if (Test-Command ffmpeg) {
  (ffmpeg -version)[0]
}
else {
  Write-Host "ffmpeg を winget で導入します（数分かかります）..."
  winget install --id Gyan.FFmpeg `
    --accept-source-agreements --accept-package-agreements --silent
  Refresh-Path
  if (Test-Command ffmpeg) {
    (ffmpeg -version)[0]
  }
  else {
    Write-Warning "ffmpeg の PATH 反映が遅れている可能性があります。PowerShell を開き直して再実行してください。"
  }
}

# ---- 3. .venv 再構築 ----
Write-Step "3. 仮想環境 .venv の作成"
$venvDir = Join-Path $projectRoot ".venv"
if (Test-Path $venvDir) {
  Write-Host "既存の .venv を削除します"
  Remove-Item -Recurse -Force $venvDir
}
& $pythonExe -m venv $venvDir
$venvPy = Join-Path $venvDir "Scripts\python.exe"
if (-not (Test-Path $venvPy)) {
  Write-Error ".venv の作成に失敗しました"
  exit 1
}
& $venvPy --version

# ---- 4-8. 依存パッケージ ----
Write-Step "4. pip アップグレード"
& $venvPy -m pip install --upgrade pip

Write-Step "5. webrtcvad-wheels (Windows用ビルド済みホイール)"
& $venvPy -m pip install webrtcvad-wheels

Write-Step "6. resemblyzer (--no-deps で依存解決をスキップ)"
& $venvPy -m pip install --no-deps resemblyzer

Write-Step "7. 処理系パッケージ (faster-whisper, scikit-learn, numpy, librosa, scipy)"
& $venvPy -m pip install faster-whisper scikit-learn numpy librosa scipy

Write-Step "8. torch (CPU版)"
& $venvPy -m pip install torch --index-url https://download.pytorch.org/whl/cpu

# ---- 9. import 動作確認 ----
Write-Step "9. import 動作確認"
$env:PYTHONIOENCODING = "utf-8"
$importCheck = @'
import faster_whisper, resemblyzer, sklearn, numpy, librosa, scipy, webrtcvad, torch
print("全ライブラリ import OK")
print("  numpy", numpy.__version__)
print("  torch", torch.__version__)
'@
& $venvPy -c $importCheck

# ---- 10. CLI ヘルプで起動確認 ----
Write-Step "10. CLI 起動確認"
& $venvPy -m ymm4_transcribe --help | Select-Object -First 4

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host " セットアップ完了！" -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "使い方:" -ForegroundColor Yellow
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host '  python -m ymm4_transcribe "音声ファイル.wav" --srt'
Write-Host ""
Write-Host "※ Whisper モデル (約3GB) は初回の文字起こし実行時に自動DLされます。" -ForegroundColor DarkYellow
