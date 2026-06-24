from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FrameFeatures:
    frame_times: list[float]
    rms: list[float]
    centroid: list[float]
    bandwidth: list[float]
    flatness: list[float]
    onset_env: list[float]


def extract_frame_features(audio_path: str | Path, hop_length: int = 512) -> FrameFeatures:
    """Extract librosa frame features.

    Kept isolated so production can swap implementation or add caching.
    """
    try:
        import numpy as np
        import librosa
    except Exception as exc:  # pragma: no cover - dependency setup handled by Codex
        raise RuntimeError("librosa and numpy are required for audio feature extraction") from exc

    y, sr = librosa.load(str(audio_path), sr=44100, mono=True)
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=2048, hop_length=hop_length)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=2048, hop_length=hop_length)[0]
    flatness = librosa.feature.spectral_flatness(y=y, n_fft=2048, hop_length=hop_length)[0]
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    frame_times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=hop_length)
    return FrameFeatures(
        frame_times=frame_times.tolist(),
        rms=rms.tolist(),
        centroid=centroid.tolist(),
        bandwidth=bandwidth.tolist(),
        flatness=flatness.tolist(),
        onset_env=onset_env[: len(rms)].tolist(),
    )
