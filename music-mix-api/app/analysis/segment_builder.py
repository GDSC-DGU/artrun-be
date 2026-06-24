from __future__ import annotations

from typing import Iterable
from app.domain.models import RawSection, RhythmResult


def snap_to_nearest_downbeat(time_sec: float, downbeat_times: list[float], max_distance: float = 1.2) -> tuple[float, float]:
    """Return snapped time and confidence-ish value.

    Confidence is 1.0 at perfect match and decreases to 0.0 at max_distance.
    """
    if not downbeat_times:
        return time_sec, 0.0
    nearest = min(downbeat_times, key=lambda t: abs(t - time_sec))
    dist = abs(nearest - time_sec)
    if dist <= max_distance:
        return nearest, max(0.0, 1.0 - dist / max_distance)
    return time_sec, 0.25


def find_bar_index(time_sec: float, bar_times: list[float]) -> int:
    if not bar_times:
        return 1
    idx = 0
    for i, t in enumerate(bar_times):
        if t <= time_sec:
            idx = i
        else:
            break
    return idx + 1


def split_long_section_by_bars(start_bar: int, end_bar: int, max_bars: int = 32, split_bars: int = 16) -> list[tuple[int, int]]:
    """Split long sections into recommendation-friendly bar ranges."""
    if end_bar < start_bar:
        return []
    total = end_bar - start_bar + 1
    if total <= max_bars:
        return [(start_bar, end_bar)]
    ranges: list[tuple[int, int]] = []
    b = start_bar
    while b <= end_bar:
        e = min(end_bar, b + split_bars - 1)
        ranges.append((b, e))
        b = e + 1
    return ranges


def time_for_bar(bar_index: int, bar_times: list[float], default: float = 0.0) -> float:
    zero_idx = max(0, bar_index - 1)
    if zero_idx < len(bar_times):
        return bar_times[zero_idx]
    return default


def normalized_boundaries_from_sections(sections: Iterable[RawSection], rhythm: RhythmResult) -> list[RawSection]:
    out: list[RawSection] = []
    for sec in sections:
        start, _ = snap_to_nearest_downbeat(sec.start_sec, rhythm.downbeats)
        end, _ = snap_to_nearest_downbeat(sec.end_sec, rhythm.downbeats)
        if end <= start:
            end = sec.end_sec
        out.append(RawSection(start_sec=start, end_sec=end, model_label=sec.model_label, confidence=sec.confidence))
    return out
