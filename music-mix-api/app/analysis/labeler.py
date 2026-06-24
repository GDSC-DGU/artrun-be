from __future__ import annotations

from dataclasses import dataclass
from app.domain.models import SectionType


@dataclass(frozen=True)
class SectionStats:
    mean_energy: float
    start_energy: float
    end_energy: float
    mean_onset_density: float
    position_ratio: float
    model_label: str | None = None


def relabel_for_running(stats: SectionStats) -> SectionType:
    """Map model/energy statistics to mobile running section labels."""
    e_mean = stats.mean_energy
    trend = stats.end_energy - stats.start_energy
    onset = stats.mean_onset_density
    pos = stats.position_ratio

    if pos < 0.15 and e_mean < 0.45:
        return SectionType.INTRO

    if pos > 0.82 and e_mean < 0.45:
        return SectionType.OUTRO

    if trend > 0.15 and stats.end_energy >= 0.60:
        return SectionType.BUILD_UP

    if e_mean >= 0.75 and onset >= 0.65:
        return SectionType.DROP

    if e_mean < 0.45 and onset < 0.45 and pos > 0.20:
        return SectionType.BREAKDOWN

    # Soft mapping from structure model labels, used only if rules did not trigger.
    label = (stats.model_label or "").lower()
    if label == "intro":
        return SectionType.INTRO
    if label in {"chorus", "refrain"} and e_mean >= 0.60:
        return SectionType.DROP
    if label in {"verse", "pre-chorus", "prechorus"}:
        return SectionType.GROOVE
    if label == "outro":
        return SectionType.OUTRO

    return SectionType.GROOVE
