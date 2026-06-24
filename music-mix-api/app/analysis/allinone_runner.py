from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from app.domain.models import RawSection


@dataclass(frozen=True)
class StructureResult:
    tempo: float
    beats: list[float]
    downbeats: list[float]
    sections: list[RawSection]
    confidence: float = 0.5


def run_all_in_one(audio_path: str | Path) -> StructureResult:
    """Placeholder for All-In-One Music Structure Analyzer integration.

    Codex should replace this stub with the real model/CLI wrapper.
    Required normalized output:
      - tempo
      - beats
      - downbeats
      - RawSection(start_sec, end_sec, model_label, confidence)
    """
    raise NotImplementedError(
        "All-In-One wrapper is not connected yet. Implement this function by calling the model/CLI."
    )
