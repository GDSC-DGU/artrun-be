
"""
speed_degree_pace_core_v2.py

Speed-degree based core for Multi-Model EDM Pace Analyzer v2.

v2 shifts the center from intention buckets to continuous speed-degree control:
current_speed_kmh vs target_speed_kmh
-> music_pace_control (-1.0 to +1.0)
-> target_music_speed_degree (0.15 to 0.85)
-> match segment.music_speed_degree

The debug intention label is retained for human readability only.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Sequence


class SegmentUse(str, Enum):
    STABLE = "STABLE"
    TRANSITION = "TRANSITION"
    ENTRY_ONLY = "ENTRY_ONLY"
    EXIT_ONLY = "EXIT_ONLY"
    REJECT = "REJECT"


class TransitionType(str, Enum):
    NONE = "NONE"
    BUILD_TO_DROP = "BUILD_TO_DROP"
    BREAKDOWN_TO_BUILD = "BREAKDOWN_TO_BUILD"
    GROOVE_TO_BUILD = "GROOVE_TO_BUILD"
    GROOVE_TO_DROP = "GROOVE_TO_DROP"
    DROP_TO_GROOVE = "DROP_TO_GROOVE"
    DROP_TO_BREAKDOWN = "DROP_TO_BREAKDOWN"
    INTRO_TO_GROOVE = "INTRO_TO_GROOVE"
    MIXED_UNKNOWN = "MIXED_UNKNOWN"


@dataclass(frozen=True)
class RunnerSpeedState:
    current_speed_kmh: float
    target_speed_kmh: float
    speed_20s_ago_kmh: float | None = None
    current_cadence_spm: float | None = None
    fatigue_score: float = 0.0


@dataclass(frozen=True)
class TargetMusicProfileV2:
    target_speed_kmh: float
    current_speed_kmh: float
    speed_20s_ago_kmh: float | None
    speed_gap_ratio: float
    speed_trend_ratio: float
    music_pace_control: float
    target_music_speed_degree: float
    debug_intention_label: str
    target_effective_pulse_range: tuple[float, float]
    target_cadence_lock_min: float
    target_pace_push_range: tuple[float, float]
    target_flow_momentum_range: tuple[float, float]
    target_rhythm_predictability_min: float
    target_beat_salience_min: float
    target_transition_slope: float
    target_transition_direction: str
    allow_connector: bool
    max_push_jump: float
    max_pulse_jump: float
    max_loudness_jump: float
    forbidden: list[str]


@dataclass(frozen=True)
class StructureFieldsV2:
    segment_id: str
    track_id: str
    start_sec: float
    end_sec: float
    start_bar: int
    end_bar: int
    duration_bars: int
    segment_use: str
    transition_type: str = TransitionType.NONE.value
    transition_slope: float = 0.0
    flow_direction: str = "flat"
    target_after_transition: str | None = None
    entry_quality: float = 0.7
    exit_quality: float = 0.7
    phrase_confidence: float = 0.7
    is_contiguous_original_audio: bool = True


@dataclass(frozen=True)
class RhythmSignalFeaturesV2:
    bpm: float
    effective_pulse_bpm: float
    pulse_relation: str
    beat_confidence: float
    downbeat_confidence: float
    cadence_lock_support: float
    beat_salience_score: float
    onset_density_score: float
    rhythm_predictability_score: float
    groove_stability_score: float
    tempogram_strength_score: float


@dataclass(frozen=True)
class TimbreEnergyFeaturesV2:
    bass_energy_score: float
    bass_modulation_score: float
    low_end_stability_score: float
    loudness_density_score: float
    loudness_change_score: float
    spectral_brightness_score: float
    brightness_change_score: float
    static_loop_penalty: float
    static_low_end_penalty: float
    chaos_penalty: float


@dataclass(frozen=True)
class ModelFeatureScoresV2:
    model_speed_degree: float | None = None
    model_drive_score: float | None = None
    model_groove_score: float | None = None
    model_transition_score: float | None = None
    model_stability_score: float | None = None
    model_confidence: float = 0.0
    semantic_speed_degree: float | None = None
    semantic_confidence: float = 0.0


@dataclass(frozen=True)
class PaceFeatureVectorV2:
    music_speed_degree: float
    effective_pulse_bpm: float
    cadence_lock_support: float
    beat_salience_score: float
    rhythm_predictability_score: float
    onset_density_score: float
    groove_stability_score: float
    bass_modulation_score: float
    flow_momentum_score: float
    pace_push_score: float
    transition_slope: float
    transition_usefulness_score: float
    target_arrival_score: float
    intro_like_score: float
    pulse_drop_score: float
    drive_preservation_score: float
    connector_drive_score: float
    overpush_risk: float
    chaos_risk: float
    static_risk: float
    model_confidence: float
    signal_confidence: float
    combined_confidence: float
    fusion_weights: dict[str, float] = field(default_factory=dict)
    debug_components: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentAnalysisV2:
    structure: StructureFieldsV2
    rhythm: RhythmSignalFeaturesV2
    timbre: TimbreEnergyFeaturesV2
    model: ModelFeatureScoresV2
    pace_vector: PaceFeatureVectorV2


def build_target_music_profile_v2(state: RunnerSpeedState) -> TargetMusicProfileV2:
    """Create continuous target music values from real running speed."""
    if state.target_speed_kmh <= 0:
        raise ValueError("target_speed_kmh must be positive")
    if state.current_speed_kmh <= 0:
        raise ValueError("current_speed_kmh must be positive")

    speed_gap_ratio = (state.target_speed_kmh - state.current_speed_kmh) / state.target_speed_kmh
    if state.speed_20s_ago_kmh is None:
        speed_trend_ratio = 0.0
    else:
        speed_trend_ratio = (state.current_speed_kmh - state.speed_20s_ago_kmh) / state.target_speed_kmh

    music_pace_control = clamp((speed_gap_ratio - 0.5 * speed_trend_ratio) / 0.42, -1.0, 1.0)
    target_music_speed_degree = clamp(0.50 + 0.35 * music_pace_control, 0.15, 0.85)
    label = debug_label_from_control(music_pace_control)

    target_cadence_lock_min = interpolate_by_control(music_pace_control, 0.45, 0.62, 0.82)
    target_beat_salience_min = interpolate_by_control(music_pace_control, 0.45, 0.60, 0.78)
    target_rhythm_predictability_min = interpolate_by_control(music_pace_control, 0.55, 0.64, 0.72)
    push_center = target_music_speed_degree
    flow_center = clamp(0.48 + 0.35 * music_pace_control, 0.18, 0.88)

    pulse_low = interpolate_by_control(music_pace_control, 90, 118, 132)
    pulse_high = interpolate_by_control(music_pace_control, 124, 140, 156)

    target_transition_slope = clamp(music_pace_control, -1.0, 1.0)
    if target_transition_slope >= 0.25:
        direction = "up"
    elif target_transition_slope <= -0.25:
        direction = "down"
    else:
        direction = "flat"

    forbidden = ["chaotic_section", "static_loop"]
    if music_pace_control > 0.20:
        forbidden.extend(["down_transition", "deep_recovery_section", "excessive_overpush"])
    elif music_pace_control < -0.20:
        forbidden.extend(["up_transition", "build_to_drop", "high_push"])

    return TargetMusicProfileV2(
        target_speed_kmh=state.target_speed_kmh,
        current_speed_kmh=state.current_speed_kmh,
        speed_20s_ago_kmh=state.speed_20s_ago_kmh,
        speed_gap_ratio=speed_gap_ratio,
        speed_trend_ratio=speed_trend_ratio,
        music_pace_control=music_pace_control,
        target_music_speed_degree=target_music_speed_degree,
        debug_intention_label=label,
        target_effective_pulse_range=(round(pulse_low, 2), round(pulse_high, 2)),
        target_cadence_lock_min=round(target_cadence_lock_min, 4),
        target_pace_push_range=bounded_range(push_center, width=0.16, lo=0.08, hi=0.92),
        target_flow_momentum_range=bounded_range(flow_center, width=0.16, lo=0.12, hi=0.92),
        target_rhythm_predictability_min=round(target_rhythm_predictability_min, 4),
        target_beat_salience_min=round(target_beat_salience_min, 4),
        target_transition_slope=target_transition_slope,
        target_transition_direction=direction,
        allow_connector=True,
        max_push_jump=round(interpolate_abs_control(abs(music_pace_control), 0.25, 0.48), 4),
        max_pulse_jump=round(interpolate_abs_control(abs(music_pace_control), 18, 42), 2),
        max_loudness_jump=round(interpolate_abs_control(abs(music_pace_control), 0.22, 0.35), 4),
        forbidden=forbidden,
    )


def build_pace_feature_vector_v2(
    *,
    structure: StructureFieldsV2,
    rhythm: RhythmSignalFeaturesV2,
    timbre: TimbreEnergyFeaturesV2,
    model: ModelFeatureScoresV2 = ModelFeatureScoresV2(),
) -> PaceFeatureVectorV2:
    signal_conf = compute_signal_confidence_v2(structure=structure, rhythm=rhythm, timbre=timbre)
    signal = compute_signal_degrees_v2(structure=structure, rhythm=rhythm, timbre=timbre)
    weights = choose_v2_fusion_weights(
        signal_confidence=signal_conf,
        model_confidence=model.model_confidence if model.model_speed_degree is not None else None,
        semantic_confidence=model.semantic_confidence if model.semantic_speed_degree is not None else None,
    )

    model_degree = model.model_speed_degree if model.model_speed_degree is not None else signal["music_speed_degree"]
    semantic_degree = model.semantic_speed_degree if model.semantic_speed_degree is not None else signal["music_speed_degree"]

    music_speed_degree = clamp01(
        weights["signal"] * signal["music_speed_degree"]
        + weights["model"] * model_degree
        + weights["semantic"] * semantic_degree
    )
    model_conf = clamp01(weights["model"] * model.model_confidence + weights["semantic"] * model.semantic_confidence)
    combined_conf = clamp01(
        weights["signal"] * signal_conf
        + weights["model"] * (model.model_confidence if model.model_speed_degree is not None else 0.0)
        + weights["semantic"] * (model.semantic_confidence if model.semantic_speed_degree is not None else 0.0)
    )

    return PaceFeatureVectorV2(
        music_speed_degree=music_speed_degree,
        effective_pulse_bpm=rhythm.effective_pulse_bpm,
        cadence_lock_support=rhythm.cadence_lock_support,
        beat_salience_score=rhythm.beat_salience_score,
        rhythm_predictability_score=rhythm.rhythm_predictability_score,
        onset_density_score=rhythm.onset_density_score,
        groove_stability_score=rhythm.groove_stability_score,
        bass_modulation_score=timbre.bass_modulation_score,
        flow_momentum_score=signal["flow_momentum_score"],
        pace_push_score=signal["pace_push_score"],
        transition_slope=structure.transition_slope,
        transition_usefulness_score=signal["transition_usefulness_score"],
        target_arrival_score=signal["target_arrival_score"],
        intro_like_score=signal["intro_like_score"],
        pulse_drop_score=signal["pulse_drop_score"],
        drive_preservation_score=signal["drive_preservation_score"],
        connector_drive_score=signal["connector_drive_score"],
        overpush_risk=signal["overpush_risk"],
        chaos_risk=signal["chaos_risk"],
        static_risk=signal["static_risk"],
        model_confidence=model_conf,
        signal_confidence=signal_conf,
        combined_confidence=combined_conf,
        fusion_weights=weights,
        debug_components=signal,
    )


def compute_signal_degrees_v2(
    *,
    structure: StructureFieldsV2,
    rhythm: RhythmSignalFeaturesV2,
    timbre: TimbreEnergyFeaturesV2,
) -> dict[str, float]:
    flow = clamp01(
        0.22 * rhythm.cadence_lock_support
        + 0.18 * rhythm.beat_salience_score
        + 0.16 * rhythm.onset_density_score
        + 0.15 * rhythm.rhythm_predictability_score
        + 0.12 * rhythm.groove_stability_score
        + 0.12 * timbre.bass_modulation_score
        + 0.05 * positive_trend(timbre.brightness_change_score, timbre.loudness_change_score)
        - 0.16 * timbre.static_loop_penalty
        - 0.14 * timbre.chaos_penalty
    )
    push = clamp01(
        0.22 * rhythm.cadence_lock_support
        + 0.17 * rhythm.beat_salience_score
        + 0.15 * rhythm.rhythm_predictability_score
        + 0.14 * rhythm.onset_density_score
        + 0.13 * flow
        + 0.12 * timbre.bass_modulation_score
        + 0.07 * max(0.0, structure.transition_slope)
        - 0.12 * timbre.static_low_end_penalty
        - 0.12 * timbre.chaos_penalty
    )
    transition_use = clamp01(
        0.25 * abs(structure.transition_slope)
        + 0.20 * flow
        + 0.18 * push
        + 0.16 * structure.entry_quality
        + 0.13 * structure.exit_quality
        + 0.08 * structure.phrase_confidence
        - 0.12 * timbre.chaos_penalty
    )
    target_arrival = clamp01(
        0.34 * transition_use
        + 0.20 * rhythm.beat_salience_score
        + 0.18 * rhythm.rhythm_predictability_score
        + 0.14 * structure.exit_quality
        + 0.14 * structure.phrase_confidence
    )
    overpush = clamp01(
        0.28 * timbre.loudness_density_score
        + 0.22 * rhythm.onset_density_score
        + 0.20 * timbre.spectral_brightness_score
        + 0.18 * push
        + 0.12 * max(0.0, structure.transition_slope)
        - 0.18 * rhythm.rhythm_predictability_score
    )
    chaos = clamp01(
        timbre.chaos_penalty
        + 0.18 * max(0.0, rhythm.onset_density_score - rhythm.rhythm_predictability_score)
        + 0.12 * max(0.0, timbre.loudness_change_score - 0.5)
    )
    static = clamp01(
        0.52 * timbre.static_loop_penalty
        + 0.30 * timbre.static_low_end_penalty
        + 0.18 * max(0.0, timbre.bass_energy_score - timbre.bass_modulation_score)
    )
    music_speed_degree = clamp01(
        0.18 * effective_pulse_score(rhythm.effective_pulse_bpm)
        + 0.16 * rhythm.cadence_lock_support
        + 0.13 * rhythm.beat_salience_score
        + 0.12 * rhythm.rhythm_predictability_score
        + 0.11 * rhythm.onset_density_score
        + 0.11 * flow
        + 0.10 * push
        + 0.08 * timbre.bass_modulation_score
        + 0.05 * max(0.0, structure.transition_slope)
        - 0.10 * chaos
        - 0.08 * static
        - 0.06 * overpush
    )
    intro_like = clamp01(
        (0.65 if structure.segment_use == SegmentUse.ENTRY_ONLY.value else 0.0)
        + (0.35 if structure.transition_type == TransitionType.INTRO_TO_GROOVE.value else 0.0)
        + 0.20 * max(0.0, 0.55 - rhythm.beat_salience_score)
        + 0.20 * max(0.0, 0.58 - rhythm.cadence_lock_support)
    )
    pulse_drop = clamp01(
        0.35 * max(0.0, 0.55 - rhythm.beat_salience_score)
        + 0.30 * max(0.0, 0.58 - rhythm.cadence_lock_support)
        + 0.25 * max(0.0, 0.50 - flow)
        + 0.10 * max(0.0, -structure.transition_slope)
    )
    drive_preservation = clamp01(
        0.30 * rhythm.beat_salience_score
        + 0.25 * rhythm.cadence_lock_support
        + 0.20 * flow
        + 0.15 * push
        + 0.10 * timbre.bass_modulation_score
        - 0.20 * pulse_drop
        - 0.15 * intro_like
    )
    connector_drive = clamp01(
        0.28 * drive_preservation
        + 0.24 * rhythm.beat_salience_score
        + 0.20 * rhythm.cadence_lock_support
        + 0.18 * flow
        + 0.10 * timbre.bass_modulation_score
        - 0.18 * static
        - 0.16 * chaos
    )
    return {
        "music_speed_degree": music_speed_degree,
        "flow_momentum_score": flow,
        "pace_push_score": push,
        "transition_usefulness_score": transition_use,
        "target_arrival_score": target_arrival,
        "intro_like_score": intro_like,
        "pulse_drop_score": pulse_drop,
        "drive_preservation_score": drive_preservation,
        "connector_drive_score": connector_drive,
        "overpush_risk": overpush,
        "chaos_risk": chaos,
        "static_risk": static,
        "effective_pulse_score": effective_pulse_score(rhythm.effective_pulse_bpm),
    }


def stable_score_v2(
    *,
    analysis: SegmentAnalysisV2,
    target: TargetMusicProfileV2,
    current_segment_id: str | None = None,
    recent_segment_ids: Sequence[str] = (),
) -> tuple[float, dict[str, Any]]:
    ok, reason = hard_filter_v2(
        analysis=analysis, target=target, current_segment_id=current_segment_id,
        recent_segment_ids=recent_segment_ids, as_connector=False
    )
    if not ok:
        return 0.0, {"reject_reason": reason}
    if analysis.structure.segment_use != SegmentUse.STABLE.value:
        return 0.0, {"reject_reason": "not_STABLE_main_candidate"}

    p, r, s = analysis.pace_vector, analysis.rhythm, analysis.structure
    speed_degree_match = degree_match(p.music_speed_degree, target.target_music_speed_degree)
    pulse_match = range_match(r.effective_pulse_bpm, target.target_effective_pulse_range)
    cadence_match = threshold_match(p.cadence_lock_support, target.target_cadence_lock_min)
    push_match = range_match(p.pace_push_score, target.target_pace_push_range)
    flow_match = range_match(p.flow_momentum_score, target.target_flow_momentum_range)
    rhythm_match = threshold_match(p.rhythm_predictability_score, target.target_rhythm_predictability_min)
    beat_match = threshold_match(p.beat_salience_score, target.target_beat_salience_min)
    quality = clamp01((s.entry_quality + s.exit_quality + s.phrase_confidence) / 3.0)

    score = clamp01(
        0.20 * speed_degree_match
        + 0.15 * pulse_match
        + 0.14 * cadence_match
        + 0.13 * push_match
        + 0.12 * flow_match
        + 0.10 * rhythm_match
        + 0.08 * beat_match
        + 0.06 * quality
        + 0.04 * p.combined_confidence
        - 0.10 * p.overpush_risk
        - 0.10 * p.chaos_risk
        - 0.08 * p.static_risk
    )
    return score, {
        "music_speed_degree_match": round(speed_degree_match, 4),
        "segment_music_speed_degree": round(p.music_speed_degree, 4),
        "target_music_speed_degree": round(target.target_music_speed_degree, 4),
        "effective_pulse_match": round(pulse_match, 4),
        "cadence_lock_match": round(cadence_match, 4),
        "pace_push_match": round(push_match, 4),
        "flow_momentum_match": round(flow_match, 4),
        "rhythm_predictability_match": round(rhythm_match, 4),
        "beat_salience_match": round(beat_match, 4),
        "entry_exit_quality": round(quality, 4),
        "final_score": round(score, 4),
    }


def connector_score_v2(
    *,
    analysis: SegmentAnalysisV2,
    target: TargetMusicProfileV2,
    current_segment_id: str | None = None,
    recent_segment_ids: Sequence[str] = (),
    runtime_context: str = "runtime",
) -> tuple[float, dict[str, Any]]:
    ok, reason = hard_filter_v2(
        analysis=analysis, target=target, current_segment_id=current_segment_id,
        recent_segment_ids=recent_segment_ids, as_connector=True, runtime_context=runtime_context
    )
    if not ok:
        return 0.0, {"reject_reason": reason}
    if analysis.structure.segment_use not in {SegmentUse.TRANSITION.value, SegmentUse.ENTRY_ONLY.value, SegmentUse.EXIT_ONLY.value}:
        return 0.0, {"reject_reason": "not_connector_candidate"}

    p, s = analysis.pace_vector, analysis.structure
    transition_slope_match = slope_match(s.transition_slope, target.target_transition_slope)
    speed_degree_match = degree_match(p.music_speed_degree, target.target_music_speed_degree)
    flow_match = range_match(p.flow_momentum_score, target.target_flow_momentum_range)
    push_match = range_match(p.pace_push_score, target.target_pace_push_range)
    quality = clamp01((s.entry_quality + s.exit_quality + s.phrase_confidence) / 3.0)

    score = clamp01(
        0.16 * transition_slope_match
        + 0.16 * speed_degree_match
        + 0.14 * p.transition_usefulness_score
        + 0.12 * p.target_arrival_score
        + 0.13 * p.drive_preservation_score
        + 0.13 * p.connector_drive_score
        + 0.08 * flow_match
        + 0.06 * push_match
        + 0.04 * quality
        + 0.03 * p.combined_confidence
        - 0.14 * p.pulse_drop_score
        - 0.12 * p.intro_like_score
        - 0.10 * p.chaos_risk
        - 0.08 * p.overpush_risk
    )
    return score, {
        "transition_slope_match": round(transition_slope_match, 4),
        "segment_transition_slope": round(s.transition_slope, 4),
        "target_transition_slope": round(target.target_transition_slope, 4),
        "music_speed_degree_match": round(speed_degree_match, 4),
        "segment_music_speed_degree": round(p.music_speed_degree, 4),
        "target_music_speed_degree": round(target.target_music_speed_degree, 4),
        "transition_usefulness_score": round(p.transition_usefulness_score, 4),
        "target_arrival_score": round(p.target_arrival_score, 4),
        "drive_preservation_score": round(p.drive_preservation_score, 4),
        "connector_drive_score": round(p.connector_drive_score, 4),
        "pulse_drop_score": round(p.pulse_drop_score, 4),
        "intro_like_score": round(p.intro_like_score, 4),
        "flow_momentum_match": round(flow_match, 4),
        "pace_push_match": round(push_match, 4),
        "entry_exit_quality": round(quality, 4),
        "final_score": round(score, 4),
    }


def hard_filter_v2(
    *,
    analysis: SegmentAnalysisV2,
    target: TargetMusicProfileV2,
    current_segment_id: str | None,
    recent_segment_ids: Sequence[str],
    as_connector: bool,
    runtime_context: str = "runtime",
) -> tuple[bool, str | None]:
    s, p, r = analysis.structure, analysis.pace_vector, analysis.rhythm
    if not s.is_contiguous_original_audio:
        return False, "not_contiguous_original_audio"
    if s.segment_use == SegmentUse.REJECT.value:
        return False, "segment_use_REJECT"
    if current_segment_id is not None and s.segment_id == current_segment_id:
        return False, "current_segment_hard_exclude"
    if s.segment_id in set(recent_segment_ids):
        return False, "recent_segment_hard_exclude"
    if r.beat_confidence < 0.45:
        return False, "low_beat_confidence"
    if r.downbeat_confidence < 0.40:
        return False, "low_downbeat_confidence"
    if s.phrase_confidence < 0.45:
        return False, "low_phrase_confidence"
    if p.combined_confidence < 0.35:
        return False, "low_combined_confidence"
    if p.chaos_risk >= 0.75:
        return False, "chaos_risk_too_high"
    if p.static_risk >= 0.82:
        return False, "static_risk_too_high"
    if as_connector:
        if s.segment_use == SegmentUse.ENTRY_ONLY.value and runtime_context != "initial_entry":
            return False, "ENTRY_ONLY_blocked_during_runtime"
        if p.intro_like_score >= 0.55 and runtime_context != "initial_entry":
            return False, "intro_like_connector_blocked"
        if p.beat_salience_score < 0.55:
            return False, "connector_low_beat_salience"
        if p.cadence_lock_support < 0.58:
            return False, "connector_low_cadence_lock"
        if p.flow_momentum_score < 0.50:
            return False, "connector_low_flow_momentum"
        if p.music_speed_degree < target.target_music_speed_degree - 0.22:
            return False, "connector_drops_music_speed_degree"
    if target.music_pace_control > 0.20 and s.transition_slope < -0.25:
        return False, "negative_transition_slope_blocked_for_positive_control"
    if target.music_pace_control < -0.20 and s.transition_slope > 0.25:
        return False, "positive_transition_slope_blocked_for_negative_control"
    if not as_connector and s.segment_use != SegmentUse.STABLE.value:
        return False, "non_STABLE_not_allowed_as_main"
    return True, None


def choose_v2_fusion_weights(*, signal_confidence: float, model_confidence: float | None, semantic_confidence: float | None) -> dict[str, float]:
    if model_confidence is None and semantic_confidence is None:
        return {"signal": 1.0, "model": 0.0, "semantic": 0.0}
    raw = {
        "signal": 0.50 * max(0.25, signal_confidence),
        "model": 0.38 * max(0.25, model_confidence or 0.0),
        "semantic": 0.12 * max(0.20, semantic_confidence or 0.0),
    }
    if model_confidence is None:
        raw["model"] = 0.0
    if semantic_confidence is None:
        raw["semantic"] = 0.0
    total = sum(raw.values()) or 1.0
    return {k: round(v / total, 4) for k, v in raw.items()}


def compute_signal_confidence_v2(*, structure: StructureFieldsV2, rhythm: RhythmSignalFeaturesV2, timbre: TimbreEnergyFeaturesV2) -> float:
    base = (
        0.24 * rhythm.beat_confidence
        + 0.20 * rhythm.downbeat_confidence
        + 0.18 * structure.phrase_confidence
        + 0.12 * structure.entry_quality
        + 0.12 * structure.exit_quality
        + 0.08 * rhythm.rhythm_predictability_score
        + 0.06 * (1.0 - timbre.chaos_penalty)
    )
    if not structure.is_contiguous_original_audio:
        base -= 0.45
    if structure.segment_use == SegmentUse.REJECT.value:
        base -= 0.35
    return clamp01(base)


def debug_label_from_control(control: float) -> str:
    if control <= -0.80:
        return "deep_recovery"
    if control <= -0.40:
        return "recovery"
    if control <= -0.15:
        return "light_control"
    if control < 0.15:
        return "steady"
    if control < 0.35:
        return "gentle_push"
    if control < 0.70:
        return "controlled_push"
    if control < 0.90:
        return "strong_push"
    return "rhythm_rebuild"


def effective_pulse_score(effective_pulse_bpm: float) -> float:
    if effective_pulse_bpm < 80:
        return 0.20
    if effective_pulse_bpm <= 110:
        return interpolate(effective_pulse_bpm, 80, 110, 0.25, 0.50)
    if effective_pulse_bpm <= 140:
        return interpolate(effective_pulse_bpm, 110, 140, 0.50, 0.75)
    if effective_pulse_bpm <= 176:
        return interpolate(effective_pulse_bpm, 140, 176, 0.75, 0.95)
    return 0.70


def degree_match(value: float, target: float) -> float:
    return clamp01(1.0 - abs(value - target) / 0.45)


def slope_match(value: float, target: float) -> float:
    return clamp01(1.0 - abs(value - target) / 1.35)


def range_match(value: float, target_range: tuple[float, float]) -> float:
    lo, hi = target_range
    if lo <= value <= hi:
        return 1.0
    margin = max(0.05, (hi - lo) * 0.75)
    if value < lo:
        return clamp01(1.0 - (lo - value) / margin)
    return clamp01(1.0 - (value - hi) / margin)


def threshold_match(value: float, minimum: float) -> float:
    if value >= minimum:
        return 1.0
    return clamp01(value / max(0.05, minimum))


def bounded_range(center: float, width: float, lo: float, hi: float) -> tuple[float, float]:
    return (round(clamp(center - width / 2, lo, hi), 4), round(clamp(center + width / 2, lo, hi), 4))


def interpolate_by_control(control: float, negative_value: float, neutral_value: float, positive_value: float) -> float:
    if control >= 0:
        return interpolate(control, 0, 1, neutral_value, positive_value)
    return interpolate(control, -1, 0, negative_value, neutral_value)


def interpolate_abs_control(abs_control: float, neutral_value: float, max_value: float) -> float:
    return interpolate(clamp01(abs_control), 0, 1, neutral_value, max_value)


def interpolate(x: float, x0: float, x1: float, y0: float, y1: float) -> float:
    if x1 == x0:
        return y0
    t = clamp01((x - x0) / (x1 - x0))
    return y0 + t * (y1 - y0)


def positive_trend(brightness_change: float, loudness_change: float) -> float:
    return clamp01(0.55 * max(0.0, brightness_change) + 0.45 * max(0.0, loudness_change))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(value)))


def profile_to_dict(profile: TargetMusicProfileV2) -> dict[str, Any]:
    return asdict(profile)


def analysis_to_dict(analysis: SegmentAnalysisV2) -> dict[str, Any]:
    return asdict(analysis)
