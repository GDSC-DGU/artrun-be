from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from app.domain.models import PlaybackContext, RunningContext, RunningMode, SectionType, Segment

EPS = 1e-9


class RunningIntention(str, Enum):
    RECOVERY_OR_CONTROL = "recovery_or_control"
    STEADY = "steady"
    PACE_UP = "pace_up"
    SPRINT_PUSH = "sprint_push"


class EffectivePulseRelation(str, Enum):
    DIRECT = "direct"
    HALF_TIME = "half_time"
    DOUBLE_TIME = "double_time"
    WORKOUT_PULSE = "workout_pulse"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class TargetMusicProfile:
    running_intention: str
    pace_gap_ratio: float
    target_cadence_spm: float | None
    desired_music_pulse_range: tuple[float, float]
    allowed_bpm_ranges: list[tuple[float, float]]
    desired_push_range: tuple[float, float]
    max_bpm_jump: float
    max_push_jump: float
    allowed_transition_steps: list[str]
    debug_reason: str = ""

    def to_debug_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["pace_gap_ratio"] = round(self.pace_gap_ratio, 4)
        return data


@dataclass(frozen=True)
class CurrentMusicState:
    track_id: str | None = None
    segment_id: str | None = None
    bpm: float | None = None
    effective_pulse_value: float | None = None
    pace_push_score: float | None = None
    energy_score: float | None = None
    section_type: str | None = None


@dataclass(frozen=True)
class MusicProfileScoreBreakdown:
    final_score: float
    running_intention: str
    pace_gap_ratio: float
    tempo_match_score: float
    cadence_alignment_score: float
    transition_continuity_score: float
    pace_push_score: float
    groove_score: float
    bass_drive_score: float
    section_role_score: float
    static_low_end_penalty: float
    ai_perceived_speed_score: float
    ai_flow_momentum_score: float
    ai_pace_push_score: float
    ai_cadence_lock_score: float
    ai_groove_score: float
    ai_bass_drive_score: float
    ai_static_loop_penalty: float
    ai_static_low_end_penalty: float
    ai_chaos_penalty: float
    ai_role_match_score: float
    avoid_for_penalty: float
    excessive_jump_penalty: float
    repetition_penalty: float
    effective_pulse_value: float
    effective_pulse_relation: str
    energy_score_debug_only: float
    target_music_profile: TargetMusicProfile
    reason: str

    @property
    def cadence_alignment(self) -> float:
        return self.cadence_alignment_score


def clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def compute_pace_gap_ratio(current_pace_sec_per_km: float, target_pace_sec_per_km: float) -> float:
    if current_pace_sec_per_km <= 0 or target_pace_sec_per_km <= 0:
        raise ValueError("pace values must be positive")
    return (current_pace_sec_per_km - target_pace_sec_per_km) / target_pace_sec_per_km


def infer_target_cadence_from_pace(
    target_pace_sec_per_km: float,
    current_cadence_spm: float | None = None,
) -> float | None:
    if current_cadence_spm and current_cadence_spm > 0:
        return current_cadence_spm
    pace_min = target_pace_sec_per_km / 60.0
    if pace_min <= 4.5:
        return 174.0
    if pace_min <= 5.5:
        return 168.0
    if pace_min <= 6.5:
        return 162.0
    return 156.0


def infer_running_intention_from_profile_inputs(
    *,
    pace_gap_ratio: float,
    running_mode: str | None = None,
    fatigue_level: float | None = None,
) -> str:
    mode = (running_mode or "").lower()
    fatigue = clamp01(fatigue_level) if fatigue_level is not None else 0.0
    sprint_threshold = 0.16 if fatigue >= 0.65 else 0.14

    if mode in {"cool_down", "warm_down", "recovery"}:
        return RunningIntention.RECOVERY_OR_CONTROL.value
    if mode in {"sprint", "interval_high"} and pace_gap_ratio >= 0.06:
        return RunningIntention.SPRINT_PUSH.value
    if mode == "pace_up" and pace_gap_ratio >= sprint_threshold:
        return RunningIntention.SPRINT_PUSH.value
    if mode == "pace_up" and pace_gap_ratio >= 0.04:
        return RunningIntention.PACE_UP.value

    if pace_gap_ratio <= -0.04:
        return RunningIntention.RECOVERY_OR_CONTROL.value
    if pace_gap_ratio < 0.04:
        return RunningIntention.STEADY.value
    if pace_gap_ratio < sprint_threshold:
        return RunningIntention.PACE_UP.value
    return RunningIntention.SPRINT_PUSH.value


def build_target_music_profile(
    running_context: RunningContext | None = None,
    *,
    current_pace_sec_per_km: float | None = None,
    target_pace_sec_per_km: float | None = None,
    current_cadence_spm: float | None = None,
    target_cadence_spm: float | None = None,
    running_mode: str | None = None,
    fatigue_level: float | None = None,
) -> TargetMusicProfile:
    if running_context is not None:
        current_pace_sec_per_km = running_context.current_pace_sec_per_km
        target_pace_sec_per_km = running_context.target_pace_sec_per_km
        current_cadence_spm = running_context.current_cadence_spm
        target_cadence_spm = running_context.target_cadence_spm
        running_mode = (
            running_context.running_mode.value
            if isinstance(running_context.running_mode, RunningMode)
            else str(running_context.running_mode)
        )
        fatigue_level = running_context.fatigue_level

    if current_pace_sec_per_km is None or target_pace_sec_per_km is None:
        raise ValueError("current and target pace are required")

    gap = compute_pace_gap_ratio(current_pace_sec_per_km, target_pace_sec_per_km)
    intention = infer_running_intention_from_profile_inputs(
        pace_gap_ratio=gap,
        running_mode=running_mode,
        fatigue_level=fatigue_level,
    )
    cadence = target_cadence_spm or infer_target_cadence_from_pace(
        target_pace_sec_per_km=target_pace_sec_per_km,
        current_cadence_spm=current_cadence_spm,
    )

    if intention == RunningIntention.RECOVERY_OR_CONTROL.value:
        return TargetMusicProfile(
            running_intention=intention,
            pace_gap_ratio=gap,
            target_cadence_spm=cadence,
            desired_music_pulse_range=(90.0, 124.0),
            allowed_bpm_ranges=[(90.0, 112.0), (100.0, 124.0)],
            desired_push_range=(0.10, 0.45),
            max_bpm_jump=18.0,
            max_push_jump=0.30,
            allowed_transition_steps=["downshift", "same_level"],
            debug_reason="runner faster than target or recovery mode: lower/controlled pulse",
        )

    if intention == RunningIntention.STEADY.value:
        return TargetMusicProfile(
            running_intention=intention,
            pace_gap_ratio=gap,
            target_cadence_spm=cadence,
            desired_music_pulse_range=(118.0, 140.0),
            allowed_bpm_ranges=[(118.0, 130.0), (124.0, 140.0)],
            desired_push_range=(0.35, 0.65),
            max_bpm_jump=20.0,
            max_push_jump=0.28,
            allowed_transition_steps=["same_level", "small_up", "small_down"],
            debug_reason="near target pace: stable groove and low transition jump",
        )

    if intention == RunningIntention.PACE_UP.value:
        return TargetMusicProfile(
            running_intention=intention,
            pace_gap_ratio=gap,
            target_cadence_spm=cadence,
            desired_music_pulse_range=(132.0, 152.0),
            allowed_bpm_ranges=[(132.0, 145.0), (140.0, 152.0)],
            desired_push_range=(0.55, 0.82),
            max_bpm_jump=28.0,
            max_push_jump=0.38,
            allowed_transition_steps=["small_up", "medium_up", "bridge_up"],
            debug_reason="runner moderately slower than target: one-step faster pulse, not full sprint",
        )

    return TargetMusicProfile(
        running_intention=RunningIntention.SPRINT_PUSH.value,
        pace_gap_ratio=gap,
        target_cadence_spm=cadence,
        desired_music_pulse_range=(165.0, 176.0),
        allowed_bpm_ranges=[(165.0, 176.0), (150.0, 164.0)],
        desired_push_range=(0.75, 1.00),
        max_bpm_jump=45.0,
        max_push_jump=0.55,
        allowed_transition_steps=["medium_up", "large_up_if_needed"],
        debug_reason="runner far slower than target: direct cadence push is allowed",
    )


def maybe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def metadata_value(segment: Segment | Mapping[str, Any], key: str, default: Any = None) -> Any:
    if isinstance(segment, Mapping):
        if key in segment:
            return segment[key]
        metadata = segment.get("metadata", {})
        return metadata.get(key, default) if isinstance(metadata, Mapping) else default
    if hasattr(segment, key):
        value = getattr(segment, key)
        if isinstance(value, SectionType):
            return value.value
        return value
    return segment.metadata.get(key, default)


def segment_float(segment: Segment | Mapping[str, Any], key: str, default: float | None = 0.0) -> float | None:
    return maybe_float(metadata_value(segment, key, default), default)


def range_score(value: float, low: float, high: float, soft_margin: float = 18.0) -> float:
    if low <= value <= high:
        return 1.0
    if value < low:
        return clamp01(1.0 - (low - value) / soft_margin)
    return clamp01(1.0 - (value - high) / soft_margin)


def effective_pulse_alignment(
    bpm: float,
    target_cadence_spm: float | None,
) -> tuple[EffectivePulseRelation, float, float]:
    if bpm <= 0:
        return EffectivePulseRelation.UNKNOWN, 0.0, 0.5
    if not target_cadence_spm or target_cadence_spm <= 0:
        return EffectivePulseRelation.WORKOUT_PULSE, bpm, 0.5

    candidates = [
        (EffectivePulseRelation.DIRECT, bpm),
        (EffectivePulseRelation.HALF_TIME, bpm * 2.0),
        (EffectivePulseRelation.DOUBLE_TIME, bpm / 2.0),
    ]
    relation, pulse = min(candidates, key=lambda row: abs(row[1] - target_cadence_spm))
    diff = abs(pulse - target_cadence_spm)
    return relation, pulse, clamp01(1.0 - diff / 28.0)


def tempo_match_score(bpm: float, pulse_value: float, profile: TargetMusicProfile) -> float:
    if bpm <= 0:
        return 0.0
    raw_bpm_score = max(range_score(bpm, low, high) for low, high in profile.allowed_bpm_ranges)
    pulse_score = range_score(
        pulse_value,
        profile.desired_music_pulse_range[0],
        profile.desired_music_pulse_range[1],
    )
    workout_bonus = 0.0
    if 120.0 <= bpm <= 152.0 and profile.running_intention in {
        RunningIntention.STEADY.value,
        RunningIntention.PACE_UP.value,
    }:
        workout_bonus = 0.15
    return clamp01(0.62 * raw_bpm_score + 0.38 * pulse_score + workout_bonus)


def segment_pace_push_score(segment: Segment | Mapping[str, Any]) -> float:
    value = segment_float(segment, "ai_pace_push_score", None)
    if value is not None:
        return clamp01(value)
    value = segment_float(segment, "pace_push_score", None)
    if value is not None:
        return clamp01(value)
    onset = segment_float(segment, "onset_density_score", 0.0) or 0.0
    phrase = segment_float(segment, "phrase_confidence", 0.5) or 0.5
    energy = segment_float(segment, "energy_score", 0.5) or 0.5
    return clamp01(0.45 * onset + 0.30 * phrase + 0.25 * energy)


def segment_groove_score(segment: Segment | Mapping[str, Any]) -> float:
    value = segment_float(segment, "ai_groove_score", None)
    if value is not None:
        return clamp01(value)
    for key in ("groove_syncopation_fit", "groove_score"):
        value = segment_float(segment, key, None)
        if value is not None:
            return clamp01(value)
    phrase = segment_float(segment, "phrase_confidence", 0.5) or 0.5
    onset = segment_float(segment, "onset_density_score", 0.0) or 0.0
    return clamp01(0.55 * phrase + 0.45 * onset)


def segment_bass_drive_score(segment: Segment | Mapping[str, Any]) -> float:
    value = segment_float(segment, "ai_bass_drive_score", None)
    if value is not None:
        return clamp01(value)
    for key in ("bass_drive_score", "bass_strength_score"):
        value = segment_float(segment, key, None)
        if value is not None:
            return clamp01(value)
    return 0.35


def segment_static_low_end_penalty(segment: Segment | Mapping[str, Any]) -> float:
    value = segment_float(segment, "ai_static_low_end_penalty", None)
    if value is not None:
        return clamp01(value)
    value = segment_float(segment, "static_low_end_penalty", None)
    return clamp01(value) if value is not None else 0.0


def ai_feature_score(segment: Segment | Mapping[str, Any], key: str, fallback: float) -> float:
    value = segment_float(segment, key, None)
    return clamp01(value) if value is not None else clamp01(fallback)


def ai_role_match_score(segment: Segment | Mapping[str, Any], running_intention: str) -> float:
    recommended_for = set(metadata_value(segment, "recommended_for", []) or [])
    avoid_for = set(metadata_value(segment, "avoid_for", []) or [])
    role = str(metadata_value(segment, "ai_segment_role", ""))
    if running_intention in avoid_for:
        return 0.0
    if running_intention in recommended_for:
        return 1.0
    if running_intention == "pace_up" and role in {"steady_to_pace_up_bridge", "fast_light_control"}:
        return 0.78
    if running_intention == "steady" and role in {"steady_to_pace_up_bridge", "fast_light_control"}:
        return 0.82
    if running_intention == "recovery_or_control" and role in {"recovery", "low_drive_or_static"}:
        return 0.75
    if not role:
        return section_role_score_for_profile(segment, running_intention)
    return 0.45


def avoid_for_penalty(segment: Segment | Mapping[str, Any], running_intention: str) -> float:
    avoid_for = set(metadata_value(segment, "avoid_for", []) or [])
    if running_intention in avoid_for:
        return 1.0
    role = str(metadata_value(segment, "ai_segment_role", ""))
    section = str(metadata_value(segment, "section_type", "")).split(".")[-1].lower()
    if role:
        if running_intention == RunningIntention.SPRINT_PUSH.value and role in {"steady", "recovery", "low_drive_or_static"}:
            return 0.9
        if running_intention == RunningIntention.PACE_UP.value and section in {"intro", "outro"} and role == "steady":
            return 0.6
    else:
        if running_intention == RunningIntention.RECOVERY_OR_CONTROL.value and section in {"drop", "build_up"}:
            return 1.0
        if running_intention == RunningIntention.SPRINT_PUSH.value and section in {"intro", "outro", "breakdown"}:
            return 0.8
    return 0.0


def section_role_score_for_profile(segment: Segment | Mapping[str, Any], running_intention: str) -> float:
    section = str(
        metadata_value(segment, "corrected_section_type", None)
        or metadata_value(segment, "section_type", "groove")
    )
    section = section.split(".")[-1].lower()
    table = {
        RunningIntention.RECOVERY_OR_CONTROL.value: {
            "breakdown": 1.00,
            "outro": 0.85,
            "intro": 0.72,
            "groove": 0.60,
            "build_up": 0.25,
            "drop": 0.10,
        },
        RunningIntention.STEADY.value: {
            "groove": 1.00,
            "intro": 0.55,
            "build_up": 0.55,
            "drop": 0.50,
            "breakdown": 0.35,
            "outro": 0.30,
        },
        RunningIntention.PACE_UP.value: {
            "groove": 0.88,
            "build_up": 0.92,
            "drop": 0.78,
            "intro": 0.35,
            "breakdown": 0.20,
            "outro": 0.15,
        },
        RunningIntention.SPRINT_PUSH.value: {
            "drop": 1.00,
            "build_up": 0.75,
            "groove": 0.62,
            "intro": 0.15,
            "breakdown": 0.10,
            "outro": 0.05,
        },
    }
    return table.get(running_intention, {}).get(section, 0.50)


def current_music_state_from_segment(segment: Segment | None) -> CurrentMusicState | None:
    if segment is None:
        return None
    relation, pulse_value, _ = effective_pulse_alignment(segment.bpm, None)
    return CurrentMusicState(
        track_id=segment.track_id,
        segment_id=segment.segment_id,
        bpm=segment.bpm,
        effective_pulse_value=pulse_value if relation != EffectivePulseRelation.UNKNOWN else None,
        pace_push_score=segment_pace_push_score(segment),
        energy_score=segment.energy_score,
        section_type=segment.section_type.value,
    )


def transition_continuity_score(
    *,
    profile: TargetMusicProfile,
    current: CurrentMusicState | None,
    candidate_pulse_value: float,
    candidate_pace_push: float,
) -> tuple[float, float]:
    if current is None:
        return 0.70, 0.0

    current_pulse = current.effective_pulse_value or current.bpm
    if current_pulse is None or current_pulse <= 0:
        pulse_jump_score = 0.70
        pulse_jump_penalty = 0.0
    else:
        diff = abs(candidate_pulse_value - current_pulse)
        pulse_jump_score = clamp01(1.0 - diff / max(profile.max_bpm_jump, EPS))
        pulse_jump_penalty = clamp01((diff - profile.max_bpm_jump) / 40.0)

    if current.pace_push_score is None:
        push_jump_score = 0.70
        push_jump_penalty = 0.0
        direction_bonus = 0.0
    else:
        diff_push = abs(candidate_pace_push - current.pace_push_score)
        push_jump_score = clamp01(1.0 - diff_push / max(profile.max_push_jump, EPS))
        push_jump_penalty = clamp01((diff_push - profile.max_push_jump) / 0.60)
        delta = candidate_pace_push - current.pace_push_score
        if profile.running_intention in {RunningIntention.PACE_UP.value, RunningIntention.SPRINT_PUSH.value}:
            direction_bonus = 0.12 if delta >= -0.05 else -0.10
        elif profile.running_intention == RunningIntention.RECOVERY_OR_CONTROL.value:
            direction_bonus = 0.12 if delta <= 0.05 else -0.12
        else:
            direction_bonus = 0.08 if abs(delta) <= 0.20 else -0.05

    score = clamp01(0.55 * pulse_jump_score + 0.45 * push_jump_score + direction_bonus)
    penalty = clamp01(0.60 * pulse_jump_penalty + 0.40 * push_jump_penalty)
    return score, penalty


def repetition_penalty_for_segment(
    segment: Segment,
    playback_context: PlaybackContext,
) -> float:
    penalty = 0.0
    if segment.track_id and segment.track_id in playback_context.recent_track_ids:
        penalty += 0.45
    if segment.segment_id and segment.segment_id in playback_context.recent_segment_ids:
        penalty += 0.65
    if segment.track_id and segment.track_id == playback_context.current_track_id:
        penalty += 0.22
    if segment.segment_id and segment.segment_id == playback_context.current_segment_id:
        penalty += 0.80
    return clamp01(penalty)


def score_segment_for_profile(
    segment: Segment,
    profile: TargetMusicProfile,
    playback_context: PlaybackContext,
    current_music_state: CurrentMusicState | None = None,
) -> MusicProfileScoreBreakdown:
    bpm = segment.bpm
    relation, pulse_value, cadence_alignment = effective_pulse_alignment(bpm, profile.target_cadence_spm)
    tempo_match = tempo_match_score(bpm, pulse_value, profile)
    pace_push = segment_pace_push_score(segment)
    groove = segment_groove_score(segment)
    bass_drive = segment_bass_drive_score(segment)
    static_penalty = segment_static_low_end_penalty(segment)
    section_score = section_role_score_for_profile(segment, profile.running_intention)
    role_match = ai_role_match_score(segment, profile.running_intention)
    avoid_penalty = avoid_for_penalty(segment, profile.running_intention)
    ai_perceived_speed = ai_feature_score(segment, "ai_perceived_speed_score", tempo_match)
    ai_flow = ai_feature_score(segment, "ai_flow_momentum_score", pace_push)
    ai_pace_push = ai_feature_score(segment, "ai_pace_push_score", pace_push)
    ai_cadence_lock = ai_feature_score(segment, "ai_cadence_lock_score", cadence_alignment)
    ai_groove = ai_feature_score(segment, "ai_groove_score", groove)
    ai_bass = ai_feature_score(segment, "ai_bass_drive_score", bass_drive)
    ai_static_loop = ai_feature_score(segment, "ai_static_loop_penalty", 0.0)
    ai_static_low = ai_feature_score(segment, "ai_static_low_end_penalty", static_penalty)
    ai_chaos = ai_feature_score(segment, "ai_chaos_penalty", 0.0)
    transition_score, jump_penalty = transition_continuity_score(
        profile=profile,
        current=current_music_state,
        candidate_pulse_value=pulse_value,
        candidate_pace_push=ai_pace_push,
    )
    repetition_penalty = repetition_penalty_for_segment(segment, playback_context)

    final = (
        0.22 * tempo_match
        + 0.14 * cadence_alignment
        + 0.17 * transition_score
        + 0.18 * ai_pace_push
        + 0.13 * ai_flow
        + 0.07 * ai_groove
        + 0.05 * ai_cadence_lock
        + 0.04 * role_match
        - 0.16 * ai_static_loop
        - 0.12 * ai_static_low
        - 0.10 * ai_chaos
        - 0.10 * jump_penalty
        - 0.08 * avoid_penalty
        - 0.08 * repetition_penalty
    )
    final = clamp01(final)
    strongest = sorted(
        [
            ("tempo", tempo_match),
            ("cadence", cadence_alignment),
            ("transition", transition_score),
            ("ai_pace_push", ai_pace_push),
            ("ai_flow", ai_flow),
            ("ai_groove", ai_groove),
            ("ai_cadence_lock", ai_cadence_lock),
            ("ai_role", role_match),
        ],
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    reason = (
        f"profile={profile.running_intention}; "
        + ", ".join(f"{name}={score:.2f}" for name, score in strongest)
        + f"; ai_static_low={ai_static_low:.2f}; avoid={avoid_penalty:.2f}; jump={jump_penalty:.2f}"
    )

    return MusicProfileScoreBreakdown(
        final_score=final,
        running_intention=profile.running_intention,
        pace_gap_ratio=profile.pace_gap_ratio,
        tempo_match_score=tempo_match,
        cadence_alignment_score=cadence_alignment,
        transition_continuity_score=transition_score,
        pace_push_score=pace_push,
        groove_score=groove,
        bass_drive_score=bass_drive,
        section_role_score=section_score,
        static_low_end_penalty=static_penalty,
        ai_perceived_speed_score=ai_perceived_speed,
        ai_flow_momentum_score=ai_flow,
        ai_pace_push_score=ai_pace_push,
        ai_cadence_lock_score=ai_cadence_lock,
        ai_groove_score=ai_groove,
        ai_bass_drive_score=ai_bass,
        ai_static_loop_penalty=ai_static_loop,
        ai_static_low_end_penalty=ai_static_low,
        ai_chaos_penalty=ai_chaos,
        ai_role_match_score=role_match,
        avoid_for_penalty=avoid_penalty,
        excessive_jump_penalty=jump_penalty,
        repetition_penalty=repetition_penalty,
        effective_pulse_value=pulse_value,
        effective_pulse_relation=relation.value,
        energy_score_debug_only=segment.energy_score,
        target_music_profile=profile,
        reason=reason,
    )
