from __future__ import annotations

from app.domain.models import RhythmResult
from app.analysis.allinone_runner import StructureResult


def build_phrase_grid(bar_times: list[float]) -> tuple[list[float], list[float]]:
    return bar_times[::8], bar_times[::16]


def validate_structure_rhythm(structure: StructureResult) -> RhythmResult:
    """MVP rhythm validator for All-In-One output.

    Codex should enhance this with BeatNet/librosa fallback.
    """
    bpm = structure.tempo
    confidence = structure.confidence
    if not (60.0 <= bpm <= 200.0):
        confidence *= 0.4

    downbeats = sorted(structure.downbeats)
    bar_times = downbeats[:]
    phrase_8, phrase_16 = build_phrase_grid(bar_times)

    if len(bar_times) < 4:
        confidence *= 0.5

    return RhythmResult(
        bpm=bpm,
        beats=sorted(structure.beats),
        downbeats=downbeats,
        bar_times=bar_times,
        phrase_8bar_times=phrase_8,
        phrase_16bar_times=phrase_16,
        confidence=max(0.0, min(1.0, confidence)),
    )
