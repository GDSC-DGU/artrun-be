from __future__ import annotations

from app.analysis.energy import energy_level
from app.domain.models import RunningMode, TargetEnergyDecision


def pace_to_speed_mps(pace_sec_per_km: float) -> float:
    if pace_sec_per_km <= 0:
        raise ValueError("pace_sec_per_km must be positive")
    return 1000.0 / pace_sec_per_km


def compute_speed_gap_ratio(current_pace_sec_per_km: float, target_pace_sec_per_km: float) -> float:
    current_speed = pace_to_speed_mps(current_pace_sec_per_km)
    target_speed = pace_to_speed_mps(target_pace_sec_per_km)
    return (target_speed - current_speed) / target_speed


def base_energy_for_mode(running_mode: RunningMode | str) -> float:
    mode = running_mode.value if isinstance(running_mode, RunningMode) else str(running_mode)
    return {
        RunningMode.WARM_UP.value: 0.35,
        RunningMode.STEADY_RUN.value: 0.55,
        RunningMode.PACE_UP.value: 0.68,
        RunningMode.SPRINT.value: 0.82,
        RunningMode.INTERVAL_HIGH.value: 0.82,
        RunningMode.COOL_DOWN.value: 0.30,
    }.get(mode, 0.55)


def reason_for_gap(gap: float) -> str:
    if gap > 0.06:
        return "runner_is_slower_than_target"
    if gap < -0.06:
        return "runner_is_faster_than_target"
    return "runner_is_near_target"


def compute_target_energy(
    current_pace_sec_per_km: float,
    target_pace_sec_per_km: float,
    running_mode: RunningMode | str,
    fatigue_level: float | None = None,
    gap_weight: float = 1.25,
) -> TargetEnergyDecision:
    current_speed = pace_to_speed_mps(current_pace_sec_per_km)
    target_speed = pace_to_speed_mps(target_pace_sec_per_km)
    gap = (target_speed - current_speed) / target_speed

    base_energy = base_energy_for_mode(running_mode)
    adjustment = gap * gap_weight

    if fatigue_level is not None:
        fatigue = max(0.0, min(1.0, fatigue_level))
        adjustment *= 1.0 - 0.35 * fatigue

    target_energy = max(0.15, min(0.95, base_energy + adjustment))

    return TargetEnergyDecision(
        current_speed_mps=current_speed,
        target_speed_mps=target_speed,
        speed_gap_ratio=gap,
        target_energy_score=target_energy,
        target_energy_level=energy_level(target_energy),
        main_reason=reason_for_gap(gap),
    )
