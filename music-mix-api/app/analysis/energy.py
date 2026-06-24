from __future__ import annotations

from dataclasses import dataclass


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def energy_level(score: float) -> int:
    score = clamp(score)
    if score < 0.20:
        return 1
    if score < 0.40:
        return 2
    if score < 0.60:
        return 3
    if score < 0.80:
        return 4
    return 5


@dataclass(frozen=True)
class EnergyFeatures:
    volume_score: float = 0.0
    onset_density_score: float = 0.0
    brightness_score: float = 0.0
    sound_density_score: float = 0.0
    bpm_score: float = 0.0
    dynamic_change_score: float = 0.0
    drum_density_score: float | None = None
    bass_strength_score: float | None = None


def compute_energy_score_v01(features: EnergyFeatures) -> float:
    """Energy score without stem separation."""
    score = (
        0.25 * features.volume_score
        + 0.25 * features.onset_density_score
        + 0.15 * features.brightness_score
        + 0.15 * features.sound_density_score
        + 0.10 * features.bpm_score
        + 0.10 * features.dynamic_change_score
    )
    return clamp(score)


def compute_energy_score_v02(features: EnergyFeatures) -> float:
    """Energy score with optional Demucs drum/bass stem features."""
    drum = features.drum_density_score
    bass = features.bass_strength_score

    if drum is None or bass is None:
        return compute_energy_score_v01(features)

    score = (
        0.20 * features.volume_score
        + 0.20 * drum
        + 0.18 * bass
        + 0.15 * features.onset_density_score
        + 0.12 * features.sound_density_score
        + 0.08 * features.brightness_score
        + 0.07 * features.dynamic_change_score
    )
    return clamp(score)


def compute_energy_score(features: EnergyFeatures, profile: str = "basic") -> tuple[float, int]:
    if profile == "precise":
        score = compute_energy_score_v02(features)
    else:
        score = compute_energy_score_v01(features)
    return score, energy_level(score)
