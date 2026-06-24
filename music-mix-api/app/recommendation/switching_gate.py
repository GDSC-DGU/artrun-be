from __future__ import annotations


def should_request_new_segment(
    current_segment_played_sec: float,
    seconds_since_last_switch: float,
    previous_target_energy: float,
    current_target_energy: float,
    *,
    min_played_sec: float = 30.0,
    min_switch_interval_sec: float = 45.0,
    min_energy_delta: float = 0.15,
) -> bool:
    if current_segment_played_sec < min_played_sec:
        return False

    if seconds_since_last_switch < min_switch_interval_sec:
        return False

    if abs(current_target_energy - previous_target_energy) < min_energy_delta:
        return False

    return True
