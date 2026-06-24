from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import subprocess


@dataclass(frozen=True)
class PreparedAudioFiles:
    original: Path
    mono_wav: Path
    stereo_wav: Path


def prepare_audio(input_path: str | Path, work_dir: str | Path = "outputs/audio") -> PreparedAudioFiles:
    """Convert input audio to analysis wav files using system ffmpeg.

    This is intentionally small and predictable. Codex should add error handling,
    storage integration, and temp cleanup when connecting production infrastructure.
    """
    src = Path(input_path)
    if not src.exists():
        raise FileNotFoundError(f"Audio file not found: {src}")

    out_dir = Path(work_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = src.stem
    mono = out_dir / f"{stem}.mono.44100.wav"
    stereo = out_dir / f"{stem}.stereo.44100.wav"

    if shutil.which("ffmpeg") is None:
        return PreparedAudioFiles(original=src, mono_wav=src, stereo_wav=src)

    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "1", str(mono)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(src), "-ar", "44100", "-ac", "2", str(stereo)], check=True)

    return PreparedAudioFiles(original=src, mono_wav=mono, stereo_wav=stereo)
