from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.models import PlaybackContext, RunningContext, RunningMode, SectionType, Segment
from app.recommendation.target_energy import compute_speed_gap_ratio
from app.recommendation.target_music_profile import (
    TargetMusicProfile,
    build_target_music_profile,
    current_music_state_from_segment,
    score_segment_for_profile,
)


@dataclass(frozen=True)
class SegmentScoreBreakdown:
    final_score: float
    energy_match: float
    cadence_match: float
    section_priority: float
    phrase_score: float
    repeat_penalty: float
    same_track_penalty: float


@dataclass(frozen=True)
class PaceAssistScoreBreakdown:
    final_score: float
    running_intention: str
    speed_gap_ratio: float
    cadence_alignment: float
    bpm_profile_match: float
    section_role_match: float
    beat_lock: float
    groove_score: float
    bass_drive_fit: float
    musical_motivation: float
    energy_fit: float
    contrast_score: float
    repeat_penalty: float
    reason: str
    target_music_profile: dict[str, Any] = field(default_factory=dict)
    tempo_match_score: float = 0.0
    cadence_alignment_score: float = 0.0
    transition_continuity_score: float = 0.0
    pace_push_score: float = 0.0
    effective_pulse_value: float = 0.0
    effective_pulse_relation: str = "unknown"
    energy_score_debug_only: float = 0.0
    excessive_jump_penalty: float = 0.0
    groove_score_profile: float = 0.0
    bass_drive_score: float = 0.0
    static_low_end_penalty: float = 0.0
    section_role_score: float = 0.0
    repetition_penalty: float = 0.0
    ai_perceived_speed_score: float = 0.0
    ai_flow_momentum_score: float = 0.0
    ai_pace_push_score: float = 0.0
    ai_cadence_lock_score: float = 0.0
    ai_groove_score: float = 0.0
    ai_bass_drive_score: float = 0.0
    ai_static_loop_penalty: float = 0.0
    ai_static_low_end_penalty: float = 0.0
    ai_chaos_penalty: float = 0.0
    ai_role_match_score: float = 0.0
    avoid_for_penalty: float = 0.0


INTENTION_POLICIES: dict[str, dict[str, Any]] = {
    "recovery": {
        "preferred_bpm_ranges": [(95, 112), (80, 95)],
        "preferred_sections": ["breakdown", "outro", "intro", "groove"],
        "avoid_sections": ["drop", "build_up"],
        "preferred_energy_range": (0.10, 0.45),
        "preferred_bass_drive_range": (0.00, 0.45),
        "preferred_syncopation_center": 0.25,
        "min_contrast_delta": 0.12,
        "weights": {
            "cadence_alignment": 0.10,
            "bpm_profile": 0.18,
            "section_role": 0.18,
            "beat_lock": 0.14,
            "groove": 0.10,
            "bass_drive_fit": 0.12,
            "musical_motivation": 0.08,
            "energy_fit": 0.10,
        },
    },
    "steady": {
        "preferred_bpm_ranges": [(118, 128), (120, 132)],
        "preferred_sections": ["groove"],
        "avoid_sections": ["intro", "outro"],
        "preferred_energy_range": (0.38, 0.66),
        "preferred_bass_drive_range": (0.30, 0.65),
        "preferred_syncopation_center": 0.42,
        "min_contrast_delta": 0.00,
        "weights": {
            "cadence_alignment": 0.14,
            "bpm_profile": 0.15,
            "section_role": 0.20,
            "beat_lock": 0.16,
            "groove": 0.13,
            "bass_drive_fit": 0.08,
            "musical_motivation": 0.09,
            "energy_fit": 0.05,
        },
    },
    "pace_up": {
        "preferred_bpm_ranges": [(132, 145), (128, 136)],
        "preferred_sections": ["build_up", "drop", "groove"],
        "avoid_sections": ["intro", "outro"],
        "preferred_energy_range": (0.58, 0.88),
        "preferred_bass_drive_range": (0.55, 0.90),
        "preferred_syncopation_center": 0.55,
        "min_contrast_delta": 0.10,
        "weights": {
            "cadence_alignment": 0.18,
            "bpm_profile": 0.17,
            "section_role": 0.15,
            "beat_lock": 0.14,
            "groove": 0.13,
            "bass_drive_fit": 0.12,
            "musical_motivation": 0.07,
            "energy_fit": 0.04,
        },
    },
    "sprint_push": {
        "preferred_bpm_ranges": [(165, 176), (150, 164)],
        "preferred_sections": ["drop", "build_up"],
        "avoid_sections": ["intro", "outro", "breakdown"],
        "preferred_energy_range": (0.72, 1.00),
        "preferred_bass_drive_range": (0.62, 1.00),
        "preferred_syncopation_center": 0.45,
        "min_contrast_delta": 0.16,
        "weights": {
            "cadence_alignment": 0.26,
            "bpm_profile": 0.18,
            "section_role": 0.14,
            "beat_lock": 0.13,
            "groove": 0.08,
            "bass_drive_fit": 0.12,
            "musical_motivation": 0.06,
            "energy_fit": 0.03,
        },
    },
}


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def mean_defined(values: list[float | None], default: float = 0.5) -> float:
    clean = [float(v) for v in values if v is not None]
    return sum(clean) / len(clean) if clean else default


def metadata_score(segment: Segment, key: str, default: float) -> float:
    value = segment.metadata.get(key, default)
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)


def compute_cadence_match(bpm: float, target_cadence_spm: float | None) -> float:
    if target_cadence_spm is None or target_cadence_spm <= 0 or bpm <= 0:
        return 0.5
    candidates = [bpm, bpm * 2.0, bpm / 2.0]
    diff = min(abs(c - target_cadence_spm) for c in candidates)
    return max(0.0, 1.0 - diff / 24.0)


def section_priority(section_type: SectionType | str) -> float:
    value = section_type.value if isinstance(section_type, SectionType) else str(section_type)
    return {
        SectionType.DROP.value: 1.00,
        SectionType.BUILD_UP.value: 0.88,
        SectionType.GROOVE.value: 0.72,
        SectionType.INTRO.value: 0.45,
        SectionType.BREAKDOWN.value: 0.35,
        SectionType.OUTRO.value: 0.25,
    }.get(value, 0.50)


def score_segment(
    segment: Segment,
    target_energy: float,
    target_cadence_spm: float | None,
    context: PlaybackContext,
) -> SegmentScoreBreakdown:
    """Compatibility scoring used by older tests and any legacy callers."""
    energy_match = 1.0 - min(abs(segment.energy_score - target_energy), 1.0)
    cadence_match = compute_cadence_match(segment.bpm, target_cadence_spm)
    sec_priority = section_priority(segment.section_type)
    phrase_score = clamp01(segment.phrase_confidence)
    repeat_penalty = 0.25 if segment.track_id in context.recent_track_ids else 0.0
    same_track_penalty = 0.20 if segment.track_id == context.current_track_id else 0.0

    final = (
        0.48 * energy_match
        + 0.18 * cadence_match
        + 0.14 * sec_priority
        + 0.12 * phrase_score
        - 0.05 * repeat_penalty
        - 0.03 * same_track_penalty
    )
    return SegmentScoreBreakdown(
        final_score=final,
        energy_match=energy_match,
        cadence_match=cadence_match,
        section_priority=sec_priority,
        phrase_score=phrase_score,
        repeat_penalty=repeat_penalty,
        same_track_penalty=same_track_penalty,
    )


def infer_running_intention(running_context: RunningContext) -> tuple[str, float]:
    profile = build_target_music_profile(running_context)
    return profile.running_intention, profile.pace_gap_ratio


def linear_tolerance_score(diff: float, tolerance: float) -> float:
    if tolerance <= 0:
        return 0.0
    return clamp01(1.0 - abs(float(diff)) / tolerance)


def bpm_range_score(bpm: float, ranges: list[tuple[float, float]]) -> float:
    if bpm <= 0:
        return 0.0
    best = 0.0
    for low, high in ranges:
        if low <= bpm <= high:
            return 1.0
        diff = low - bpm if bpm < low else bpm - high
        best = max(best, linear_tolerance_score(diff, 20.0))
    return clamp01(best)


def cadence_alignment_score(bpm: float, target_cadence_spm: float | None, intention: str) -> float:
    scores: list[float] = []
    if target_cadence_spm and target_cadence_spm > 0 and bpm > 0:
        scores.append(linear_tolerance_score(abs(bpm - target_cadence_spm), 18.0))
        scores.append(linear_tolerance_score(abs((bpm * 2.0) - target_cadence_spm), 18.0))
        scores.append(linear_tolerance_score(abs((bpm / 2.0) - target_cadence_spm), 18.0))

    if intention == "sprint_push":
        scores.append(bpm_range_score(bpm, [(160, 176), (150, 164)]))
    elif intention == "pace_up":
        scores.append(bpm_range_score(bpm, [(132, 145), (128, 136)]))
    elif intention == "steady":
        scores.append(bpm_range_score(bpm, [(118, 128), (120, 132)]))
    elif intention == "recovery":
        scores.append(bpm_range_score(bpm, [(95, 112), (80, 95)]))
    else:
        scores.append(bpm_range_score(bpm, [(120, 145)]))

    return clamp01(max(scores) if scores else 0.0)


def section_role_score(section_type: SectionType | str, preferred_sections: list[str], avoid_sections: list[str]) -> float:
    section = section_type.value if isinstance(section_type, SectionType) else str(section_type)
    section = section.lower()
    if section in preferred_sections:
        return 1.0
    if section in avoid_sections:
        return 0.15
    if section == "groove":
        return 0.70
    if section in {"build_up", "drop"}:
        return 0.75
    if section == "breakdown":
        return 0.45
    if section in {"intro", "outro"}:
        return 0.25
    return 0.50


def inverted_u_score(value: float, center: float, half_width: float = 0.45) -> float:
    if half_width <= 0:
        return 0.0
    return clamp01(1.0 - abs(clamp01(value) - center) / half_width)


def range_fit_score(value: float, preferred_range: tuple[float, float]) -> float:
    value = clamp01(value)
    low, high = preferred_range
    if low <= value <= high:
        return 1.0
    if value < low:
        return linear_tolerance_score(low - value, 0.35)
    return linear_tolerance_score(value - high, 0.35)


def beat_salience_score(segment: Segment) -> float:
    return metadata_score(segment, "beat_salience_score", segment.phrase_confidence)


def rhythmic_predictability_score(segment: Segment) -> float:
    return metadata_score(segment, "rhythmic_predictability_score", segment.phrase_confidence)


def rhythmic_activity_score(segment: Segment) -> float:
    return metadata_score(segment, "rhythmic_activity_score", segment.onset_density_score)


def syncopation_score(segment: Segment) -> float:
    return metadata_score(segment, "syncopation_score", 0.5)


def bass_drive_score(segment: Segment) -> float:
    fallback = mean_defined([segment.sound_density_score, segment.volume_score, segment.energy_score], default=segment.energy_score)
    # Until analysis produces a dedicated low-frequency bass feature, keep this
    # conservative: high volume/sound density alone should not make a light
    # segment look like a physically driving bass segment.
    fallback *= 0.55 + 0.45 * clamp01(segment.energy_score)
    return metadata_score(
        segment,
        "bass_drive_score",
        fallback,
    )


def musical_motivation_score(segment: Segment) -> float:
    if "pace_push_score" in segment.metadata:
        return metadata_score(segment, "pace_push_score", 0.5)
    return metadata_score(
        segment,
        "musical_motivation_score",
        mean_defined([segment.phrase_confidence, segment.brightness_score, segment.sound_density_score], default=0.5),
    )


def contrast_score_for_intention(segment: Segment, current_segment: Segment | None, intention: str, min_delta: float) -> float:
    if current_segment is None:
        return 0.7

    delta = segment.energy_score - current_segment.energy_score
    if intention in {"pace_up", "sprint_push"}:
        if delta >= min_delta:
            return 1.0
        return linear_tolerance_score(min_delta - delta, 0.35)
    if intention == "recovery":
        if -delta >= min_delta:
            return 1.0
        return linear_tolerance_score(min_delta + delta, 0.35)
    return clamp01(1.0 - abs(delta) / 0.35)


def anti_repeat_penalty(segment: Segment, playback_context: PlaybackContext) -> float:
    penalty = 0.0
    if segment.segment_id == playback_context.current_segment_id:
        penalty += 0.40
    if segment.segment_id in playback_context.recent_segment_ids:
        penalty += 0.20
    if segment.track_id == playback_context.current_track_id:
        penalty += 0.12
    if segment.track_id in playback_context.recent_track_ids:
        penalty += 0.08
    return min(0.50, penalty)


def build_reason(
    intention: str,
    cadence_alignment: float,
    bpm_profile: float,
    section_role: float,
    beat_lock: float,
    groove: float,
    bass_drive_fit: float,
    energy_fit: float,
    contrast: float,
    repeat_penalty: float,
) -> str:
    strongest = sorted(
        [
            ("cadence", cadence_alignment),
            ("bpm_profile", bpm_profile),
            ("section", section_role),
            ("beat_lock", beat_lock),
            ("groove", groove),
            ("bass_drive", bass_drive_fit),
            ("energy_fit", energy_fit),
            ("contrast", contrast),
        ],
        key=lambda item: item[1],
        reverse=True,
    )[:3]
    parts = ", ".join(f"{name}={score:.2f}" for name, score in strongest)
    return f"intention={intention}; strongest factors: {parts}; repeat_penalty={repeat_penalty:.2f}"


def intention_guardrail_penalty(segment: Segment, intention: str) -> float:
    """Prevent one strong factor from defeating the running role.

    This keeps cadence alignment from selecting a calm breakdown for a sprint,
    while still leaving energy as a small scoring feature instead of the main
    selector.
    """
    section = segment.section_type.value if isinstance(segment.section_type, SectionType) else str(segment.section_type)
    section = section.lower()

    if intention == "sprint_push":
        if segment.metadata.get("pace_role_hint") == "pace_up" and section == "groove":
            return 0.0 if metadata_score(segment, "pace_push_score", 0.0) >= 0.55 else 0.05

        penalty = 0.0
        if segment.energy_score < 0.65:
            penalty += 0.14
        if section not in {"drop", "build_up"}:
            penalty += 0.06
        if metadata_score(segment, "drop_likelihood_score", 0.5) < 0.45:
            penalty += 0.08
        if metadata_score(segment, "static_low_end_penalty", 0.0) > 0.45:
            penalty += 0.10
        return penalty

    if intention == "pace_up" and section in {"intro", "outro", "breakdown"}:
        return 0.05

    if intention == "recovery" and segment.energy_score > 0.55:
        return 0.08

    return 0.0


def main_body_pulse_bonus(segment: Segment, intention: str) -> float:
    """Small tie-breaker for established groove segments in pace-up runs."""
    if intention not in {"pace_up", "sprint_push"}:
        return 0.0

    section = segment.section_type.value if isinstance(segment.section_type, SectionType) else str(segment.section_type)
    if section.lower() != "groove":
        return 0.0

    if segment.metadata.get("pace_role_hint") != "pace_up":
        return 0.0

    if not (60.0 <= segment.start_sec <= 120.0):
        return 0.0

    groove_fit = metadata_score(segment, "groove_syncopation_fit", 0.5)
    pace_push = metadata_score(segment, "pace_push_score", 0.0)
    if groove_fit < 0.70 or pace_push < 0.55:
        return 0.0

    return 0.025


def score_segment_for_intention(
    segment: Segment,
    running_context: RunningContext,
    playback_context: PlaybackContext,
    current_segment: Segment | None = None,
    intention: str | None = None,
    speed_gap_ratio: float | None = None,
) -> PaceAssistScoreBreakdown:
    profile = build_target_music_profile(running_context)
    if intention == "recovery":
        intention = "recovery_or_control"
    if intention and intention != profile.running_intention:
        # Keep explicit test/debug overrides possible without introducing a
        # separate weight path. The profile remains the source of truth for
        # score shape; ordinary app calls do not take this branch.
        profile = TargetMusicProfile(
            running_intention=intention,
            pace_gap_ratio=profile.pace_gap_ratio if speed_gap_ratio is None else speed_gap_ratio,
            target_cadence_spm=profile.target_cadence_spm,
            desired_music_pulse_range=profile.desired_music_pulse_range,
            allowed_bpm_ranges=profile.allowed_bpm_ranges,
            desired_push_range=profile.desired_push_range,
            max_bpm_jump=profile.max_bpm_jump,
            max_push_jump=profile.max_push_jump,
            allowed_transition_steps=profile.allowed_transition_steps,
            debug_reason=profile.debug_reason,
        )
    current_state = current_music_state_from_segment(current_segment)
    music_score = score_segment_for_profile(
        segment,
        profile,
        playback_context,
        current_music_state=current_state,
    )
    beat_lock = clamp01(
        0.45 * beat_salience_score(segment)
        + 0.35 * rhythmic_predictability_score(segment)
        + 0.20 * clamp01(segment.phrase_confidence)
    )
    return PaceAssistScoreBreakdown(
        final_score=music_score.final_score,
        running_intention=music_score.running_intention,
        speed_gap_ratio=music_score.pace_gap_ratio,
        cadence_alignment=music_score.cadence_alignment_score,
        bpm_profile_match=music_score.tempo_match_score,
        section_role_match=music_score.section_role_score,
        beat_lock=beat_lock,
        groove_score=music_score.groove_score,
        bass_drive_fit=music_score.bass_drive_score,
        musical_motivation=music_score.pace_push_score,
        energy_fit=music_score.energy_score_debug_only,
        contrast_score=music_score.transition_continuity_score,
        repeat_penalty=music_score.repetition_penalty,
        reason=music_score.reason,
        target_music_profile=music_score.target_music_profile.to_debug_dict(),
        tempo_match_score=music_score.tempo_match_score,
        cadence_alignment_score=music_score.cadence_alignment_score,
        transition_continuity_score=music_score.transition_continuity_score,
        pace_push_score=music_score.pace_push_score,
        effective_pulse_value=music_score.effective_pulse_value,
        effective_pulse_relation=music_score.effective_pulse_relation,
        energy_score_debug_only=music_score.energy_score_debug_only,
        excessive_jump_penalty=music_score.excessive_jump_penalty,
        groove_score_profile=music_score.groove_score,
        bass_drive_score=music_score.bass_drive_score,
        static_low_end_penalty=music_score.static_low_end_penalty,
        section_role_score=music_score.section_role_score,
        repetition_penalty=music_score.repetition_penalty,
        ai_perceived_speed_score=music_score.ai_perceived_speed_score,
        ai_flow_momentum_score=music_score.ai_flow_momentum_score,
        ai_pace_push_score=music_score.ai_pace_push_score,
        ai_cadence_lock_score=music_score.ai_cadence_lock_score,
        ai_groove_score=music_score.ai_groove_score,
        ai_bass_drive_score=music_score.ai_bass_drive_score,
        ai_static_loop_penalty=music_score.ai_static_loop_penalty,
        ai_static_low_end_penalty=music_score.ai_static_low_end_penalty,
        ai_chaos_penalty=music_score.ai_chaos_penalty,
        ai_role_match_score=music_score.ai_role_match_score,
        avoid_for_penalty=music_score.avoid_for_penalty,
    )
