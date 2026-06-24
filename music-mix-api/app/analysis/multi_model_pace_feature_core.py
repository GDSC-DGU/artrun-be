"""
Multi-model EDM pace feature core.

This module keeps heavy model inference behind adapters and owns the small,
deterministic v1 contract used by analysis and recommendation debug:

- RunnerState -> TargetMusicProfile
- signal + MERT + optional semantic fusion
- PaceFeatureVector generation
- STABLE and TRANSITION/connector scoring
- hard gating and DIRECT/CONNECTOR route comparison
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping, Sequence


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


class RunningIntention(str, Enum):
    RECOVERY = "recovery_or_control"
    STEADY = "steady"
    PACE_UP = "pace_up"
    SPRINT = "sprint_push"


@dataclass(frozen=True)
class RunnerState:
    current_pace_sec_per_km: float
    target_pace_sec_per_km: float
    current_cadence_spm: float | None = None
    fatigue_score: float = 0.0


@dataclass(frozen=True)
class TargetMusicProfile:
    running_intention: str
    pace_gap_ratio: float
    assist_degree: float
    target_cadence_spm: float
    target_effective_pulse_range: tuple[float, float]
    target_cadence_lock_min: float
    target_pace_push_range: tuple[float, float]
    target_flow_momentum_range: tuple[float, float]
    target_transition_direction: str
    allow_connector: bool
    max_pulse_jump: float
    max_push_jump: float
    max_loudness_jump: float
    forbidden: list[str]
    debug_reason: str


@dataclass(frozen=True)
class StructureFields:
    segment_id: str
    track_id: str
    start_sec: float
    end_sec: float
    start_bar: int
    end_bar: int
    duration_bars: int
    segment_use: str
    transition_type: str = TransitionType.NONE.value
    flow_direction: str = "flat"
    target_after_transition: str | None = None
    entry_quality: float = 0.7
    exit_quality: float = 0.7
    phrase_confidence: float = 0.7
    is_contiguous_original_audio: bool = True


@dataclass(frozen=True)
class RhythmSignalFeatures:
    bpm: float
    effective_pulse_bpm: float
    pulse_relation: str
    beat_confidence: float
    downbeat_confidence: float
    beat_salience_score: float
    onset_density_score: float
    rhythm_predictability_score: float
    groove_stability_score: float
    tempogram_strength_score: float


@dataclass(frozen=True)
class TimbreEnergyFeatures:
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
class MERTScores:
    embedding_id: str | None = None
    model_version: str = "mert-v1"
    embedding_dim: int | None = None
    drive_score: float | None = None
    groove_score: float | None = None
    transition_score: float | None = None
    stability_score: float | None = None
    confidence: float | None = None


@dataclass(frozen=True)
class SemanticScores:
    enabled: bool = False
    scores: dict[str, float] = field(default_factory=dict)
    confidence: float | None = None


@dataclass(frozen=True)
class PaceFeatureVector:
    cadence_lock_support: float
    pace_push_score: float
    flow_momentum_score: float
    steady_support_score: float
    recovery_support_score: float
    sprint_support_score: float
    transition_usefulness_score: float
    target_arrival_score: float
    overpush_risk: float
    chaos_risk: float
    static_risk: float
    model_confidence: float
    signal_confidence: float
    combined_confidence: float
    fusion_weights: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class SegmentAnalysis:
    structure: StructureFields
    rhythm: RhythmSignalFeatures
    timbre: TimbreEnergyFeatures
    mert: MERTScores
    semantic: SemanticScores
    pace_vector: PaceFeatureVector


@dataclass(frozen=True)
class RecommendationRoute:
    route_type: str
    running_intention: str
    pace_gap_ratio: float
    assist_degree: float
    immediate_segment: dict[str, Any] | None
    target_segment: dict[str, Any] | None
    score_breakdown: dict[str, Any]
    top_direct_candidates: list[dict[str, Any]]
    top_connector_candidates: list[dict[str, Any]]
    rejected_candidates: list[dict[str, Any]]


MULTI_MODEL_METADATA_KEYS = (
    "segment_use",
    "transition_type",
    "flow_direction",
    "target_after_transition",
    "is_contiguous_original_audio",
    "beat_confidence",
    "downbeat_confidence",
    "effective_pulse_bpm",
    "pulse_relation",
    "rhythm_predictability_score",
    "groove_stability_score",
    "tempogram_strength_score",
    "bass_energy_score",
    "bass_modulation_score",
    "low_end_stability_score",
    "loudness_change_score",
    "spectral_brightness_score",
    "brightness_change_score",
    "static_loop_penalty",
    "chaos_penalty",
    "mert_embedding_id",
    "mert_model_version",
    "mert_embedding_dim",
    "mert_drive_score",
    "mert_groove_score",
    "mert_transition_score",
    "mert_stability_score",
    "mert_confidence",
    "semantic_scores",
    "semantic_confidence",
    "pace_feature_vector",
    "fusion_weights",
    "multi_model_analysis",
)


def build_target_music_profile(state: RunnerState) -> TargetMusicProfile:
    pace_gap_ratio = (state.current_pace_sec_per_km - state.target_pace_sec_per_km) / max(
        1e-6, state.target_pace_sec_per_km
    )
    assist_degree = clamp01(abs(pace_gap_ratio) / 0.14)
    target_cadence = state.current_cadence_spm or cadence_from_target_pace(state.target_pace_sec_per_km)
    sprint_threshold = 0.16 if state.fatigue_score >= 0.65 else 0.14

    if pace_gap_ratio <= -0.04:
        return TargetMusicProfile(
            RunningIntention.RECOVERY.value,
            pace_gap_ratio,
            assist_degree,
            target_cadence,
            (90, 124),
            0.45,
            (0.15, 0.45),
            (0.20, 0.55),
            "down_or_flat",
            True,
            18,
            0.30,
            0.25,
            ["up_transition", "sprint_push", "chaotic_section", "static_loop"],
            "runner faster than target; reduce push without losing pulse",
        )
    if pace_gap_ratio < 0.04:
        return TargetMusicProfile(
            RunningIntention.STEADY.value,
            pace_gap_ratio,
            assist_degree,
            target_cadence,
            (118, 140),
            0.60,
            (0.35, 0.65),
            (0.45, 0.72),
            "flat_or_slight_up",
            True,
            20,
            0.28,
            0.25,
            ["chaotic_section", "static_loop"],
            "runner near target; maintain groove and cadence lock",
        )
    if pace_gap_ratio < sprint_threshold:
        return TargetMusicProfile(
            RunningIntention.PACE_UP.value,
            pace_gap_ratio,
            assist_degree,
            target_cadence,
            (132, 152),
            0.65,
            (0.55, 0.82),
            (0.60, 0.85),
            "up",
            True,
            28,
            0.38,
            0.30,
            ["down_transition", "recovery_section", "static_loop", "chaotic_section"],
            "runner slower than target; controlled pace-up support",
        )
    return TargetMusicProfile(
        RunningIntention.SPRINT.value,
        pace_gap_ratio,
        assist_degree,
        target_cadence,
        (150, 176),
        0.75,
        (0.75, 1.00),
        (0.70, 1.00),
        "up_or_high_drive_flat",
        True,
        45,
        0.55,
        0.35,
        ["down_transition", "recovery_section", "low_drive", "static_loop", "chaotic_section"],
        "runner much slower than target; strong cadence/push support",
    )


def fuse_pace_feature_vector(
    *,
    structure: StructureFields,
    rhythm: RhythmSignalFeatures,
    timbre: TimbreEnergyFeatures,
    mert: MERTScores,
    semantic: SemanticScores = SemanticScores(),
) -> PaceFeatureVector:
    signal = compute_signal_scores(structure=structure, rhythm=rhythm, timbre=timbre)
    signal_conf = compute_signal_confidence(structure=structure, rhythm=rhythm, timbre=timbre)
    mert_available = all(
        v is not None for v in [mert.drive_score, mert.groove_score, mert.transition_score, mert.stability_score]
    )
    semantic_available = semantic.enabled and bool(semantic.scores)
    weights = choose_fusion_weights(
        signal_confidence=signal_conf,
        mert_confidence=mert.confidence if mert_available else None,
        semantic_confidence=semantic.confidence if semantic_available else None,
        semantic_enabled=semantic_available,
    )
    mert_scores = compute_mert_scores(mert) if mert_available else default_model_scores()
    semantic_scores = compute_semantic_scores(semantic) if semantic_available else default_model_scores()

    def blend(name: str) -> float:
        return clamp01(
            weights["signal"] * signal[name]
            + weights["mert"] * mert_scores[name]
            + weights["semantic"] * semantic_scores[name]
        )

    chaos = clamp01(
        0.50 * timbre.chaos_penalty
        + 0.25 * signal["chaos_risk"]
        + 0.15 * mert_scores["chaos_risk"]
        + 0.10 * semantic_scores["chaos_risk"]
    )
    static = clamp01(0.45 * timbre.static_loop_penalty + 0.35 * timbre.static_low_end_penalty + 0.20 * signal["static_risk"])
    model_conf = clamp01(
        (mert.confidence or 0.0) * (0.75 if mert_available else 0.0)
        + (semantic.confidence or 0.0) * (0.25 if semantic_available else 0.0)
    )
    if mert_available and not semantic_available:
        model_conf = clamp01(mert.confidence or 0.7)
    combined_conf = clamp01(
        weights["signal"] * signal_conf
        + weights["mert"] * model_conf
        + weights["semantic"] * (semantic.confidence or 0.0)
    )

    return PaceFeatureVector(
        cadence_lock_support=blend("cadence_lock_support"),
        pace_push_score=blend("pace_push_score"),
        flow_momentum_score=blend("flow_momentum_score"),
        steady_support_score=blend("steady_support_score"),
        recovery_support_score=blend("recovery_support_score"),
        sprint_support_score=blend("sprint_support_score"),
        transition_usefulness_score=blend("transition_usefulness_score"),
        target_arrival_score=blend("target_arrival_score"),
        overpush_risk=blend("overpush_risk"),
        chaos_risk=chaos,
        static_risk=static,
        model_confidence=model_conf,
        signal_confidence=signal_conf,
        combined_confidence=combined_conf,
        fusion_weights=weights,
    )


def compute_signal_scores(
    *,
    structure: StructureFields,
    rhythm: RhythmSignalFeatures,
    timbre: TimbreEnergyFeatures,
) -> dict[str, float]:
    cadence_lock = clamp01(
        0.35 * rhythm.beat_salience_score
        + 0.30 * rhythm.rhythm_predictability_score
        + 0.25 * rhythm.tempogram_strength_score
        + 0.10 * rhythm.groove_stability_score
    )
    flow = clamp01(
        0.22 * rhythm.beat_salience_score
        + 0.18 * rhythm.onset_density_score
        + 0.18 * rhythm.rhythm_predictability_score
        + 0.16 * timbre.bass_modulation_score
        + 0.14 * rhythm.groove_stability_score
        + 0.12 * positive_trend(timbre.brightness_change_score, timbre.loudness_change_score)
        - 0.20 * timbre.static_loop_penalty
        - 0.15 * timbre.chaos_penalty
    )
    transition_bonus = 0.18 if structure.segment_use == SegmentUse.TRANSITION.value else 0.0
    transition_bonus += 0.08 if structure.flow_direction == "up" else -0.06 if structure.flow_direction == "down" else 0.0
    push = clamp01(
        0.20 * cadence_lock
        + 0.18 * rhythm.beat_salience_score
        + 0.16 * rhythm.onset_density_score
        + 0.16 * timbre.bass_modulation_score
        + 0.14 * flow
        + 0.10 * transition_bonus
        + 0.06 * timbre.loudness_density_score
        - 0.15 * timbre.static_low_end_penalty
        - 0.15 * timbre.chaos_penalty
    )
    recovery = clamp01(
        0.45 * (1.0 - push)
        + 0.25 * rhythm.rhythm_predictability_score
        + 0.15 * rhythm.groove_stability_score
        + 0.15 * (1.0 - timbre.loudness_density_score)
        - 0.20 * timbre.chaos_penalty
    )
    steady = clamp01(
        0.30 * cadence_lock
        + 0.25 * rhythm.groove_stability_score
        + 0.20 * rhythm.rhythm_predictability_score
        + 0.15 * flow
        + 0.10 * (1.0 - abs(push - 0.55))
    )
    sprint = clamp01(
        0.26 * push
        + 0.24 * cadence_lock
        + 0.20 * flow
        + 0.16 * timbre.bass_modulation_score
        + 0.14 * rhythm.beat_salience_score
        - 0.20 * timbre.chaos_penalty
    )
    transition_use = clamp01(
        0.30 * flow
        + 0.24 * push
        + 0.20 * (1.0 if structure.segment_use == SegmentUse.TRANSITION.value else 0.0)
        + 0.16 * structure.entry_quality
        + 0.10 * structure.exit_quality
        - 0.15 * timbre.chaos_penalty
    )
    target_arrival = clamp01(
        0.38 * transition_use + 0.22 * rhythm.beat_salience_score + 0.20 * structure.exit_quality + 0.20 * structure.phrase_confidence
    )
    overpush = clamp01(
        0.34 * timbre.loudness_density_score
        + 0.25 * rhythm.onset_density_score
        + 0.22 * timbre.spectral_brightness_score
        + 0.19 * push
        - 0.20 * rhythm.rhythm_predictability_score
    )
    chaos = clamp01(
        timbre.chaos_penalty
        + 0.20 * max(0.0, rhythm.onset_density_score - rhythm.rhythm_predictability_score)
        + 0.12 * max(0.0, timbre.loudness_change_score - 0.5)
    )
    static = clamp01(
        0.55 * timbre.static_loop_penalty
        + 0.30 * timbre.static_low_end_penalty
        + 0.15 * max(0.0, timbre.bass_energy_score - timbre.bass_modulation_score)
    )
    return {
        "cadence_lock_support": cadence_lock,
        "pace_push_score": push,
        "flow_momentum_score": flow,
        "steady_support_score": steady,
        "recovery_support_score": recovery,
        "sprint_support_score": sprint,
        "transition_usefulness_score": transition_use,
        "target_arrival_score": target_arrival,
        "overpush_risk": overpush,
        "chaos_risk": chaos,
        "static_risk": static,
    }


def compute_mert_scores(mert: MERTScores) -> dict[str, float]:
    drive, groove, transition, stability = [
        clamp01(x or 0.5)
        for x in [mert.drive_score, mert.groove_score, mert.transition_score, mert.stability_score]
    ]
    return {
        "cadence_lock_support": clamp01(0.55 * groove + 0.45 * stability),
        "pace_push_score": clamp01(0.65 * drive + 0.35 * transition),
        "flow_momentum_score": clamp01(0.45 * drive + 0.35 * groove + 0.20 * transition),
        "steady_support_score": clamp01(0.55 * groove + 0.45 * stability),
        "recovery_support_score": clamp01(0.60 * (1.0 - drive) + 0.40 * stability),
        "sprint_support_score": clamp01(0.70 * drive + 0.30 * groove),
        "transition_usefulness_score": transition,
        "target_arrival_score": clamp01(0.55 * transition + 0.45 * drive),
        "overpush_risk": clamp01(max(0.0, drive - stability) * 0.85),
        "chaos_risk": clamp01(max(0.0, drive - groove) * 0.50),
        "static_risk": clamp01(max(0.0, stability - drive) * 0.40),
    }


def compute_semantic_scores(semantic: SemanticScores) -> dict[str, float]:
    s = semantic.scores
    pace = max(
        s.get("pace_up_driving_section", 0.0),
        s.get("sprint_push_drop", 0.0),
        s.get("build_up_to_drop_transition", 0.0) * 0.85,
    )
    steady = s.get("steady_running_groove", 0.0)
    recovery = s.get("recovery_control_section", 0.0)
    transition = s.get("build_up_to_drop_transition", 0.0)
    chaotic = s.get("chaotic_unstable_section", 0.0)
    static = s.get("static_low_drive_loop", 0.0)
    return {
        "cadence_lock_support": clamp01(0.60 * steady + 0.40 * pace),
        "pace_push_score": clamp01(pace),
        "flow_momentum_score": clamp01(max(pace, steady) * 0.8 + transition * 0.2),
        "steady_support_score": clamp01(steady),
        "recovery_support_score": clamp01(recovery),
        "sprint_support_score": clamp01(s.get("sprint_push_drop", 0.0)),
        "transition_usefulness_score": clamp01(transition),
        "target_arrival_score": clamp01(max(transition, s.get("sprint_push_drop", 0.0))),
        "overpush_risk": clamp01(s.get("sprint_push_drop", 0.0) * 0.30 + chaotic * 0.45),
        "chaos_risk": clamp01(chaotic),
        "static_risk": clamp01(static),
    }


def default_model_scores() -> dict[str, float]:
    return {
        "cadence_lock_support": 0.5,
        "pace_push_score": 0.5,
        "flow_momentum_score": 0.5,
        "steady_support_score": 0.5,
        "recovery_support_score": 0.5,
        "sprint_support_score": 0.5,
        "transition_usefulness_score": 0.5,
        "target_arrival_score": 0.5,
        "overpush_risk": 0.3,
        "chaos_risk": 0.2,
        "static_risk": 0.2,
    }


def choose_fusion_weights(
    *,
    signal_confidence: float,
    mert_confidence: float | None,
    semantic_confidence: float | None,
    semantic_enabled: bool,
) -> dict[str, float]:
    if mert_confidence is None:
        return {"signal": 1.0, "mert": 0.0, "semantic": 0.0}
    if semantic_enabled:
        raw = {
            "signal": 0.45 * max(0.25, signal_confidence),
            "mert": 0.40 * max(0.25, mert_confidence),
            "semantic": 0.15 * max(0.20, semantic_confidence or 0.0),
        }
    else:
        raw = {
            "signal": 0.52 * max(0.25, signal_confidence),
            "mert": 0.48 * max(0.25, mert_confidence),
            "semantic": 0.0,
        }
    total = sum(raw.values()) or 1.0
    return {k: round(v / total, 4) for k, v in raw.items()}


def compute_signal_confidence(
    *,
    structure: StructureFields,
    rhythm: RhythmSignalFeatures,
    timbre: TimbreEnergyFeatures,
) -> float:
    base = (
        0.25 * rhythm.beat_confidence
        + 0.22 * rhythm.downbeat_confidence
        + 0.20 * structure.phrase_confidence
        + 0.13 * structure.entry_quality
        + 0.10 * structure.exit_quality
        + 0.10 * (1.0 - timbre.chaos_penalty)
    )
    if not structure.is_contiguous_original_audio:
        base -= 0.45
    if structure.segment_use == SegmentUse.REJECT.value:
        base -= 0.35
    return clamp01(base)


def is_recommendable_segment(analysis: SegmentAnalysis) -> tuple[bool, str | None]:
    s, p, r = analysis.structure, analysis.pace_vector, analysis.rhythm
    if not s.is_contiguous_original_audio:
        return False, "not_contiguous_original_audio"
    if s.segment_use == SegmentUse.REJECT.value:
        return False, "segment_use_REJECT"
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
    return True, None


def stable_match_score(
    *,
    analysis: SegmentAnalysis,
    target: TargetMusicProfile,
    recent_segment_ids: Sequence[str] = (),
) -> tuple[float, dict[str, Any]]:
    ok, reason = is_recommendable_segment(analysis)
    if not ok:
        return 0.0, {"reject_reason": reason}
    s, r, p = analysis.structure, analysis.rhythm, analysis.pace_vector
    if s.segment_use != SegmentUse.STABLE.value:
        return 0.0, {"reject_reason": "not_STABLE_main_candidate"}
    if s.segment_id in set(recent_segment_ids):
        return 0.0, {"reject_reason": "recent_segment_hard_exclude"}
    pulse = range_match(r.effective_pulse_bpm, target.target_effective_pulse_range)
    cadence = threshold_match(p.cadence_lock_support, target.target_cadence_lock_min)
    push = range_match(p.pace_push_score, target.target_pace_push_range)
    flow = range_match(p.flow_momentum_score, target.target_flow_momentum_range)
    rhythm = clamp01(0.50 * r.rhythm_predictability_score + 0.50 * r.groove_stability_score)
    semantic = intention_support_score(p, target.running_intention)
    quality = clamp01((s.entry_quality + s.exit_quality + s.phrase_confidence) / 3.0)
    score = clamp01(
        0.18 * pulse
        + 0.15 * cadence
        + 0.14 * push
        + 0.13 * flow
        + 0.12 * rhythm
        + 0.10 * semantic
        + 0.08 * quality
        + 0.05 * p.model_confidence
        - 0.10 * p.overpush_risk
        - 0.10 * p.chaos_risk
        - 0.08 * p.static_risk
    )
    return score, {
        "effective_pulse_match": round(pulse, 4),
        "cadence_lock_match": round(cadence, 4),
        "pace_push_match": round(push, 4),
        "flow_momentum_match": round(flow, 4),
        "rhythm_stability_match": round(rhythm, 4),
        "semantic_intention_match": round(semantic, 4),
        "entry_exit_quality": round(quality, 4),
        "model_confidence": round(p.model_confidence, 4),
        "overpush_risk": round(p.overpush_risk, 4),
        "chaos_risk": round(p.chaos_risk, 4),
        "static_risk": round(p.static_risk, 4),
        "final_score": round(score, 4),
    }


def connector_match_score(*, analysis: SegmentAnalysis, target: TargetMusicProfile) -> tuple[float, dict[str, Any]]:
    ok, reason = is_recommendable_segment(analysis)
    if not ok:
        return 0.0, {"reject_reason": reason}
    s, p = analysis.structure, analysis.pace_vector
    if s.segment_use not in {SegmentUse.TRANSITION.value, SegmentUse.ENTRY_ONLY.value, SegmentUse.EXIT_ONLY.value}:
        return 0.0, {"reject_reason": "not_connector_candidate"}
    if target.running_intention in {RunningIntention.PACE_UP.value, RunningIntention.SPRINT.value} and s.flow_direction == "down":
        return 0.0, {"reject_reason": "down_transition_blocked_for_upward_intention"}
    if target.running_intention == RunningIntention.RECOVERY.value and s.flow_direction == "up":
        return 0.0, {"reject_reason": "up_transition_blocked_for_recovery"}
    direction = transition_direction_match(s.flow_direction, target.target_transition_direction)
    transition_use, arrival = p.transition_usefulness_score, p.target_arrival_score
    flow = range_match(p.flow_momentum_score, target.target_flow_momentum_range)
    push = range_match(p.pace_push_score, target.target_pace_push_range)
    quality = clamp01((s.entry_quality + s.exit_quality + s.phrase_confidence) / 3.0)
    score = clamp01(
        0.20 * direction
        + 0.18 * transition_use
        + 0.16 * arrival
        + 0.14 * flow
        + 0.12 * push
        + 0.10 * quality
        + 0.05 * p.model_confidence
        - 0.10 * p.chaos_risk
        - 0.08 * p.overpush_risk
    )
    return score, {
        "transition_direction_match": round(direction, 4),
        "transition_usefulness_score": round(transition_use, 4),
        "target_arrival_score": round(arrival, 4),
        "flow_momentum_match": round(flow, 4),
        "pace_push_match": round(push, 4),
        "entry_exit_quality": round(quality, 4),
        "model_confidence": round(p.model_confidence, 4),
        "chaos_risk": round(p.chaos_risk, 4),
        "overpush_risk": round(p.overpush_risk, 4),
        "final_score": round(score, 4),
    }


def recommend_route(
    *,
    analyses: Sequence[SegmentAnalysis],
    target: TargetMusicProfile,
    current_segment_id: str | None = None,
    recent_segment_ids: Sequence[str] = (),
    top_n: int = 5,
) -> RecommendationRoute:
    recent = set(recent_segment_ids)
    if current_segment_id:
        recent.add(current_segment_id)

    direct_rows: list[dict[str, Any]] = []
    connector_rows: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []

    for analysis in analyses:
        segment_id = analysis.structure.segment_id
        if segment_id == current_segment_id:
            rejected.append(candidate_summary(analysis, reject_reason="current_segment_hard_exclude"))
            continue
        if segment_id in set(recent_segment_ids):
            rejected.append(candidate_summary(analysis, reject_reason="recent_segment_hard_exclude"))
            continue

        stable_score, stable_breakdown = stable_match_score(
            analysis=analysis,
            target=target,
            recent_segment_ids=recent,
        )
        connector_score, connector_breakdown = connector_match_score(analysis=analysis, target=target)

        if stable_score > 0:
            direct_rows.append(candidate_summary(analysis, stable_score, stable_breakdown))
        elif stable_breakdown.get("reject_reason"):
            rejected.append(candidate_summary(analysis, reject_reason=stable_breakdown["reject_reason"]))

        if connector_score > 0:
            connector_rows.append(candidate_summary(analysis, connector_score, connector_breakdown))
        elif connector_breakdown.get("reject_reason") and connector_breakdown["reject_reason"] not in {
            "not_connector_candidate"
        }:
            rejected.append(candidate_summary(analysis, reject_reason=connector_breakdown["reject_reason"]))

    direct_rows = sorted(direct_rows, key=lambda row: row["score"], reverse=True)
    connector_rows = sorted(connector_rows, key=lambda row: row["score"], reverse=True)

    best_direct = direct_rows[0] if direct_rows else None
    best_connector = connector_rows[0] if connector_rows else None
    best_target = direct_rows[0] if direct_rows else None

    route_type = "NONE"
    immediate = None
    target_segment = None
    score_breakdown: dict[str, Any] = {}

    if best_direct:
        route_type = "DIRECT"
        immediate = best_direct
        target_segment = best_direct
        score_breakdown = {"direct_score": round(best_direct["score"], 4), "route_score": round(best_direct["score"], 4)}

    if target.allow_connector and best_connector and best_target:
        route_score = clamp01(0.58 * best_connector["score"] + 0.42 * best_target["score"])
        direct_score = best_direct["score"] if best_direct else 0.0
        direct_jump_large = direct_score < 0.54 or best_connector["score"] > direct_score + 0.05
        if direct_jump_large and route_score >= max(0.45, direct_score - 0.02):
            route_type = "CONNECTOR"
            immediate = best_connector
            target_segment = best_target
            score_breakdown = {
                "connector_score": round(best_connector["score"], 4),
                "target_score": round(best_target["score"], 4),
                "route_score": round(route_score, 4),
                "direct_score": round(direct_score, 4),
            }

    return RecommendationRoute(
        route_type=route_type,
        running_intention=target.running_intention,
        pace_gap_ratio=round(target.pace_gap_ratio, 4),
        assist_degree=round(target.assist_degree, 4),
        immediate_segment=route_segment_payload(immediate),
        target_segment=route_segment_payload(target_segment),
        score_breakdown=score_breakdown,
        top_direct_candidates=[route_segment_payload(row) for row in direct_rows[:top_n] if route_segment_payload(row)],
        top_connector_candidates=[route_segment_payload(row) for row in connector_rows[:top_n] if route_segment_payload(row)],
        rejected_candidates=dedupe_rejections(rejected)[:top_n],
    )


def candidate_summary(
    analysis: SegmentAnalysis,
    score: float = 0.0,
    breakdown: Mapping[str, Any] | None = None,
    *,
    reject_reason: str | None = None,
) -> dict[str, Any]:
    payload = {
        "segment_id": analysis.structure.segment_id,
        "track_id": analysis.structure.track_id,
        "segment_use": analysis.structure.segment_use,
        "transition_type": analysis.structure.transition_type,
        "flow_direction": analysis.structure.flow_direction,
        "score": round(score, 4),
        "pace_feature_vector": pace_vector_to_dict(analysis.pace_vector),
        "fusion_weights": dict(analysis.pace_vector.fusion_weights),
    }
    if breakdown:
        payload["score_breakdown"] = dict(breakdown)
    if reject_reason:
        payload["reject_reason"] = reject_reason
    return payload


def route_segment_payload(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "segment_id": row["segment_id"],
        "track_id": row["track_id"],
        "segment_use": row["segment_use"],
        "transition_type": row["transition_type"],
        "flow_direction": row["flow_direction"],
        "score": row["score"],
        "score_breakdown": row.get("score_breakdown", {}),
        "pace_feature_vector": row.get("pace_feature_vector", {}),
        "fusion_weights": row.get("fusion_weights", {}),
        "reject_reason": row.get("reject_reason"),
    }


def dedupe_rejections(rows: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for row in rows:
        key = (str(row.get("segment_id")), str(row.get("reject_reason")))
        if key in seen:
            continue
        seen.add(key)
        payload = route_segment_payload(row)
        if payload:
            out.append(payload)
    return out


def intention_support_score(p: PaceFeatureVector, intention: str) -> float:
    if intention == RunningIntention.RECOVERY.value:
        return p.recovery_support_score
    if intention == RunningIntention.STEADY.value:
        return p.steady_support_score
    if intention == RunningIntention.PACE_UP.value:
        return clamp01(0.55 * p.pace_push_score + 0.45 * p.flow_momentum_score)
    if intention == RunningIntention.SPRINT.value:
        return p.sprint_support_score
    return 0.5


def transition_direction_match(flow_direction: str, target_direction: str) -> float:
    if target_direction == "up":
        return 1.0 if flow_direction == "up" else 0.35
    if target_direction == "down_or_flat":
        return 1.0 if flow_direction in {"down", "flat"} else 0.25
    if target_direction == "flat_or_slight_up":
        return 1.0 if flow_direction in {"flat", "up"} else 0.45
    if target_direction == "up_or_high_drive_flat":
        return 1.0 if flow_direction == "up" else 0.70 if flow_direction == "flat" else 0.25
    return 0.5


def range_match(value: float, target_range: tuple[float, float]) -> float:
    lo, hi = target_range
    if lo <= value <= hi:
        return 1.0
    margin = max(0.05, (hi - lo) * 0.75)
    return clamp01(1.0 - ((lo - value) if value < lo else (value - hi)) / margin)


def threshold_match(value: float, minimum: float) -> float:
    return 1.0 if value >= minimum else clamp01(value / max(0.05, minimum))


def positive_trend(brightness_change: float, loudness_change: float) -> float:
    return clamp01(0.55 * max(0.0, brightness_change) + 0.45 * max(0.0, loudness_change))


def cadence_from_target_pace(target_pace_sec_per_km: float) -> float:
    m = target_pace_sec_per_km / 60.0
    return 174 if m <= 4.5 else 168 if m <= 5.5 else 162 if m <= 6.5 else 156


def clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def analysis_to_dict(analysis: SegmentAnalysis) -> dict[str, Any]:
    return asdict(analysis)


def target_profile_to_dict(profile: TargetMusicProfile) -> dict[str, Any]:
    data = asdict(profile)
    data["pace_gap_ratio"] = round(profile.pace_gap_ratio, 4)
    data["assist_degree"] = round(profile.assist_degree, 4)
    return data


def pace_vector_to_dict(vector: PaceFeatureVector) -> dict[str, Any]:
    data = asdict(vector)
    for key, value in list(data.items()):
        if isinstance(value, float):
            data[key] = round(value, 4)
    return data


def route_to_dict(route: RecommendationRoute) -> dict[str, Any]:
    return asdict(route)
