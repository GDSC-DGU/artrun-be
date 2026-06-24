from __future__ import annotations

from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
EDM_AUDIO_DIR = DATA_DIR / "audio" / "edm_samples"
MANIFESTS_DIR = DATA_DIR / "manifests"
SEGMENTS_DIR = DATA_DIR / "segments"
LEGACY_OUTPUTS_DIR = ROOT_DIR / "outputs"
LEGACY_AUDIO_DIR = ROOT_DIR.parent / "edm_sample"


def preferred_segments_dir() -> Path:
    if SEGMENTS_DIR.exists() and any(SEGMENTS_DIR.glob("*_segments.json")):
        return SEGMENTS_DIR
    return LEGACY_OUTPUTS_DIR


def preferred_audio_dir() -> Path:
    if EDM_AUDIO_DIR.exists() and any(EDM_AUDIO_DIR.glob("*.mp3")):
        return EDM_AUDIO_DIR
    return LEGACY_AUDIO_DIR
