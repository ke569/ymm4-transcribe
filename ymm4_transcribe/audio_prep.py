"""音声ファイルの前処理。ffmpegで16kHzモノラルWAV化し、必要ならチャンク分割する。

Whisper APIの上限は25MBなので、安全側でそれ未満になるようチャンク分割する。
16kHz/16bit/mono WAVは約 32KB/秒 なので、25MB ≒ 13分。
余裕を持って 1チャンク=10分 をデフォルトにする。
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import mkdtemp

WHISPER_MAX_BYTES = 25 * 1024 * 1024  # OpenAI Whisper API limit
DEFAULT_CHUNK_SECONDS = 600  # 10分


@dataclass
class AudioChunk:
    """1つのチャンクファイルとその元音声における開始秒。"""

    path: Path
    offset_seconds: float


def _check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError(
            "ffmpegが見つかりません。`winget install Gyan.FFmpeg` 等でインストールし、"
            "PATHを通してください。"
        )


def _probe_duration(path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return float(result.stdout.strip())


def to_mono_wav(input_path: str | Path, work_dir: Path) -> Path:
    input_path = Path(input_path)
    output_path = work_dir / f"{input_path.stem}.16k.wav"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(input_path),
            "-ac",
            "1",
            "-ar",
            "16000",
            "-vn",
            str(output_path),
        ],
        check=True,
    )
    return output_path


def split_if_needed(
    wav_path: Path, work_dir: Path, chunk_seconds: int = DEFAULT_CHUNK_SECONDS
) -> list[AudioChunk]:
    size = wav_path.stat().st_size
    if size <= WHISPER_MAX_BYTES:
        return [AudioChunk(path=wav_path, offset_seconds=0.0)]

    chunks_dir = work_dir / "chunks"
    chunks_dir.mkdir(exist_ok=True)
    pattern = chunks_dir / "chunk_%04d.wav"

    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(wav_path),
            "-f",
            "segment",
            "-segment_time",
            str(chunk_seconds),
            "-c",
            "copy",
            str(pattern),
        ],
        check=True,
    )

    chunks: list[AudioChunk] = []
    for chunk_path in sorted(chunks_dir.glob("chunk_*.wav")):
        index = int(chunk_path.stem.split("_")[1])
        offset = float(index * chunk_seconds)
        chunks.append(AudioChunk(path=chunk_path, offset_seconds=offset))
    return chunks


@dataclass
class PreparedAudio:
    full_wav: Path  # 全体WAV (diarize用)
    chunks: list[AudioChunk]  # transcribe用 (チャンク分割済)
    duration_seconds: float
    work_dir: Path  # 後始末用


def prepare(input_path: str | Path) -> PreparedAudio:
    _check_ffmpeg()
    work_dir = Path(mkdtemp(prefix="ymm4_transcribe_"))
    full_wav = to_mono_wav(input_path, work_dir)
    duration = _probe_duration(full_wav)
    chunks = split_if_needed(full_wav, work_dir)
    return PreparedAudio(
        full_wav=full_wav, chunks=chunks, duration_seconds=duration, work_dir=work_dir
    )


def cleanup(prepared: PreparedAudio) -> None:
    if prepared.work_dir.exists():
        shutil.rmtree(prepared.work_dir, ignore_errors=True)
