from __future__ import annotations

from dataclasses import dataclass, field
from app.domain.models import Segment, TransitionMethod


@dataclass(frozen=True)
class MixAction:
    offset_sec: float
    track: str
    action: str
    params: dict


@dataclass(frozen=True)
class MixPlan:
    method: TransitionMethod
    current_exit_sec: float
    next_entry_sec: float
    duration_bars: int = 0
    duration_sec: float = 0.0
    current_track_id: str | None = None
    next_track_id: str | None = None
    timeline: list[MixAction] = field(default_factory=list)


def build_direct_fade_plan(current_position_sec: float, next_segment: Segment, fade_sec: float = 2.0) -> MixPlan:
    return MixPlan(
        method=TransitionMethod.DIRECT_FADE,
        current_exit_sec=current_position_sec,
        next_entry_sec=next_segment.start_sec,
        duration_bars=0,
        duration_sec=fade_sec,
        next_track_id=next_segment.track_id,
        timeline=[
            MixAction(0.0, "current", "volume_fade", {"from": 1.0, "to": 0.0, "duration_sec": fade_sec}),
            MixAction(0.0, "next", "volume_fade", {"from": 0.0, "to": 1.0, "duration_sec": fade_sec}),
        ],
    )


def crossfade_duration_for_bpm(bpm: float, duration_bars: int = 8) -> float:
    if bpm <= 0:
        return 16.0
    return duration_bars * 4.0 * 60.0 / bpm


def build_phrase_crossfade_plan(
    current_position_sec: float,
    next_segment: Segment,
    duration_sec: float | None = None,
    duration_bars: int = 8,
) -> MixPlan:
    duration = duration_sec if duration_sec is not None else crossfade_duration_for_bpm(next_segment.bpm, duration_bars)
    return MixPlan(
        method=TransitionMethod.PHRASE_ALIGNED_CROSSFADE,
        current_exit_sec=current_position_sec,
        next_entry_sec=next_segment.start_sec,
        duration_bars=duration_bars,
        duration_sec=duration,
        next_track_id=next_segment.track_id,
        timeline=[
            MixAction(0.0, "current", "equal_power_fade_out", {"from": 1.0, "to": 0.0, "duration_sec": duration, "curve": "equal_power"}),
            MixAction(0.0, "next", "equal_power_fade_in", {"from": 0.0, "to": 1.0, "duration_sec": duration, "curve": "equal_power"}),
        ],
    )


def auto_mix_plan(current_position_sec: float, next_segment: Segment, bpm_diff: float | None = None) -> MixPlan:
    if bpm_diff is not None and bpm_diff <= 8.0 and next_segment.phrase_confidence >= 0.65:
        return build_phrase_crossfade_plan(current_position_sec, next_segment)
    return build_direct_fade_plan(current_position_sec, next_segment)


def build_transition_mix_plan(current_segment: Segment, next_segment: Segment, current_position_sec: float | None = None) -> MixPlan:
    exit_sec = current_position_sec if current_position_sec is not None else max(current_segment.start_sec, current_segment.end_sec - 2.0)
    plan = auto_mix_plan(exit_sec, next_segment, bpm_diff=abs(current_segment.bpm - next_segment.bpm))
    return MixPlan(
        method=plan.method,
        current_exit_sec=plan.current_exit_sec,
        next_entry_sec=plan.next_entry_sec,
        duration_bars=plan.duration_bars,
        duration_sec=plan.duration_sec,
        current_track_id=current_segment.track_id,
        next_track_id=next_segment.track_id,
        timeline=plan.timeline,
    )
