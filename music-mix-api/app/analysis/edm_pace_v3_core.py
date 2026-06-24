"""
edm_pace_v3_core.py

Control-window based EDM running music analyzer/recommender core.

Design intent
-------------
This module rewrites the v2 speed-degree idea into a v3 runtime model:

- Do not react to instant GPS speed changes.
- Smooth running state over a control window, default 30s.
- Use speed zones + deadband + hysteresis + minimum music hold.
- Recommend 16-bar stable blocks or 8-bar drive-preserving connectors.
- Block intro-like, pulse-drop, low-drive transitions during runtime.
- Apply controlled diversity only among high-quality candidates.

Research basis for defaults
---------------------------
The numeric defaults are not claimed to be universal constants. They are
research-informed, conservative initial parameters intended for product testing:

- GPS pace can be noisy, so recommendations use a 30s control window rather
  than instant speed samples.
- Exercise-music literature supports synchronous / rhythmic / preferred music
  and moderately fast tempos as useful for exercise, but also shows individual
  differences; therefore, this recommender exposes tunable thresholds and debug.
- Rhythmic auditory cueing can tighten gait control; therefore, cadence lock,
  pulse continuity, and beat salience are first-class features.
- EDM phrasing commonly makes 8/16/32-bar blocks natural units; therefore,
  route changes are planned around phrase exits.

Open-source integration
-----------------------
The core is dependency-light and testable with the Python standard library.
The optional analyzer companion module uses open-source libraries when present:
librosa, numpy, soundfile, scipy, Essentia, madmom, All-In-One, MERT, MuQ-MuLan.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from enum import Enum
from math import floor
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping, Sequence


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    if abs(denominator) < 1e-9:
        return default
    return numerator / denominator


def inverse_distance_score(value: float, target: float, tolerance: float) -> float:
    """Return 1.0 at target, 0.0 at target +/- tolerance or farther."""
    if tolerance <= 0:
        return 1.0 if value == target else 0.0
    return clamp(1.0 - abs(value - target) / tolerance, 0.0, 1.0)


def weighted_average(values: Sequence[float], weights: Sequence[float]) -> float:
    if not values:
        return 0.0
    total = sum(weights)
    if total <= 0:
        return mean(values)
    return sum(v * w for v, w in zip(values, weights)) / total


def degree_bin(value: float, bin_size: float = 0.10) -> str:
    v = clamp(value, 0.0, 0.999999)
    start = floor(v / bin_size) * bin_size
    end = start + bin_size
    return f"{start:.2f}-{end:.2f}"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SegmentUse(str, Enum):
    STABLE = "STABLE"
    DRIVE_CONNECTOR = "DRIVE_CONNECTOR"
    EXIT_CONNECTOR = "EXIT_CONNECTOR"
    ENTRY_ONLY = "ENTRY_ONLY"
    REJECT = "REJECT"


class RouteType(str, Enum):
    HOLD = "HOLD"
    DIRECT = "DIRECT"
    CONNECTOR = "CONNECTOR"
    FALLBACK = "FALLBACK"
    NO_CANDIDATE = "NO_CANDIDATE"


class SpeedZone(str, Enum):
    DEEP_CONTROL = "deep_control"
    CONTROL = "control"
    LIGHT_CONTROL = "light_control"
    STEADY_DEADBAND = "steady_deadband"
    LIGHT_PUSH = "light_push"
    PUSH = "push"
    STRONG_PUSH = "strong_push"
    RHYTHM_REBUILD = "rhythm_rebuild"


class RuntimeContext(str, Enum):
    INITIAL_ENTRY = "initial_entry"
    RUNTIME = "runtime"
    MANUAL_REVIEW = "manual_review"


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class V3Config:
    active_tuning_profile: str = "default"
    speed_zone_boundaries: dict[str, float] = field(default_factory=lambda: {
        "deep_control_max": -0.25,
        "control_max": -0.12,
        "light_control_max": -0.05,
        "steady_min": -0.05,
        "steady_max": 0.05,
        "light_push_max": 0.12,
        "push_max": 0.25,
        "strong_push_max": 0.35,
    })
    preferred_degree_ranges: dict[str, tuple[float, float]] = field(default_factory=lambda: {
        SpeedZone.DEEP_CONTROL.value: (0.15, 0.40),
        SpeedZone.CONTROL.value: (0.15, 0.40),
        SpeedZone.LIGHT_CONTROL.value: (0.35, 0.50),
        SpeedZone.STEADY_DEADBAND.value: (0.45, 0.60),
        SpeedZone.LIGHT_PUSH.value: (0.58, 0.72),
        SpeedZone.PUSH.value: (0.65, 0.80),
        SpeedZone.STRONG_PUSH.value: (0.75, 0.90),
        SpeedZone.RHYTHM_REBUILD.value: (0.75, 0.90),
    })
    fake_groove_thresholds: dict[str, float] = field(default_factory=lambda: {
        "tempo_feel_drop_block": 0.35,
        "pulse_density_drop_block": 0.35,
        "drive_cliff_block": 0.35,
        "half_time_shift_block": 0.40,
        "internal_degree_range_block": 0.28,
        "effective_pulse_stability_min": 0.55,
        "min_internal_degree_margin": 0.25,
    })
    score_weights: dict[str, float] = field(default_factory=lambda: {
        "music_speed_degree_match": 0.08,
        "speed_zone_contrast_score": 0.16,
        "current_to_candidate_smoothness": 0.13,
        "degree_step_smoothness": 0.10,
        "pulse_continuity_score": 0.11,
        "drive_preservation_score": 0.10,
        "cadence_lock_support": 0.08,
        "flow_momentum_score": 0.07,
        "block_stability_score": 0.07,
        "jump_penalty": 0.12,
        "pulse_drop_penalty": 0.12,
        "intro_like_penalty": 0.08,
        "overpush_penalty": 0.06,
        "pace_assist_score": 0.34,
        "asc_cue_fit": 0.18,
        "asc_quality_score": 0.16,
        "asc_risk_safety": 0.12,
    })
    pace_assist_v3_4: dict[str, float] = field(default_factory=lambda: {
        "asc_strength_min": 0.65,
        "asc_stability_min": 0.70,
        "pulse_clarity_min": 0.35,
        "rhythm_predictability_min": 0.10,
        "pulse_dropout_max": 0.25,
        "half_time_risk_max": 0.25,
        "fake_groove_risk_max": 0.35,
        "min_lift_from_current_music_spm": 2.0,
        "asc_tolerance_spm": 3.0,
        "max_cadence_overcue_pct": 0.07,
        "ai_negative_semantic_risk_max": 0.40,
        "fast_min_asc_floor_from_current_music": -1.0,
    })
    latency_policy: dict[str, dict[str, float]] = field(default_factory=lambda: {
        "pace_up_responsive": {
            "confirmation_sec": 3.0,
            "min_hold_sec": 3.0,
            "boundary_max_wait_sec": 4.0,
            "crossfade_sec": 2.0,
            "max_change_latency_sec": 10.0,
            "allowed_boundary_bars": 4.0,
        },
        "demo_fast_switching": {
            "confirmation_sec": 0.0,
            "min_hold_sec": 0.0,
            "boundary_max_wait_sec": 1.0,
            "crossfade_sec": 1.5,
            "max_change_latency_sec": 3.0,
            "allowed_boundary_bars": 1.0,
        },
    })

    # Running sensor smoothing. 30s aligns with GPS noise reduction and roughly
    # one 16-bar EDM block at 128 BPM (~30s).
    control_window_sec: float = 30.0
    previous_control_window_sec: float = 30.0
    short_trend_window_sec: float = 10.0

    # Zone/deadband. +/-5% avoids reacting to minor GPS/pace fluctuation.
    steady_deadband_ratio: float = 0.05
    zone_enter_buffer_ratio: float = 0.02
    zone_exit_buffer_ratio: float = 0.02
    zone_change_confirm_sec: float = 25.0
    zone_return_confirm_sec: float = 18.0

    # Music block constraints.
    default_block_bars: int = 16
    connector_block_bars: int = 8
    stable_hold_bars_min: int = 16
    min_hold_sec: float = 30.0
    target_degree_change_threshold: float = 0.08

    # Target profile transform.
    # Divisor is slightly tighter than v2 (0.35) because v3 already smooths speed.
    music_pace_control_divisor: float = 0.35
    trend_compensation: float = 0.5
    target_degree_center: float = 0.50
    target_degree_span: float = 0.35
    target_degree_min: float = 0.15
    target_degree_max: float = 0.85

    # Direct change and connector gating.
    max_direct_degree_jump_small: float = 0.14
    max_direct_degree_jump_large: float = 0.26
    connector_intro_like_block: float = 0.45
    connector_pulse_drop_block: float = 0.35
    connector_pulse_continuity_min: float = 0.60
    connector_drive_preservation_min: float = 0.55
    connector_cadence_lock_continuity_min: float = 0.55
    connector_target_drop_margin: float = 0.22

    # Diversity / coverage.
    degree_bin_size: float = 0.10
    min_stable_candidates_per_bin: int = 5
    min_connector_candidates_per_bin: int = 2
    ideal_stable_candidates_per_bin: int = 10
    ideal_connector_candidates_per_bin: int = 4
    min_unique_tracks_per_bin: int = 2
    ideal_unique_tracks_per_bin: int = 3
    controlled_diversity_score_margin: float = 0.05
    recent_track_cooldown_count: int = 4
    recent_track_penalty: float = 0.08
    same_degree_bin_penalty: float = 0.04
    same_section_label_penalty: float = 0.03
    session_play_count_penalty: float = 0.025
    session_play_count_penalty_max: float = 0.15

    # Confidence filters.
    min_valid_block_confidence: float = 0.45
    min_phrase_confidence: float = 0.50
    max_chaos_risk: float = 0.70
    max_static_risk: float = 0.70


# ---------------------------------------------------------------------------
# Running state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RunningSample:
    timestamp_sec: float
    speed_kmh: float
    cadence_spm: float | None = None


@dataclass(frozen=True)
class RunnerControlState:
    target_speed_kmh: float
    now_sec: float
    current_speed_kmh: float
    control_speed_kmh: float
    previous_control_speed_kmh: float
    short_trend_speed_kmh: float
    speed_gap_ratio: float
    speed_trend_ratio: float
    short_trend_ratio: float
    control_speed_variance: float
    control_speed_stability: float
    candidate_speed_zone: str
    active_speed_zone: str
    zone_stable_duration_sec: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ZoneMemory:
    active_speed_zone: str = SpeedZone.STEADY_DEADBAND.value
    candidate_speed_zone: str = SpeedZone.STEADY_DEADBAND.value
    candidate_since_sec: float = 0.0
    last_zone_change_sec: float = 0.0


# ---------------------------------------------------------------------------
# Music segment profiles
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SegmentPaceProfile:
    music_speed_degree: float
    start_degree: float
    mid_degree: float
    end_degree: float
    degree_slope: float
    degree_stability: float
    curve_shape: str = "unknown"


@dataclass(frozen=True)
class PulseProfile:
    effective_pulse_bpm: float
    kick_presence_score: float
    pulse_continuity_score: float
    beat_salience_score: float
    beat_salience_continuity: float
    cadence_lock_support: float
    cadence_lock_continuity: float
    rhythm_predictability_score: float


@dataclass(frozen=True)
class DriveProfile:
    entry_drive_score: float
    mid_drive_score: float
    exit_drive_score: float
    drive_preservation_score: float
    flow_momentum_score: float
    pace_push_score: float
    bass_modulation_score: float


@dataclass(frozen=True)
class TransitionProfile:
    transition_slope: float
    transition_target_degree: float
    transition_arrival_confidence: float
    runtime_connector_allowed: bool
    drive_connector_score: float
    transition_type: str = "NONE"


@dataclass(frozen=True)
class RiskProfile:
    intro_like_score: float
    pulse_drop_score: float
    dropout_risk: float
    breakdown_like_score: float
    static_risk: float
    chaos_risk: float
    overpush_risk: float


@dataclass(frozen=True)
class PaceAssistV34Profile:
    primary_ASC_spm: float
    ASC_strength: float
    ASC_stability: float
    pulse_clarity: float
    rhythm_predictability: float
    pulse_dropout_risk: float
    half_time_shift_risk: float
    fake_groove_risk: float
    pace_assist_score: float
    ai_semantic_scores: Mapping[str, float] = field(default_factory=dict)
    user_response_effect: float = 0.50


@dataclass(frozen=True)
class BlockProfile:
    preferred_block_bars: int
    min_hold_bars: int
    min_hold_sec: float
    stable_duration_sec: float
    valid_runtime_block: bool
    phrase_confidence: float = 0.75


@dataclass(frozen=True)
class SegmentRecord:
    segment_id: str
    track_id: str
    track_title: str
    start_sec: float
    end_sec: float
    start_bar: int
    end_bar: int
    segment_use: str
    section_label: str
    pace: SegmentPaceProfile
    pulse: PulseProfile
    drive: DriveProfile
    transition: TransitionProfile
    risk: RiskProfile
    block: BlockProfile
    pace_assist: PaceAssistV34Profile = field(default_factory=lambda: PaceAssistV34Profile(
        primary_ASC_spm=0.0,
        ASC_strength=0.0,
        ASC_stability=0.0,
        pulse_clarity=0.0,
        rhythm_predictability=0.0,
        pulse_dropout_risk=1.0,
        half_time_shift_risk=1.0,
        fake_groove_risk=1.0,
        pace_assist_score=0.0,
    ))
    is_contiguous_original_audio: bool = True
    combined_confidence: float = 0.75
    manual_disabled: bool = False
    license_info: dict[str, str] = field(default_factory=dict)

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)

    @property
    def duration_bars(self) -> int:
        return max(0, self.end_bar - self.start_bar)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Target profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetMusicBlockProfile:
    speed_zone: str
    zone_stable_duration_sec: float
    speed_gap_ratio: float
    speed_trend_ratio: float
    music_pace_control: float
    target_music_speed_degree: float
    previous_target_music_speed_degree: float | None
    target_degree_delta: float
    target_transition_slope: float
    target_transition_direction: str
    recommended_block_bars: int
    min_hold_bars: int
    allow_connector: bool
    max_direct_degree_jump: float
    should_change_music: bool
    hold_reason: str | None
    change_reason: str | None
    debug_intention_label: str
    current_runner_cadence_spm: float | None = None
    current_music_ASC_spm: float | None = None
    desired_next_ASC_spm: float | None = None
    pace_lift_state: str | None = None
    latency_route: str = "HOLD"
    max_change_latency_sec: float | None = None
    estimated_change_latency_sec: float | None = None
    confirmation_elapsed_sec: float | None = None
    min_hold_remaining_sec: float | None = None
    boundary_wait_sec: float | None = None
    crossfade_sec: float | None = None
    preselected_segment_id: str | None = None
    change_intent_reason: str | None = None
    change_blocked_reason: str | None = None
    forced_crossfade_used: bool = False

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SessionHistory:
    recent_segment_ids: tuple[str, ...] = ()
    recent_track_ids: tuple[str, ...] = ()
    recent_degree_bins: tuple[str, ...] = ()
    recent_section_labels: tuple[str, ...] = ()
    last_change_sec: float = 0.0
    session_play_counts: Mapping[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class CandidateScore:
    segment_id: str
    track_id: str
    segment_use: str
    base_score: float
    final_score: float
    score_breakdown: dict[str, float]
    reject_reasons: tuple[str, ...] = ()
    diversity_penalties: dict[str, float] = field(default_factory=dict)
    why_selected_ko: tuple[str, ...] = ()
    why_rejected_ko: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CoverageBin:
    degree_bin: str
    stable_count: int
    drive_connector_count: int
    exit_connector_count: int
    entry_only_count: int
    reject_count: int
    unique_track_count: int
    warnings: tuple[str, ...]
    explanation_ko: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RecommendationResult:
    route_type: str
    immediate_segment: SegmentRecord | None
    target_segment: SegmentRecord | None
    target_profile: TargetMusicBlockProfile
    hold_reason: str | None
    change_reason: str | None
    top_candidates: tuple[CandidateScore, ...]
    candidate_pool_warning: tuple[str, ...]
    debug: dict[str, Any]

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        return data


# ---------------------------------------------------------------------------
# Running control functions
# ---------------------------------------------------------------------------


def classify_speed_zone(speed_gap_ratio: float, config: V3Config = V3Config()) -> str:
    b = config.speed_zone_boundaries
    if speed_gap_ratio <= b.get("deep_control_max", -0.25):
        return SpeedZone.DEEP_CONTROL.value
    if speed_gap_ratio <= b.get("control_max", -0.12):
        return SpeedZone.CONTROL.value
    if speed_gap_ratio <= b.get("light_control_max", -0.05):
        return SpeedZone.LIGHT_CONTROL.value
    steady_min = b.get("steady_min", -0.05)
    steady_max = b.get("steady_max", 0.05)
    if steady_min <= speed_gap_ratio < steady_max:
        return SpeedZone.STEADY_DEADBAND.value
    if speed_gap_ratio < b.get("light_push_max", 0.12):
        return SpeedZone.LIGHT_PUSH.value
    if speed_gap_ratio < b.get("push_max", 0.25):
        return SpeedZone.PUSH.value
    if speed_gap_ratio < b.get("strong_push_max", 0.35):
        return SpeedZone.STRONG_PUSH.value
    return SpeedZone.RHYTHM_REBUILD.value


def _samples_in_window(
    samples: Sequence[RunningSample],
    now_sec: float,
    start_offset_sec: float,
    end_offset_sec: float,
) -> list[RunningSample]:
    start = now_sec - start_offset_sec
    end = now_sec - end_offset_sec
    return [s for s in samples if start <= s.timestamp_sec <= end]


def _linear_weighted_speed(window_samples: Sequence[RunningSample], now_sec: float) -> float:
    if not window_samples:
        return 0.0
    speeds = [max(0.0, s.speed_kmh) for s in window_samples]
    # More recent samples get slightly higher weight, but not too aggressively.
    ages = [max(0.0, now_sec - s.timestamp_sec) for s in window_samples]
    max_age = max(ages) if ages else 1.0
    weights = [1.0 + (1.0 - safe_div(age, max_age, 0.0)) for age in ages]
    return weighted_average(speeds, weights)


def update_zone_memory(
    candidate_zone: str,
    now_sec: float,
    memory: ZoneMemory | None,
    config: V3Config = V3Config(),
) -> ZoneMemory:
    if memory is None:
        return ZoneMemory(
            active_speed_zone=candidate_zone,
            candidate_speed_zone=candidate_zone,
            candidate_since_sec=now_sec,
            last_zone_change_sec=now_sec,
        )

    if candidate_zone == memory.active_speed_zone:
        return ZoneMemory(
            active_speed_zone=memory.active_speed_zone,
            candidate_speed_zone=candidate_zone,
            candidate_since_sec=now_sec,
            last_zone_change_sec=memory.last_zone_change_sec,
        )

    # New candidate begins.
    if candidate_zone != memory.candidate_speed_zone:
        return ZoneMemory(
            active_speed_zone=memory.active_speed_zone,
            candidate_speed_zone=candidate_zone,
            candidate_since_sec=now_sec,
            last_zone_change_sec=memory.last_zone_change_sec,
        )

    # Candidate has persisted long enough.
    elapsed = now_sec - memory.candidate_since_sec
    required = (
        config.zone_return_confirm_sec
        if candidate_zone == SpeedZone.STEADY_DEADBAND.value
        else config.zone_change_confirm_sec
    )
    if elapsed >= required:
        return ZoneMemory(
            active_speed_zone=candidate_zone,
            candidate_speed_zone=candidate_zone,
            candidate_since_sec=now_sec,
            last_zone_change_sec=now_sec,
        )

    return memory


def build_control_state(
    samples: Sequence[RunningSample],
    target_speed_kmh: float,
    now_sec: float | None = None,
    memory: ZoneMemory | None = None,
    config: V3Config = V3Config(),
) -> tuple[RunnerControlState, ZoneMemory]:
    if not samples:
        raise ValueError("At least one running sample is required")
    if target_speed_kmh <= 0:
        raise ValueError("target_speed_kmh must be positive")
    samples = sorted(samples, key=lambda s: s.timestamp_sec)
    now = float(now_sec if now_sec is not None else samples[-1].timestamp_sec)

    current_speed = samples[-1].speed_kmh
    current_window = _samples_in_window(samples, now, config.control_window_sec, 0.0)
    previous_window = _samples_in_window(
        samples,
        now,
        config.control_window_sec + config.previous_control_window_sec,
        config.control_window_sec,
    )
    short_window = _samples_in_window(samples, now, config.short_trend_window_sec, 0.0)

    control_speed = _linear_weighted_speed(current_window or [samples[-1]], now)
    previous_control_speed = _linear_weighted_speed(previous_window, now) if previous_window else control_speed
    short_trend_speed = _linear_weighted_speed(short_window or current_window or [samples[-1]], now)

    speed_gap_ratio = (target_speed_kmh - control_speed) / target_speed_kmh
    speed_trend_ratio = (control_speed - previous_control_speed) / target_speed_kmh
    short_trend_ratio = (short_trend_speed - control_speed) / target_speed_kmh
    speeds = [s.speed_kmh for s in current_window] or [current_speed]
    variance = pstdev(speeds) if len(speeds) >= 2 else 0.0
    # 1.5 km/h stdev in a 30s window is considered unstable for this product.
    stability = clamp(1.0 - variance / 1.5, 0.0, 1.0)
    candidate_zone = classify_speed_zone(speed_gap_ratio, config)
    new_memory = update_zone_memory(candidate_zone, now, memory, config)
    zone_stable_duration = now - new_memory.candidate_since_sec
    if new_memory.active_speed_zone == candidate_zone:
        zone_stable_duration = max(0.0, now - new_memory.last_zone_change_sec)

    state = RunnerControlState(
        target_speed_kmh=target_speed_kmh,
        now_sec=now,
        current_speed_kmh=current_speed,
        control_speed_kmh=control_speed,
        previous_control_speed_kmh=previous_control_speed,
        short_trend_speed_kmh=short_trend_speed,
        speed_gap_ratio=speed_gap_ratio,
        speed_trend_ratio=speed_trend_ratio,
        short_trend_ratio=short_trend_ratio,
        control_speed_variance=variance,
        control_speed_stability=stability,
        candidate_speed_zone=candidate_zone,
        active_speed_zone=new_memory.active_speed_zone,
        zone_stable_duration_sec=zone_stable_duration,
    )
    return state, new_memory


def debug_intention_label_for_zone(zone: str) -> str:
    return {
        SpeedZone.DEEP_CONTROL.value: "deep_recovery",
        SpeedZone.CONTROL.value: "recovery_control",
        SpeedZone.LIGHT_CONTROL.value: "light_control",
        SpeedZone.STEADY_DEADBAND.value: "steady",
        SpeedZone.LIGHT_PUSH.value: "controlled_push",
        SpeedZone.PUSH.value: "push",
        SpeedZone.STRONG_PUSH.value: "strong_push",
        SpeedZone.RHYTHM_REBUILD.value: "rhythm_rebuild",
    }.get(zone, "unknown")


def build_target_profile(
    state: RunnerControlState,
    previous_target_music_speed_degree: float | None = None,
    elapsed_since_last_change_sec: float = 999.0,
    near_phrase_boundary: bool = True,
    config: V3Config = V3Config(),
) -> TargetMusicBlockProfile:
    control = clamp(
        (state.speed_gap_ratio - config.trend_compensation * state.speed_trend_ratio)
        / config.music_pace_control_divisor,
        -1.0,
        1.0,
    )
    target_degree = clamp(
        config.target_degree_center + config.target_degree_span * control,
        config.target_degree_min,
        config.target_degree_max,
    )
    previous_degree = previous_target_music_speed_degree
    delta = abs(target_degree - previous_degree) if previous_degree is not None else 1.0
    target_transition_slope = control
    direction = "flat"
    if control > 0.20:
        direction = "up"
    elif control < -0.20:
        direction = "down"

    max_jump = (
        config.max_direct_degree_jump_large
        if abs(control) >= 0.55
        else config.max_direct_degree_jump_small
    )
    allow_connector = abs(control) >= 0.20

    hold_reason: str | None = None
    change_reason: str | None = None
    should_change = True
    latency_debug = latency_decision_for_target(
        state=state,
        control=control,
        elapsed_since_last_change_sec=elapsed_since_last_change_sec,
        near_phrase_boundary=near_phrase_boundary,
        config=config,
    )
    if state.active_speed_zone == SpeedZone.STEADY_DEADBAND.value:
        should_change = False
        hold_reason = "within_steady_deadband"
    elif latency_debug["is_pace_up"]:
        should_change = bool(latency_debug["should_change"])
        hold_reason = latency_debug["change_blocked_reason"] if not should_change else None
        change_reason = latency_debug["change_intent_reason"] if should_change else None
    elif state.zone_stable_duration_sec < config.zone_change_confirm_sec:
        should_change = False
        hold_reason = "zone_change_not_confirmed"
    elif delta < config.target_degree_change_threshold:
        should_change = False
        hold_reason = "target_degree_delta_too_small"
    elif elapsed_since_last_change_sec < config.min_hold_sec:
        should_change = False
        hold_reason = "minimum_music_hold_not_met"
    elif not near_phrase_boundary:
        should_change = False
        hold_reason = "waiting_for_phrase_boundary"
    else:
        change_reason = "zone_stable_and_degree_delta_exceeded"

    latency_route = str(latency_debug["route"] if state.active_speed_zone != SpeedZone.STEADY_DEADBAND.value else "HOLD")
    if not latency_debug["is_pace_up"] and state.active_speed_zone != SpeedZone.STEADY_DEADBAND.value and should_change:
        latency_route = "STABILIZE"

    return TargetMusicBlockProfile(
        speed_zone=state.active_speed_zone,
        zone_stable_duration_sec=state.zone_stable_duration_sec,
        speed_gap_ratio=state.speed_gap_ratio,
        speed_trend_ratio=state.speed_trend_ratio,
        music_pace_control=control,
        target_music_speed_degree=target_degree,
        previous_target_music_speed_degree=previous_degree,
        target_degree_delta=delta,
        target_transition_slope=target_transition_slope,
        target_transition_direction=direction,
        recommended_block_bars=config.default_block_bars,
        min_hold_bars=config.stable_hold_bars_min,
        allow_connector=allow_connector,
        max_direct_degree_jump=max_jump,
        should_change_music=should_change,
        hold_reason=hold_reason,
        change_reason=change_reason,
        debug_intention_label=debug_intention_label_for_zone(state.active_speed_zone),
        latency_route=latency_route,
        max_change_latency_sec=float(latency_debug["max_change_latency_sec"]),
        estimated_change_latency_sec=float(latency_debug["estimated_change_latency_sec"]),
        confirmation_elapsed_sec=float(latency_debug["confirmation_elapsed_sec"]),
        min_hold_remaining_sec=float(latency_debug["min_hold_remaining_sec"]),
        boundary_wait_sec=float(latency_debug["boundary_wait_sec"]),
        crossfade_sec=float(latency_debug["crossfade_sec"]),
        change_intent_reason=latency_debug["change_intent_reason"],
        change_blocked_reason=hold_reason,
        forced_crossfade_used=bool(latency_debug["forced_crossfade_used"]),
    )


def is_pace_up_zone(zone: str, control: float) -> bool:
    return zone in {
        SpeedZone.LIGHT_PUSH.value,
        SpeedZone.PUSH.value,
        SpeedZone.STRONG_PUSH.value,
        SpeedZone.RHYTHM_REBUILD.value,
    } or control > 0.08


def latency_policy_for_config(config: V3Config) -> dict[str, float]:
    key = "demo_fast_switching" if config.active_tuning_profile == "demo_fast_switching" else "pace_up_responsive"
    base = config.latency_policy["pace_up_responsive"].copy()
    base.update(config.latency_policy.get(key, {}))
    return base


def latency_decision_for_target(
    *,
    state: RunnerControlState,
    control: float,
    elapsed_since_last_change_sec: float,
    near_phrase_boundary: bool,
    config: V3Config = V3Config(),
) -> dict[str, Any]:
    policy = latency_policy_for_config(config)
    is_pace_up = is_pace_up_zone(state.active_speed_zone, control)
    confirmation_sec = float(policy.get("confirmation_sec", 3.0)) if is_pace_up else config.zone_change_confirm_sec
    min_hold_sec = float(policy.get("min_hold_sec", 3.0)) if is_pace_up else config.min_hold_sec
    boundary_max_wait_sec = float(policy.get("boundary_max_wait_sec", 4.0)) if is_pace_up else 999.0
    crossfade_sec = float(policy.get("crossfade_sec", 2.0)) if is_pace_up else 2.0
    max_latency = float(policy.get("max_change_latency_sec", 10.0)) if is_pace_up else 999.0

    confirmation_remaining = max(0.0, confirmation_sec - state.zone_stable_duration_sec)
    min_hold_remaining = max(0.0, min_hold_sec - elapsed_since_last_change_sec)
    boundary_wait = 0.0 if near_phrase_boundary else boundary_max_wait_sec
    estimated = confirmation_remaining + min_hold_remaining + boundary_wait + crossfade_sec
    blocked = confirmation_remaining > 0 or min_hold_remaining > 0 or boundary_wait > 0
    forced = bool(is_pace_up and estimated > max_latency)

    if not is_pace_up:
        route = "HOLD"
        should_change = False
        intent = None
        blocked_reason = None
    elif forced:
        route = "FORCED_CROSSFADE"
        should_change = True
        intent = "pace_up_latency_budget_forced_crossfade"
        blocked_reason = None
        estimated = min(estimated, max_latency)
    elif confirmation_remaining <= 0 and min_hold_remaining <= 0:
        route = "WAIT_BOUNDARY" if boundary_wait > 0 else "CHANGE_NOW"
        should_change = True
        intent = "pace_up_boundary_ready_change_scheduled" if boundary_wait > 0 else "pace_up_latency_ready_change_now"
        blocked_reason = None
    elif blocked:
        route = "WAIT_BOUNDARY" if boundary_wait > 0 else "PRESELECT"
        should_change = False
        intent = "pace_up_candidate_preselected"
        if confirmation_remaining > 0:
            blocked_reason = "pace_up_confirmation_wait"
        elif min_hold_remaining > 0:
            blocked_reason = "pace_up_min_hold_wait"
        else:
            blocked_reason = "pace_up_boundary_wait"
    else:
        route = "CHANGE_NOW"
        should_change = True
        intent = "pace_up_latency_ready_change_now"
        blocked_reason = None

    return {
        "is_pace_up": is_pace_up,
        "route": route,
        "should_change": should_change,
        "max_change_latency_sec": max_latency,
        "estimated_change_latency_sec": max(0.0, estimated),
        "confirmation_elapsed_sec": max(0.0, state.zone_stable_duration_sec),
        "min_hold_remaining_sec": min_hold_remaining,
        "boundary_wait_sec": boundary_wait,
        "crossfade_sec": crossfade_sec,
        "change_intent_reason": intent,
        "change_blocked_reason": blocked_reason,
        "forced_crossfade_used": forced,
    }


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def music_speed_degree_match(segment: SegmentRecord, target: TargetMusicBlockProfile) -> float:
    return inverse_distance_score(segment.pace.music_speed_degree, target.target_music_speed_degree, 0.45)


def speed_zone_contrast_score(
    segment: SegmentRecord,
    target: TargetMusicBlockProfile,
    config: V3Config = V3Config(),
) -> float:
    low, high = config.preferred_degree_ranges.get(
        target.speed_zone,
        (max(config.target_degree_min, target.target_music_speed_degree - 0.10), min(config.target_degree_max, target.target_music_speed_degree + 0.10)),
    )
    degree = segment.pace.music_speed_degree
    if low <= degree <= high:
        return 1.0
    center = (low + high) / 2.0
    tolerance = max(0.12, (high - low) * 1.5)
    return inverse_distance_score(degree, center, tolerance)


def current_to_candidate_smoothness(
    current: SegmentRecord | None,
    candidate: SegmentRecord,
    target: TargetMusicBlockProfile,
) -> float:
    if current is None:
        return 0.80
    jump = abs(candidate.pace.start_degree - current.pace.end_degree)
    return inverse_distance_score(jump, 0.0, target.max_direct_degree_jump * 1.8)


def degree_step_smoothness(
    current: SegmentRecord | None,
    candidate: SegmentRecord,
    target: TargetMusicBlockProfile,
) -> float:
    if current is None:
        return 0.80
    desired_delta = target.target_music_speed_degree - current.pace.end_degree
    actual_delta = candidate.pace.mid_degree - current.pace.end_degree
    return inverse_distance_score(actual_delta, desired_delta, 0.35)


def cadence_lock_match(segment: SegmentRecord, target: TargetMusicBlockProfile) -> float:
    # Up/push zones need stronger cadence lock. Control/recovery can accept slightly less.
    min_needed = 0.72 if target.music_pace_control > 0.20 else 0.60
    return clamp(segment.pulse.cadence_lock_support / max(min_needed, 1e-6), 0.0, 1.0)


def flow_momentum_match(segment: SegmentRecord, target: TargetMusicBlockProfile) -> float:
    desired = clamp(0.50 + 0.30 * target.music_pace_control, 0.25, 0.85)
    return inverse_distance_score(segment.drive.flow_momentum_score, desired, 0.45)


def block_stability_score(segment: SegmentRecord) -> float:
    raw = (
        0.35 * segment.pace.degree_stability
        + 0.30 * segment.pulse.pulse_continuity_score
        + 0.20 * segment.drive.drive_preservation_score
        + 0.15 * segment.block.valid_runtime_block
    )
    return clamp(raw, 0.0, 1.0)


def jump_penalty(current: SegmentRecord | None, candidate: SegmentRecord, target: TargetMusicBlockProfile) -> float:
    if current is None:
        return 0.0
    jump = abs(candidate.pace.start_degree - current.pace.end_degree)
    if jump <= target.max_direct_degree_jump:
        return 0.0
    return clamp((jump - target.max_direct_degree_jump) / 0.35, 0.0, 1.0)


def intro_like_penalty(segment: SegmentRecord) -> float:
    return clamp(segment.risk.intro_like_score, 0.0, 1.0)


def pulse_drop_penalty(segment: SegmentRecord) -> float:
    return clamp(segment.risk.pulse_drop_score, 0.0, 1.0)


def overpush_penalty(segment: SegmentRecord, target: TargetMusicBlockProfile) -> float:
    # Overpush matters most in control/recovery and steady zones.
    multiplier = 1.0 if target.music_pace_control <= 0.15 else 0.45
    return clamp(segment.risk.overpush_risk * multiplier, 0.0, 1.0)


def target_arrival_score(connector: SegmentRecord, target_segment: SegmentRecord | None, target: TargetMusicBlockProfile) -> float:
    if target_segment is not None:
        return inverse_distance_score(connector.transition.transition_target_degree, target_segment.pace.start_degree, 0.35)
    return inverse_distance_score(connector.transition.transition_target_degree, target.target_music_speed_degree, 0.35)


def transition_slope_match(connector: SegmentRecord, target: TargetMusicBlockProfile) -> float:
    return inverse_distance_score(
        connector.transition.transition_slope,
        target.target_transition_slope,
        0.75,
    )


def asc_cue_fit(segment: SegmentRecord, target: TargetMusicBlockProfile, config: V3Config = V3Config()) -> float:
    candidate = segment.pace_assist.primary_ASC_spm
    if candidate <= 0:
        return 0.0
    current_music = target.current_music_ASC_spm
    cadence = target.current_runner_cadence_spm
    desired = target.desired_next_ASC_spm
    if desired is None:
        return 0.50
    tolerance = config.pace_assist_v3_4.get("asc_tolerance_spm", 3.0)
    if target.pace_lift_state == "hold_or_stabilize":
        center = max(current_music or 0.0, (cadence or desired) * 0.96)
        return inverse_distance_score(candidate, center, max(8.0, tolerance * 2.0))
    return inverse_distance_score(candidate, desired, max(tolerance, 1.0))


def asc_quality_score(segment: SegmentRecord) -> float:
    profile = segment.pace_assist
    return clamp(
        0.30 * profile.ASC_strength
        + 0.30 * profile.ASC_stability
        + 0.20 * profile.pulse_clarity
        + 0.20 * profile.rhythm_predictability,
        0.0,
        1.0,
    )


def ai_negative_semantic_risk(segment: SegmentRecord) -> float:
    ai = segment.pace_assist.ai_semantic_scores or {}
    return clamp(
        max(
            float(ai.get("half_time_trap", 0.0) or 0.0),
            float(ai.get("cinematic_breakdown", 0.0) or 0.0),
            float(ai.get("beatless_bridge", 0.0) or 0.0),
            float(ai.get("fake_groove", 0.0) or 0.0),
            float(ai.get("too_aggressive", 0.0) or 0.0),
            0.7 * float(ai.get("unclear_cue", 0.0) or 0.0),
        ),
        0.0,
        1.0,
    )


def asc_risk_safety(segment: SegmentRecord) -> float:
    profile = segment.pace_assist
    risk = max(
        profile.pulse_dropout_risk,
        profile.half_time_shift_risk,
        profile.fake_groove_risk,
        ai_negative_semantic_risk(segment),
    )
    return clamp(1.0 - risk, 0.0, 1.0)


def asc_lift_from_current_music(segment: SegmentRecord, target: TargetMusicBlockProfile) -> float | None:
    if target.current_music_ASC_spm is None:
        return None
    return segment.pace_assist.primary_ASC_spm - target.current_music_ASC_spm


def hard_filter_pace_assist_v3_4(segment: SegmentRecord, target: TargetMusicBlockProfile, config: V3Config = V3Config()) -> list[str]:
    cfg = config.pace_assist_v3_4
    profile = segment.pace_assist
    reasons: list[str] = []
    if not profile.ai_semantic_scores:
        return reasons
    if profile.primary_ASC_spm <= 0:
        reasons.append("missing_candidate_ASC_spm")
    if profile.ASC_strength < cfg.get("asc_strength_min", 0.65):
        reasons.append("asc_strength_too_low")
    if profile.ASC_stability < cfg.get("asc_stability_min", 0.70):
        reasons.append("asc_stability_too_low")
    if profile.pulse_clarity < cfg.get("pulse_clarity_min", 0.55):
        reasons.append("pulse_clarity_too_low")
    if profile.rhythm_predictability < cfg.get("rhythm_predictability_min", 0.55):
        reasons.append("rhythm_predictability_too_low")
    if profile.pulse_dropout_risk > cfg.get("pulse_dropout_max", 0.25):
        reasons.append("pulse_dropout_risk")
    if profile.half_time_shift_risk > cfg.get("half_time_risk_max", 0.25):
        reasons.append("half_time_shift_risk")
    if profile.fake_groove_risk > cfg.get("fake_groove_risk_max", 0.35):
        reasons.append("fake_groove_risk")
    if ai_negative_semantic_risk(segment) > cfg.get("ai_negative_semantic_risk_max", 0.40):
        reasons.append("ai_negative_semantic_risk")

    current_music = target.current_music_ASC_spm
    cadence = target.current_runner_cadence_spm
    desired = target.desired_next_ASC_spm
    if target.pace_lift_state != "hold_or_stabilize":
        if current_music is not None and profile.primary_ASC_spm <= current_music + cfg.get("min_lift_from_current_music_spm", 2.0):
            reasons.append("not_higher_than_current_music")
        if cadence is not None and profile.primary_ASC_spm > cadence * (1.0 + cfg.get("max_cadence_overcue_pct", 0.07)):
            reasons.append("overcue_risk")
        if desired is not None and abs(profile.primary_ASC_spm - desired) > cfg.get("asc_tolerance_spm", 3.0) + 6.0:
            reasons.append("far_from_desired_next_ASC")
    else:
        floor = (current_music or 0.0) + cfg.get("fast_min_asc_floor_from_current_music", -1.0)
        if profile.primary_ASC_spm < floor:
            reasons.append("fast_state_blocks_slow_down_music")
        if profile.pulse_dropout_risk > min(0.35, cfg.get("pulse_dropout_max", 0.25) + 0.10):
            reasons.append("fast_state_blocks_pulse_drop")
        if profile.half_time_shift_risk > min(0.35, cfg.get("half_time_risk_max", 0.25) + 0.10):
            reasons.append("fast_state_blocks_half_time")
    return reasons


# ---------------------------------------------------------------------------
# Filters and scoring
# ---------------------------------------------------------------------------


def base_hard_filter(
    segment: SegmentRecord,
    target: TargetMusicBlockProfile,
    history: SessionHistory | None = None,
    config: V3Config = V3Config(),
) -> list[str]:
    reasons: list[str] = []
    history = history or SessionHistory()
    if segment.manual_disabled:
        reasons.append("manual_disabled")
    if not segment.is_contiguous_original_audio:
        reasons.append("not_contiguous_original_audio")
    if segment.segment_use == SegmentUse.REJECT.value:
        reasons.append("segment_use_reject")
    if segment.segment_id in history.recent_segment_ids:
        reasons.append("recent_segment_hard_exclude")
    if config.recent_track_penalty >= 0.90 and segment.track_id in history.recent_track_ids[: config.recent_track_cooldown_count]:
        reasons.append("recent_track_cooldown_hard_exclude")
    if segment.combined_confidence < config.min_valid_block_confidence:
        reasons.append("low_combined_confidence")
    if segment.block.phrase_confidence < config.min_phrase_confidence:
        reasons.append("low_phrase_confidence")
    if segment.risk.chaos_risk > config.max_chaos_risk:
        reasons.append("chaos_risk_too_high")
    if segment.risk.static_risk > config.max_static_risk:
        reasons.append("static_risk_too_high")
    return reasons


def hard_filter_stable(
    segment: SegmentRecord,
    target: TargetMusicBlockProfile,
    current: SegmentRecord | None = None,
    history: SessionHistory | None = None,
    config: V3Config = V3Config(),
) -> list[str]:
    reasons = base_hard_filter(segment, target, history, config)
    if segment.segment_use != SegmentUse.STABLE.value:
        reasons.append("not_stable_main_candidate")
    if not segment.block.valid_runtime_block:
        reasons.append("invalid_runtime_block")
    if segment.duration_sec < min(20.0, config.min_hold_sec * 0.75):
        reasons.append("block_too_short")
    if segment.risk.intro_like_score >= config.connector_intro_like_block:
        reasons.append("intro_like_stable_block")
    if segment.risk.pulse_drop_score >= config.connector_pulse_drop_block:
        reasons.append("pulse_drop_stable_block")
    strict_fake_gate = (
        config.active_tuning_profile == "strict_no_fake_groove"
        or min(
            config.fake_groove_thresholds.get("tempo_feel_drop_block", 1.0),
            config.fake_groove_thresholds.get("pulse_density_drop_block", 1.0),
            config.fake_groove_thresholds.get("drive_cliff_block", 1.0),
        )
        <= 0.30
    )
    if strict_fake_gate:
        fake_reasons = fake_groove_reasons(segment, config)
        reasons.extend(f"fake_groove_{reason}" for reason in fake_reasons)
    if target.desired_next_ASC_spm is not None:
        reasons.extend(hard_filter_pace_assist_v3_4(segment, target, config))
    return reasons


def hard_filter_connector(
    segment: SegmentRecord,
    target: TargetMusicBlockProfile,
    current: SegmentRecord | None = None,
    history: SessionHistory | None = None,
    runtime_context: str = RuntimeContext.RUNTIME.value,
    config: V3Config = V3Config(),
) -> list[str]:
    reasons = base_hard_filter(segment, target, history, config)
    if segment.segment_use == SegmentUse.ENTRY_ONLY.value and runtime_context != RuntimeContext.INITIAL_ENTRY.value:
        reasons.append("ENTRY_ONLY_blocked_during_runtime")
    if segment.segment_use not in {SegmentUse.DRIVE_CONNECTOR.value, SegmentUse.EXIT_CONNECTOR.value, SegmentUse.ENTRY_ONLY.value}:
        reasons.append("not_connector_candidate")
    if not segment.transition.runtime_connector_allowed:
        reasons.append("runtime_connector_not_allowed")
    if segment.risk.intro_like_score >= config.connector_intro_like_block:
        reasons.append("intro_like_connector_blocked")
    if segment.risk.pulse_drop_score >= config.connector_pulse_drop_block:
        reasons.append("connector_pulse_drop_blocked")
    if segment.pulse.pulse_continuity_score < config.connector_pulse_continuity_min:
        reasons.append("connector_low_pulse_continuity")
    if segment.drive.drive_preservation_score < config.connector_drive_preservation_min:
        reasons.append("connector_low_drive_preservation")
    if segment.pulse.cadence_lock_continuity < config.connector_cadence_lock_continuity_min:
        reasons.append("connector_low_cadence_lock_continuity")
    if segment.pace.music_speed_degree < target.target_music_speed_degree - config.connector_target_drop_margin:
        reasons.append("connector_drops_music_speed_degree")
    if target.music_pace_control > 0.20 and segment.transition.transition_slope < -0.25:
        reasons.append("up_control_blocks_down_connector")
    if target.music_pace_control < -0.20 and segment.transition.transition_slope > 0.25:
        reasons.append("down_control_blocks_up_connector")
    if target.target_transition_direction == "up" and segment.segment_use == SegmentUse.EXIT_CONNECTOR.value:
        reasons.append("exit_connector_not_allowed_for_upward_control")
    return reasons


def fake_groove_reasons(segment: SegmentRecord, config: V3Config = V3Config()) -> list[str]:
    thresholds = config.fake_groove_thresholds
    tempo_feel_drop = segment.risk.pulse_drop_score
    pulse_density_drop = segment.risk.pulse_drop_score
    drive_cliff = (
        1.0 - segment.drive.drive_preservation_score
        if segment.drive.drive_preservation_score < config.connector_drive_preservation_min
        else 0.0
    )
    half_time_shift = segment.risk.breakdown_like_score
    internal_degree_range = 1.0 - segment.pace.degree_stability
    effective_pulse_stability = segment.pulse.pulse_continuity_score
    reasons: list[str] = []
    if tempo_feel_drop >= thresholds.get("tempo_feel_drop_block", 0.35):
        reasons.append("tempo_feel_drop")
    if pulse_density_drop >= thresholds.get("pulse_density_drop_block", 0.35):
        reasons.append("pulse_density_drop")
    if drive_cliff >= thresholds.get("drive_cliff_block", 0.35):
        reasons.append("drive_cliff")
    if half_time_shift >= thresholds.get("half_time_shift_block", 0.40):
        reasons.append("half_time_shift_risk")
    if internal_degree_range >= thresholds.get("internal_degree_range_block", 0.28):
        reasons.append("unstable_internal_speed_degree")
    if effective_pulse_stability < thresholds.get("effective_pulse_stability_min", 0.55):
        reasons.append("low_effective_pulse_stability")
    return reasons


def stable_score(
    segment: SegmentRecord,
    target: TargetMusicBlockProfile,
    current: SegmentRecord | None = None,
    config: V3Config = V3Config(),
) -> tuple[float, dict[str, float]]:
    components = {
        "music_speed_degree_match": music_speed_degree_match(segment, target),
        "speed_zone_contrast_score": speed_zone_contrast_score(segment, target, config),
        "current_to_candidate_smoothness": current_to_candidate_smoothness(current, segment, target),
        "degree_step_smoothness": degree_step_smoothness(current, segment, target),
        "pulse_continuity_score": segment.pulse.pulse_continuity_score,
        "drive_preservation_score": segment.drive.drive_preservation_score,
        "cadence_lock_match": cadence_lock_match(segment, target),
        "flow_momentum_match": flow_momentum_match(segment, target),
        "block_stability_score": block_stability_score(segment),
        "diversity_score": 0.50,  # filled/adjusted by final diversity pass
        "jump_penalty": jump_penalty(current, segment, target),
        "pulse_drop_penalty": pulse_drop_penalty(segment),
        "intro_like_penalty": intro_like_penalty(segment),
        "overpush_penalty": overpush_penalty(segment, target),
        "pace_assist_score": segment.pace_assist.pace_assist_score,
        "asc_cue_fit": asc_cue_fit(segment, target, config),
        "asc_quality_score": asc_quality_score(segment),
        "asc_risk_safety": asc_risk_safety(segment),
        "candidate_ASC_spm": segment.pace_assist.primary_ASC_spm,
        "ASC_lift_from_current_music": asc_lift_from_current_music(segment, target) or 0.0,
    }
    weights = config.score_weights
    legacy_score = (
        weights.get("music_speed_degree_match", 0.18) * components["music_speed_degree_match"]
        + weights.get("speed_zone_contrast_score", 0.16) * components["speed_zone_contrast_score"]
        + weights.get("current_to_candidate_smoothness", 0.13) * components["current_to_candidate_smoothness"]
        + weights.get("degree_step_smoothness", 0.10) * components["degree_step_smoothness"]
        + weights.get("pulse_continuity_score", 0.11) * components["pulse_continuity_score"]
        + weights.get("drive_preservation_score", 0.10) * components["drive_preservation_score"]
        + weights.get("cadence_lock_support", 0.08) * components["cadence_lock_match"]
        + weights.get("flow_momentum_score", 0.07) * components["flow_momentum_match"]
        + weights.get("block_stability_score", 0.07) * components["block_stability_score"]
        - weights.get("jump_penalty", 0.12) * components["jump_penalty"]
        - weights.get("pulse_drop_penalty", 0.12) * components["pulse_drop_penalty"]
        - weights.get("intro_like_penalty", 0.08) * components["intro_like_penalty"]
        - weights.get("overpush_penalty", 0.06) * components["overpush_penalty"]
    )
    asc_score = (
        weights.get("pace_assist_score", 0.34) * components["pace_assist_score"]
        + weights.get("asc_cue_fit", 0.18) * components["asc_cue_fit"]
        + weights.get("asc_quality_score", 0.16) * components["asc_quality_score"]
        + weights.get("asc_risk_safety", 0.12) * components["asc_risk_safety"]
    )
    score = 0.42 * legacy_score + 0.58 * asc_score if target.desired_next_ASC_spm is not None else legacy_score
    return clamp(score, 0.0, 1.0), components


def connector_score(
    connector: SegmentRecord,
    target: TargetMusicBlockProfile,
    target_segment: SegmentRecord | None = None,
    config: V3Config = V3Config(),
) -> tuple[float, dict[str, float]]:
    components = {
        "transition_slope_match": transition_slope_match(connector, target),
        "drive_connector_score": connector.transition.drive_connector_score,
        "target_arrival_score": target_arrival_score(connector, target_segment, target),
        "pulse_continuity_score": connector.pulse.pulse_continuity_score,
        "music_speed_degree_match": music_speed_degree_match(connector, target),
        "drive_preservation_score": connector.drive.drive_preservation_score,
        "entry_exit_quality": min(connector.drive.entry_drive_score, connector.drive.exit_drive_score),
        "pulse_drop_penalty": pulse_drop_penalty(connector),
        "intro_like_penalty": intro_like_penalty(connector),
        "low_drive_penalty": 1.0 - connector.drive.drive_preservation_score,
    }
    weights = config.score_weights
    score = (
        0.18 * components["transition_slope_match"]
        + 0.16 * components["drive_connector_score"]
        + 0.15 * components["target_arrival_score"]
        + weights.get("pulse_continuity_score", 0.14) * components["pulse_continuity_score"]
        + weights.get("music_speed_degree_match", 0.12) * components["music_speed_degree_match"]
        + weights.get("drive_preservation_score", 0.10) * components["drive_preservation_score"]
        + 0.08 * components["entry_exit_quality"]
        - weights.get("pulse_drop_penalty", 0.14) * components["pulse_drop_penalty"]
        - weights.get("intro_like_penalty", 0.12) * components["intro_like_penalty"]
        - 0.10 * components["low_drive_penalty"]
    )
    return clamp(score, 0.0, 1.0), components


# ---------------------------------------------------------------------------
# Diversity, coverage, and Korean explainability
# ---------------------------------------------------------------------------


def diversity_penalties(
    segment: SegmentRecord,
    history: SessionHistory,
    config: V3Config = V3Config(),
) -> dict[str, float]:
    penalties: dict[str, float] = {}
    if segment.track_id in history.recent_track_ids:
        penalties["same_track_penalty"] = config.recent_track_penalty
    seg_bin = degree_bin(segment.pace.music_speed_degree, config.degree_bin_size)
    if seg_bin in history.recent_degree_bins:
        penalties["same_degree_bin_repeat_penalty"] = config.same_degree_bin_penalty
    if segment.section_label in history.recent_section_labels:
        penalties["same_section_label_repeat_penalty"] = config.same_section_label_penalty
    play_count = int(history.session_play_counts.get(segment.track_id, 0))
    if play_count > 0:
        penalties["session_play_count_penalty"] = min(
            config.session_play_count_penalty_max,
            play_count * config.session_play_count_penalty,
        )
    return penalties


def apply_diversity(
    scored: list[tuple[SegmentRecord, float, dict[str, float]]],
    history: SessionHistory,
    config: V3Config = V3Config(),
) -> list[CandidateScore]:
    if not scored:
        return []
    top_score = max(score for _, score, _ in scored)
    result: list[CandidateScore] = []
    for segment, base, breakdown in scored:
        penalties = diversity_penalties(segment, history, config)
        eligible_for_diversity = base >= top_score - config.controlled_diversity_score_margin
        total_penalty = sum(penalties.values()) if eligible_for_diversity else 0.0
        final = clamp(base - total_penalty, 0.0, 1.0)
        why_selected = build_why_selected_ko(segment, breakdown, penalties, eligible_for_diversity)
        result.append(
            CandidateScore(
                segment_id=segment.segment_id,
                track_id=segment.track_id,
                segment_use=segment.segment_use,
                base_score=base,
                final_score=final,
                score_breakdown=breakdown,
                diversity_penalties=penalties,
                why_selected_ko=tuple(why_selected),
            )
        )
    return sorted(result, key=lambda s: s.final_score, reverse=True)


def build_why_selected_ko(
    segment: SegmentRecord,
    breakdown: Mapping[str, float],
    penalties: Mapping[str, float],
    diversity_applied: bool,
) -> list[str]:
    reasons: list[str] = []
    if breakdown.get("music_speed_degree_match", 0.0) >= 0.75:
        reasons.append("목표 music speed degree와 가깝습니다.")
    if segment.pulse.pulse_continuity_score >= 0.75:
        reasons.append("kick/pulse가 안정적으로 유지됩니다.")
    if segment.drive.drive_preservation_score >= 0.75:
        reasons.append("구간 중간에 drive가 꺼지지 않습니다.")
    if segment.risk.intro_like_score < 0.20:
        reasons.append("intro-like 위험이 낮습니다.")
    if penalties:
        reasons.append("최근 재생 이력 때문에 다양성 penalty가 일부 적용되었습니다.")
    if diversity_applied:
        reasons.append("품질 점수가 충분히 높은 후보 풀 안에서 controlled diversity를 적용했습니다.")
    return reasons


def metric_level(value: float) -> str:
    if value < 0.20:
        return "Very Low"
    if value < 0.40:
        return "Low"
    if value < 0.60:
        return "Medium"
    if value < 0.80:
        return "High"
    return "Very High"


def risk_level(value: float) -> str:
    if value < 0.20:
        return "Safe"
    if value < 0.35:
        return "Watch"
    if value < 0.45:
        return "Risky"
    return "Block"


METRIC_EXPLANATIONS_KO: dict[str, str] = {
    "music_speed_degree": "러닝 속도감을 얼마나 밀어주는지 나타내는 핵심 값입니다.",
    "pulse_continuity_score": "kick/pulse가 구간 내내 안정적으로 유지되는지 나타냅니다.",
    "drive_preservation_score": "구간 중간에 힘이 빠지지 않고 drive가 유지되는지 나타냅니다.",
    "cadence_lock_support": "러너의 cadence와 음악 pulse가 맞을 가능성을 나타냅니다.",
    "intro_like_score": "intro처럼 힘이 빠지는 구간일 가능성을 나타냅니다.",
    "pulse_drop_score": "중간에 beat/pulse가 사라질 위험을 나타냅니다.",
    "target_music_speed_degree": "현재 control speed zone에서 추천기가 찾는 목표 음악 속도감입니다.",
    "speed_gap_ratio": "최근 control speed가 목표 속도에서 얼마나 벗어났는지 나타냅니다.",
}


RISK_KEYS = {
    "intro_like_score",
    "pulse_drop_score",
    "dropout_risk",
    "breakdown_like_score",
    "static_risk",
    "chaos_risk",
    "overpush_risk",
}


def metric_explain_ko(metric_key: str, value: float) -> dict[str, Any]:
    is_risk = metric_key in RISK_KEYS
    level = risk_level(value) if is_risk else metric_level(value)
    explanation = METRIC_EXPLANATIONS_KO.get(metric_key, "분석 metric입니다. 값의 높고 낮음을 기준표와 함께 확인하세요.")
    if is_risk:
        threshold = "0.00~0.20 Safe, 0.20~0.35 Watch, 0.35~0.45 Risky, 0.45 이상 Block/strong penalty"
    else:
        threshold = "0.00~0.20 Very Low, 0.20~0.40 Low, 0.40~0.60 Medium, 0.60~0.80 High, 0.80~1.00 Very High"
    impact = recommendation_impact_ko(metric_key, value)
    return {
        "metric_key": metric_key,
        "numeric_value": round(value, 4),
        "level": level,
        "explanation_ko": explanation,
        "threshold_ko": threshold,
        "recommendation_impact_ko": impact,
    }


def recommendation_impact_ko(metric_key: str, value: float) -> str:
    if metric_key == "music_speed_degree":
        if value >= 0.70:
            return "strong_push / rhythm_rebuild 상태에서 유리합니다."
        if value >= 0.60:
            return "light_push / controlled_push 상태에 적합합니다."
        if value >= 0.40:
            return "steady block 후보로 적합합니다."
        return "control/recovery 상태에 더 적합합니다."
    if metric_key == "intro_like_score":
        return "0.45 이상이면 runtime 중간 추천에서 차단합니다." if value >= 0.45 else "runtime 추천 사용 가능성이 높습니다."
    if metric_key == "pulse_drop_score":
        return "0.35 이상이면 connector에서 제외합니다." if value >= 0.35 else "러닝 흐름을 깨지 않을 가능성이 높습니다."
    if metric_key == "pulse_continuity_score":
        return "0.60 미만이면 runtime connector 후보에서 제외합니다." if value < 0.60 else "러닝 중간 block으로 사용하기 좋습니다."
    if metric_key == "drive_preservation_score":
        return "0.55 미만이면 drive connector로 사용하지 않습니다." if value < 0.55 else "stable block 또는 drive connector 후보로 좋습니다."
    return "추천 점수와 debug 판단에 사용됩니다."


# ---------------------------------------------------------------------------
# Coverage audit
# ---------------------------------------------------------------------------


def coverage_audit(
    segments: Sequence[SegmentRecord],
    config: V3Config = V3Config(),
) -> list[CoverageBin]:
    bins: dict[str, dict[str, Any]] = {}
    for seg in segments:
        b = degree_bin(seg.pace.music_speed_degree, config.degree_bin_size)
        row = bins.setdefault(
            b,
            {
                "stable": 0,
                "drive_connector": 0,
                "exit_connector": 0,
                "entry_only": 0,
                "reject": 0,
                "tracks": set(),
            },
        )
        row["tracks"].add(seg.track_id)
        if seg.segment_use == SegmentUse.STABLE.value:
            row["stable"] += 1
        elif seg.segment_use == SegmentUse.DRIVE_CONNECTOR.value:
            row["drive_connector"] += 1
        elif seg.segment_use == SegmentUse.EXIT_CONNECTOR.value:
            row["exit_connector"] += 1
        elif seg.segment_use == SegmentUse.ENTRY_ONLY.value:
            row["entry_only"] += 1
        elif seg.segment_use == SegmentUse.REJECT.value:
            row["reject"] += 1

    output: list[CoverageBin] = []
    for b, row in sorted(bins.items()):
        warnings: list[str] = []
        stable = row["stable"]
        conn = row["drive_connector"]
        unique_tracks = len(row["tracks"])
        if stable < config.min_stable_candidates_per_bin:
            warnings.append("stable_pool_too_small")
        if conn < config.min_connector_candidates_per_bin:
            warnings.append("connector_pool_too_small")
        if unique_tracks < config.min_unique_tracks_per_bin:
            warnings.append("unique_track_count_too_small")
        if not warnings:
            explanation = "이 degree bin은 추천 후보가 비교적 충분합니다."
        else:
            explanation = "이 degree bin은 후보가 부족하여 같은 음악 반복 또는 fallback이 발생할 수 있습니다."
        output.append(
            CoverageBin(
                degree_bin=b,
                stable_count=stable,
                drive_connector_count=conn,
                exit_connector_count=row["exit_connector"],
                entry_only_count=row["entry_only"],
                reject_count=row["reject"],
                unique_track_count=unique_tracks,
                warnings=tuple(warnings),
                explanation_ko=explanation,
            )
        )
    return output


def warnings_for_target_bin(
    target: TargetMusicBlockProfile,
    segments: Sequence[SegmentRecord],
    config: V3Config = V3Config(),
) -> tuple[str, ...]:
    target_bin = degree_bin(target.target_music_speed_degree, config.degree_bin_size)
    audit = {row.degree_bin: row for row in coverage_audit(segments, config)}
    row = audit.get(target_bin)
    warnings: list[str] = []
    if row is None:
        return ("target_degree_bin_underfilled", "candidate_pool_too_small")
    warnings.extend(row.warnings)
    if row.stable_count + row.drive_connector_count < (
        config.min_stable_candidates_per_bin + config.min_connector_candidates_per_bin
    ):
        warnings.append("candidate_pool_too_small")
    return tuple(dict.fromkeys(warnings))


# ---------------------------------------------------------------------------
# Recommendation
# ---------------------------------------------------------------------------


def score_stable_candidates(
    segments: Sequence[SegmentRecord],
    target: TargetMusicBlockProfile,
    current: SegmentRecord | None,
    history: SessionHistory,
    config: V3Config = V3Config(),
) -> tuple[list[CandidateScore], dict[str, tuple[str, ...]]]:
    scored: list[tuple[SegmentRecord, float, dict[str, float]]] = []
    rejected: dict[str, tuple[str, ...]] = {}
    for seg in segments:
        reasons = hard_filter_stable(seg, target, current, history, config)
        if reasons:
            rejected[seg.segment_id] = tuple(reasons)
            continue
        score, breakdown = stable_score(seg, target, current, config)
        scored.append((seg, score, breakdown))
    return apply_diversity(scored, history, config), rejected


def score_connector_candidates(
    segments: Sequence[SegmentRecord],
    target: TargetMusicBlockProfile,
    current: SegmentRecord | None,
    history: SessionHistory,
    runtime_context: str = RuntimeContext.RUNTIME.value,
    config: V3Config = V3Config(),
) -> tuple[list[CandidateScore], dict[str, tuple[str, ...]]]:
    scored: list[tuple[SegmentRecord, float, dict[str, float]]] = []
    rejected: dict[str, tuple[str, ...]] = {}
    for seg in segments:
        reasons = hard_filter_connector(seg, target, current, history, runtime_context, config)
        if reasons:
            rejected[seg.segment_id] = tuple(reasons)
            continue
        score, breakdown = connector_score(seg, target, None, config)
        scored.append((seg, score, breakdown))
    return apply_diversity(scored, history, config), rejected


def relaxed_sparse_pool_config(config: V3Config = V3Config()) -> V3Config:
    pace_cfg = dict(config.pace_assist_v3_4)
    pace_cfg.update(
        {
            "asc_strength_min": min(pace_cfg.get("asc_strength_min", 0.65), 0.35),
            "asc_stability_min": min(pace_cfg.get("asc_stability_min", 0.70), 0.35),
            "pulse_clarity_min": min(pace_cfg.get("pulse_clarity_min", 0.55), 0.15),
            "rhythm_predictability_min": min(pace_cfg.get("rhythm_predictability_min", 0.55), 0.0),
            "pulse_dropout_max": max(pace_cfg.get("pulse_dropout_max", 0.25), 0.45),
            "half_time_risk_max": max(pace_cfg.get("half_time_risk_max", 0.25), 0.45),
            "fake_groove_risk_max": max(pace_cfg.get("fake_groove_risk_max", 0.35), 0.55),
            "min_lift_from_current_music_spm": min(pace_cfg.get("min_lift_from_current_music_spm", 2.0), -4.0),
            "asc_tolerance_spm": max(pace_cfg.get("asc_tolerance_spm", 3.0), 18.0),
            "max_cadence_overcue_pct": max(pace_cfg.get("max_cadence_overcue_pct", 0.07), 0.18),
            "ai_negative_semantic_risk_max": max(pace_cfg.get("ai_negative_semantic_risk_max", 0.40), 0.75),
        }
    )
    return replace(
        config,
        pace_assist_v3_4=pace_cfg,
        recent_track_penalty=min(config.recent_track_penalty, 0.45),
        controlled_diversity_score_margin=max(config.controlled_diversity_score_margin, 0.50),
    )


def _by_id(segments: Sequence[SegmentRecord]) -> dict[str, SegmentRecord]:
    return {s.segment_id: s for s in segments}


def recommend_next_block(
    segments: Sequence[SegmentRecord],
    target: TargetMusicBlockProfile,
    current_segment: SegmentRecord | None = None,
    history: SessionHistory | None = None,
    runtime_context: str = RuntimeContext.RUNTIME.value,
    config: V3Config = V3Config(),
) -> RecommendationResult:
    history = history or SessionHistory()
    segment_by_id = _by_id(segments)
    target_bin = degree_bin(target.target_music_speed_degree, config.degree_bin_size)
    pool_warnings = list(warnings_for_target_bin(target, segments, config))

    stable_scores, stable_rejected = score_stable_candidates(segments, target, current_segment, history, config)
    connector_scores, connector_rejected = score_connector_candidates(
        segments, target, current_segment, history, runtime_context, config
    )
    if not stable_scores and target.desired_next_ASC_spm is not None:
        relaxed_config = relaxed_sparse_pool_config(config)
        stable_scores, stable_rejected = score_stable_candidates(
            segments,
            target,
            current_segment,
            history,
            relaxed_config,
        )
        if stable_scores:
            pool_warnings.append("relaxed_pace_assist_sparse_pool_fallback")
        else:
            current_segment_ids = (current_segment.segment_id,) if current_segment is not None else ()
            relaxed_history = replace(history, recent_segment_ids=current_segment_ids)
            stable_scores, stable_rejected = score_stable_candidates(
                segments,
                target,
                current_segment,
                relaxed_history,
                relaxed_config,
            )
            if stable_scores:
                pool_warnings.append("relaxed_recent_segment_sparse_pool_fallback")
            else:
                legacy_target = replace(target, desired_next_ASC_spm=None)
                stable_scores, stable_rejected = score_stable_candidates(
                    segments,
                    legacy_target,
                    current_segment,
                    relaxed_history,
                    relaxed_config,
                )
                if stable_scores:
                    pool_warnings.append("legacy_speed_degree_sparse_pool_fallback")
    preselected_segment_id = stable_scores[0].segment_id if stable_scores else None

    if not target.should_change_music:
        return RecommendationResult(
            route_type=RouteType.HOLD.value,
            immediate_segment=current_segment,
            target_segment=current_segment,
            target_profile=target,
            hold_reason=target.hold_reason,
            change_reason=None,
            top_candidates=tuple(stable_scores[:10]),
            candidate_pool_warning=tuple(pool_warnings),
            debug={
                "target_degree_bin": target_bin,
                "hold_reason": target.hold_reason,
                "preselected_segment_id": preselected_segment_id,
                "stable_rejected": stable_rejected,
                "connector_rejected": connector_rejected,
            },
        )

    if not stable_scores:
        pool_warnings.append("stable_pool_too_small")
        return RecommendationResult(
            route_type=RouteType.NO_CANDIDATE.value,
            immediate_segment=None,
            target_segment=None,
            target_profile=target,
            hold_reason="no_valid_stable_candidate",
            change_reason=None,
            top_candidates=tuple(connector_scores[:10]),
            candidate_pool_warning=tuple(dict.fromkeys(pool_warnings)),
            debug={
                "target_degree_bin": target_bin,
                "preselected_segment_id": preselected_segment_id,
                "stable_rejected": stable_rejected,
                "connector_rejected": connector_rejected,
            },
        )

    best_stable_score = stable_scores[0]
    best_stable = segment_by_id[best_stable_score.segment_id]
    direct_jump = 0.0
    if current_segment is not None:
        direct_jump = abs(best_stable.pace.start_degree - current_segment.pace.end_degree)

    direct_allowed = direct_jump <= target.max_direct_degree_jump or not target.allow_connector
    if direct_allowed or not connector_scores:
        if target.allow_connector and not connector_scores and direct_jump > target.max_direct_degree_jump:
            pool_warnings.append("connector_pool_too_small")
        return RecommendationResult(
            route_type=RouteType.DIRECT.value,
            immediate_segment=best_stable,
            target_segment=best_stable,
            target_profile=target,
            hold_reason=None,
            change_reason=target.change_reason or "direct_block_selected",
            top_candidates=tuple(stable_scores[:10]),
            candidate_pool_warning=tuple(dict.fromkeys(pool_warnings)),
            debug={
                "target_degree_bin": target_bin,
                "direct_jump": direct_jump,
                "direct_allowed": direct_allowed,
                "selected_candidate_rank": 1,
                "preselected_segment_id": preselected_segment_id,
                "stable_rejected": stable_rejected,
                "connector_rejected": connector_rejected,
            },
        )

    best_connector_score = connector_scores[0]
    best_connector = segment_by_id[best_connector_score.segment_id]
    combined_route_score = 0.55 * best_connector_score.final_score + 0.45 * best_stable_score.final_score
    direct_route_score = best_stable_score.final_score - clamp(direct_jump - target.max_direct_degree_jump, 0.0, 1.0)
    route_type = RouteType.CONNECTOR.value if combined_route_score >= direct_route_score else RouteType.DIRECT.value
    immediate = best_connector if route_type == RouteType.CONNECTOR.value else best_stable

    return RecommendationResult(
        route_type=route_type,
        immediate_segment=immediate,
        target_segment=best_stable,
        target_profile=target,
        hold_reason=None,
        change_reason=target.change_reason or "route_selected",
        top_candidates=tuple((connector_scores + stable_scores)[:10]),
        candidate_pool_warning=tuple(dict.fromkeys(pool_warnings)),
        debug={
            "target_degree_bin": target_bin,
            "direct_jump": direct_jump,
            "max_direct_degree_jump": target.max_direct_degree_jump,
            "combined_route_score": combined_route_score,
            "direct_route_score": direct_route_score,
            "selected_candidate_rank": 1,
            "preselected_segment_id": preselected_segment_id,
            "stable_pool_size": len(stable_scores),
            "connector_pool_size": len(connector_scores),
            "stable_rejected": stable_rejected,
            "connector_rejected": connector_rejected,
        },
    )


# ---------------------------------------------------------------------------
# Sample manifest and simple construction helpers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SampleManifestRow:
    track_id: str
    title: str
    artist: str
    source: str
    license: str
    license_url: str
    download_url: str
    bpm_hint: float | None
    genre_hint: str
    usage_scope: str
    notes: str = ""

    def validate_for_edm_test(self) -> list[str]:
        warnings: list[str] = []
        genre = self.genre_hint.lower()
        if not any(k in genre for k in ["edm", "electronic", "house", "techno", "trance", "dance", "drum"]):
            warnings.append("genre_not_edm_like")
        if self.bpm_hint is not None and not (110 <= self.bpm_hint <= 180):
            warnings.append("bpm_outside_running_edm_test_range")
        if not self.license:
            warnings.append("missing_license")
        if not self.source:
            warnings.append("missing_source")
        return warnings


# ---------------------------------------------------------------------------
# Synthetic fixture helper for tests / demos
# ---------------------------------------------------------------------------


def make_segment(
    segment_id: str,
    track_id: str,
    degree: float,
    segment_use: str = SegmentUse.STABLE.value,
    section_label: str = "drop",
    start_degree: float | None = None,
    end_degree: float | None = None,
    transition_slope: float = 0.0,
    intro_like: float = 0.05,
    pulse_drop: float = 0.05,
    pulse_continuity: float = 0.82,
    drive_preservation: float = 0.82,
    cadence_lock: float = 0.78,
) -> SegmentRecord:
    start = degree if start_degree is None else start_degree
    end = degree if end_degree is None else end_degree
    return SegmentRecord(
        segment_id=segment_id,
        track_id=track_id,
        track_title=track_id,
        start_sec=0.0,
        end_sec=32.0,
        start_bar=0,
        end_bar=16,
        segment_use=segment_use,
        section_label=section_label,
        pace=SegmentPaceProfile(
            music_speed_degree=degree,
            start_degree=start,
            mid_degree=degree,
            end_degree=end,
            degree_slope=end - start,
            degree_stability=0.86,
            curve_shape="stable" if abs(end - start) < 0.08 else "ramp",
        ),
        pulse=PulseProfile(
            effective_pulse_bpm=128.0,
            kick_presence_score=0.84,
            pulse_continuity_score=pulse_continuity,
            beat_salience_score=0.82,
            beat_salience_continuity=0.80,
            cadence_lock_support=cadence_lock,
            cadence_lock_continuity=cadence_lock,
            rhythm_predictability_score=0.82,
        ),
        drive=DriveProfile(
            entry_drive_score=drive_preservation,
            mid_drive_score=drive_preservation,
            exit_drive_score=drive_preservation,
            drive_preservation_score=drive_preservation,
            flow_momentum_score=max(0.0, min(1.0, degree + 0.10)),
            pace_push_score=max(0.0, min(1.0, degree + 0.05)),
            bass_modulation_score=0.78,
        ),
        transition=TransitionProfile(
            transition_slope=transition_slope,
            transition_target_degree=end,
            transition_arrival_confidence=0.82,
            runtime_connector_allowed=segment_use in {SegmentUse.DRIVE_CONNECTOR.value, SegmentUse.EXIT_CONNECTOR.value},
            drive_connector_score=drive_preservation,
            transition_type="BUILD_TO_DROP" if transition_slope > 0.2 else "NONE",
        ),
        risk=RiskProfile(
            intro_like_score=intro_like,
            pulse_drop_score=pulse_drop,
            dropout_risk=0.08,
            breakdown_like_score=0.10,
            static_risk=0.08,
            chaos_risk=0.10,
            overpush_risk=max(0.0, degree - 0.80),
        ),
        block=BlockProfile(
            preferred_block_bars=16,
            min_hold_bars=16,
            min_hold_sec=30.0,
            stable_duration_sec=32.0,
            valid_runtime_block=True,
            phrase_confidence=0.82,
        ),
        combined_confidence=0.84,
    )
