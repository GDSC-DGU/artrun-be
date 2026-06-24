"""
Pace Assist Analyzer v3.4 — AI + Signal Hybrid

Goal:
Select music segments that can actually help a runner adjust pace.

Core premise:
- "Fast music" is not the target.
- The target is an actionable, stable step cue that is slightly above the
  current music cue and within the runner's followable cadence range.

Layers:
1. Signal processing:
   onset envelope, tempogram/local tempo, beat/pulse regularity,
   Actionable Step Cue (ASC), dropout/half-time/fake-groove risks.

2. AI semantic interpretation:
   Optional CLAP/MERT/embedding hook + rule fallback.
   Scores concepts such as stable running groove, pace-up cue,
   half-time trap, cinematic breakdown, unclear cue, over-aggressive cue.

3. Runner context:
   current speed, target speed, current runner cadence,
   current music ASC, desired ASC lift.

4. Outcome learning:
   after 30/60 sec pace error reduction and skip/dislike feedback.

This module is dependency-light except the optional real-audio function, which
requires librosa. AI model calls are optional hooks so the service can run
without heavyweight dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Protocol, Sequence, Tuple
import json
import math
import statistics

import numpy as np


PACE_ASSIST_V3_4_FEATURE_KEYS = [
    "primary_ASC_spm",
    "ASC_strength",
    "ASC_stability",
    "pulse_clarity",
    "rhythm_predictability",
    "pulse_dropout_risk",
    "half_time_shift_risk",
    "fake_groove_risk",
    "AI_semantic_scores",
    "ai_semantic_provider",
    "ai_stable_running_groove",
    "ai_clear_step_cue",
    "ai_pace_up_cue",
    "ai_maintainable_drive",
    "ai_half_time_trap",
    "ai_cinematic_breakdown",
    "ai_beatless_bridge",
    "ai_fake_groove",
    "ai_too_aggressive",
    "ai_unclear_cue",
    "pace_assist_score",
    "pace_assist_v3_4_reject_reasons",
    "pace_assist_v3_4_score_breakdown",
    "pace_assist_v3_4_analysis_confidence",
    "start_ASC_spm",
    "mid_ASC_spm",
    "end_ASC_spm",
    "ASC_internal_range_spm",
    "user_response_effect",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def safe_mean(values: Sequence[float], default: float = 0.0) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return default
    return float(np.mean(arr))


def safe_std(values: Sequence[float], default: float = 0.0) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return default
    return float(np.std(arr))


def robust_normalize(values: Sequence[float]) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    if float(np.nanmin(arr)) >= 0.0 and float(np.nanmax(arr)) <= 1.01:
        return np.clip(arr, 0.0, 1.0)
    lo = float(np.percentile(arr, 5))
    hi = float(np.percentile(arr, 95))
    if hi - lo < 1e-9:
        return np.zeros_like(arr)
    return np.clip((arr - lo) / (hi - lo), 0.0, 1.0)


def rolling_mean(values: Sequence[float], window: int) -> np.ndarray:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0 or window <= 1:
        return arr
    window = min(window, arr.size)
    kernel = np.ones(window, dtype=float) / window
    return np.convolve(arr, kernel, mode="same")


def split_thirds(values: Sequence[float]) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    arr = np.asarray(values, dtype=float)
    if arr.size < 3:
        return arr, arr, arr
    n = arr.size
    return arr[: n // 3], arr[n // 3 : 2 * n // 3], arr[2 * n // 3 :]


def max_forward_drop(values: Sequence[float]) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size < 2:
        return 0.0
    running_max = np.maximum.accumulate(arr)
    return clamp(float(np.max(running_max - arr)))


def range_score(values: Sequence[float], scale: float) -> float:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0
    return clamp((float(np.max(arr)) - float(np.min(arr))) / max(scale, 1e-9))


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    x = np.asarray(a, dtype=float)
    y = np.asarray(b, dtype=float)
    if x.size == 0 or y.size == 0 or x.size != y.size:
        return 0.0
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    if denom <= 1e-12:
        return 0.0
    return float(np.dot(x, y) / denom)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

@dataclass
class PaceAssistConfig:
    # Cue lift by relative speed gap.
    hold_gap_max: float = 0.05
    mild_gap_max: float = 0.15
    medium_gap_max: float = 0.30

    mild_lift_pct: float = 0.025
    medium_lift_pct: float = 0.045
    strong_lift_pct: float = 0.065
    max_lift_pct: float = 0.07

    min_lift_from_current_music_spm: float = 2.0
    max_lift_from_current_music_spm: float = 8.0
    asc_tolerance_spm: float = 3.0

    # Hard gates.
    asc_strength_min: float = 0.65
    asc_stability_min: float = 0.70
    pulse_clarity_min: float = 0.55
    rhythm_predictability_min: float = 0.55
    pulse_dropout_max: float = 0.25
    half_time_risk_max: float = 0.25
    fake_groove_risk_max: float = 0.35
    overcue_risk_max: float = 0.35

    # AI semantic gates.
    ai_half_time_or_breakdown_max: float = 0.40
    ai_stable_groove_min_for_pace_up: float = 0.45
    ai_clear_step_cue_min_for_pace_up: float = 0.45

    # Scoring weights. Sum does not need to be exactly 1 because we clamp.
    w_numeric_cue_fit: float = 0.24
    w_asc_strength: float = 0.14
    w_asc_stability: float = 0.14
    w_pulse_clarity: float = 0.08
    w_rhythm_predictability: float = 0.08
    w_ai_pace_up: float = 0.12
    w_ai_stable_groove: float = 0.08
    w_user_response: float = 0.12

    w_overcue_risk: float = 0.16
    w_pulse_dropout_risk: float = 0.10
    w_half_time_risk: float = 0.10
    w_ai_negative: float = 0.14
    w_repetition_fatigue: float = 0.08


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class RunnerContext:
    current_speed_kmh: float
    target_speed_kmh: float
    current_runner_cadence_spm: Optional[float]
    current_music_asc_spm: float
    current_segment_id: Optional[str] = None
    current_track_id: Optional[str] = None


@dataclass
class PaceLiftTarget:
    state: str
    relative_gap: float
    cue_lift_pct: float
    current_runner_cadence_spm: float
    current_music_asc_spm: float
    desired_next_asc_spm: float
    min_candidate_asc_spm: float
    max_candidate_asc_spm: float
    reason: str


@dataclass
class AscCandidate:
    asc_spm: float
    strength: float
    stability: float
    source: str
    salience: float = 0.0
    start_spm: Optional[float] = None
    mid_spm: Optional[float] = None
    end_spm: Optional[float] = None


@dataclass
class SignalCueFeatures:
    segment_id: str = ""
    track_id: str = ""

    primary_asc_spm: float = 0.0
    asc_candidates: List[AscCandidate] = field(default_factory=list)

    asc_strength: float = 0.0
    asc_stability: float = 0.0
    pulse_clarity: float = 0.0
    beat_grid_confidence: float = 0.0
    rhythm_predictability: float = 0.0

    start_asc_spm: float = 0.0
    mid_asc_spm: float = 0.0
    end_asc_spm: float = 0.0
    asc_internal_range_spm: float = 0.0

    pulse_dropout_risk: float = 0.0
    half_time_shift_risk: float = 0.0
    fake_groove_risk: float = 0.0
    overcomplexity_risk: float = 0.0

    onset_density: float = 0.0
    rms_stability: float = 0.0
    segment_duration_sec: float = 0.0
    analysis_confidence: float = 0.0


@dataclass
class AISemanticScores:
    stable_running_groove: float = 0.0
    clear_step_cue: float = 0.0
    pace_up_cue: float = 0.0
    maintainable_drive: float = 0.0

    half_time_trap: float = 0.0
    cinematic_breakdown: float = 0.0
    beatless_bridge: float = 0.0
    fake_groove: float = 0.0
    too_aggressive: float = 0.0
    unclear_cue: float = 0.0

    ai_confidence: float = 0.0
    provider: str = "rule_fallback"


@dataclass
class SegmentPaceAssistFeatures:
    signal: SignalCueFeatures
    ai: AISemanticScores
    user_response_effect: float = 0.0
    repetition_fatigue: float = 0.0


@dataclass
class PaceAssistEvaluation:
    segment_id: str
    track_id: str
    pace_assist_score: float
    reject_reasons: List[str]
    score_breakdown: Dict[str, float]
    target: PaceLiftTarget
    selected_asc_spm: float
    asc_lift_from_current_music: float
    explanation_ko: Dict[str, str]


@dataclass
class PaceOutcomeRecord:
    segment_id: str
    track_id: str
    speed_state: str
    target_speed_kmh: float
    control_speed_before: float
    control_speed_after_30s: Optional[float] = None
    control_speed_after_60s: Optional[float] = None
    cadence_before_spm: Optional[float] = None
    cadence_after_30s_spm: Optional[float] = None
    cadence_after_60s_spm: Optional[float] = None
    user_skip: bool = False
    user_dislike: bool = False
    manual_bad_segment: bool = False


@dataclass
class SegmentOutcomeStats:
    segment_id: str
    track_id: str
    plays: int = 0
    avg_pace_error_reduction_30s: float = 0.0
    avg_pace_error_reduction_60s: float = 0.0
    skip_rate: float = 0.0
    dislike_rate: float = 0.0
    manual_bad_count: int = 0


# ---------------------------------------------------------------------------
# Runner context and target cue
# ---------------------------------------------------------------------------

def estimate_runner_cadence_spm(speed_kmh: float, fallback: float = 160.0) -> float:
    """
    Fallback only. Prefer actual cadence from phone/watch sensor.
    """
    s = float(speed_kmh)
    if s <= 0:
        return fallback
    if s < 6:
        return 120.0 + 5.0 * s          # 5 km/h -> 145
    if s < 10:
        return 145.0 + 5.0 * (s - 6.0)  # 8 km/h -> 155
    if s < 16:
        return 165.0 + 2.5 * (s - 10.0)
    return min(195.0, 180.0 + 1.0 * (s - 16.0))


def _cue_lift_pct(relative_gap: float, cfg: PaceAssistConfig) -> Tuple[str, float, str]:
    if relative_gap <= cfg.hold_gap_max:
        return "hold_or_stabilize", 0.0, "speed_sufficient_keep_or_stabilize"
    if relative_gap <= cfg.mild_gap_max:
        return "mild_lift", cfg.mild_lift_pct, "small_gap_apply_mild_cue_lift"
    if relative_gap <= cfg.medium_gap_max:
        return "medium_lift", cfg.medium_lift_pct, "moderate_gap_apply_medium_cue_lift"
    return "strong_lift", cfg.strong_lift_pct, "large_gap_apply_capped_strong_cue_lift"


def build_pace_lift_target(context: RunnerContext, cfg: PaceAssistConfig = PaceAssistConfig()) -> PaceLiftTarget:
    current_speed = max(float(context.current_speed_kmh), 0.1)
    target_speed = max(float(context.target_speed_kmh), 0.1)
    cadence = context.current_runner_cadence_spm or estimate_runner_cadence_spm(current_speed)
    relative_gap = (target_speed - current_speed) / current_speed

    state, lift_pct, reason = _cue_lift_pct(relative_gap, cfg)

    if state == "hold_or_stabilize":
        desired = context.current_music_asc_spm
        return PaceLiftTarget(
            state=state,
            relative_gap=relative_gap,
            cue_lift_pct=0.0,
            current_runner_cadence_spm=cadence,
            current_music_asc_spm=context.current_music_asc_spm,
            desired_next_asc_spm=desired,
            min_candidate_asc_spm=max(0.0, desired - cfg.asc_tolerance_spm),
            max_candidate_asc_spm=desired + cfg.asc_tolerance_spm,
            reason=reason,
        )

    lift_pct = min(lift_pct, cfg.max_lift_pct)
    cue_step = clamp(cadence * lift_pct, cfg.min_lift_from_current_music_spm, cfg.max_lift_from_current_music_spm)
    desired = context.current_music_asc_spm + cue_step
    cadence_cap = cadence * (1.0 + cfg.max_lift_pct)
    desired = min(desired, cadence_cap)

    return PaceLiftTarget(
        state=state,
        relative_gap=relative_gap,
        cue_lift_pct=lift_pct,
        current_runner_cadence_spm=cadence,
        current_music_asc_spm=context.current_music_asc_spm,
        desired_next_asc_spm=desired,
        min_candidate_asc_spm=max(context.current_music_asc_spm + cfg.min_lift_from_current_music_spm, desired - cfg.asc_tolerance_spm),
        max_candidate_asc_spm=min(cadence_cap, desired + cfg.asc_tolerance_spm),
        reason=reason,
    )


# ---------------------------------------------------------------------------
# Signal ASC extraction
# ---------------------------------------------------------------------------

def map_tempo_to_step_cue_candidates(tempo_bpm: float, min_spm: float = 105.0, max_spm: float = 205.0) -> List[float]:
    """
    A musical tempo can cue steps via beat, double-time, half-time, or 1.5x
    subdivisions. Keep hypotheses rather than assuming BPM == step cue.
    """
    if not np.isfinite(tempo_bpm) or tempo_bpm <= 0:
        return []
    multipliers = [0.5, 1.0, 1.5, 2.0]
    out = sorted({round(float(tempo_bpm) * m, 3) for m in multipliers if min_spm <= float(tempo_bpm) * m <= max_spm})
    return out


def autocorr_strength_at_spm(onset_env: Sequence[float], frame_rate: float, candidate_spm: float, tolerance: float = 0.08) -> float:
    x = robust_normalize(onset_env)
    if x.size < 4 or candidate_spm <= 0 or frame_rate <= 0:
        return 0.0

    x = x - np.mean(x)
    ac = np.correlate(x, x, mode="full")[x.size - 1 :]
    if ac.size == 0 or ac[0] <= 1e-12:
        return 0.0
    ac = ac / ac[0]

    period_sec = 60.0 / candidate_spm
    center_lag = period_sec * frame_rate
    lo = max(1, int(center_lag * (1.0 - tolerance)))
    hi = min(len(ac), int(center_lag * (1.0 + tolerance)) + 1)
    if hi <= lo:
        return 0.0
    return clamp(float(np.max(ac[lo:hi])))


def rhythm_predictability_from_onsets(onset_env: Sequence[float]) -> float:
    x = robust_normalize(onset_env)
    if x.size < 8:
        return 0.0
    smooth = rolling_mean(x, max(3, x.size // 32))
    residual = x - smooth
    regularity = safe_std(smooth) / (safe_std(smooth) + safe_std(residual) + 1e-9)
    return clamp(regularity)


def dropout_risk_from_curve(curve: Sequence[float]) -> float:
    x = robust_normalize(curve)
    if x.size < 4:
        return 0.0
    sm = rolling_mean(x, max(3, x.size // 16))
    return max_forward_drop(sm)


def half_time_shift_risk_from_asc_curve(asc_curve: Sequence[float], strength_curve: Sequence[float]) -> float:
    asc = np.asarray(asc_curve, dtype=float)
    strength = robust_normalize(strength_curve)
    if asc.size < 4:
        return 0.0
    a, b, c = split_thirds(asc)
    s1, s2, s3 = split_thirds(strength)

    early = safe_mean(a)
    later_min = min(safe_mean(b), safe_mean(c))
    if early <= 1e-9:
        return 0.0

    ratio = later_min / early
    half_like = clamp(1.0 - abs(ratio - 0.50) / 0.25)
    strength_drop = clamp(1.0 - min(safe_mean(s2), safe_mean(s3)) / max(safe_mean(s1), 1e-9))
    return clamp(0.65 * half_like + 0.35 * strength_drop)


def _dedupe_spm(candidates: Iterable[float], min_distance: float = 2.0) -> List[float]:
    sorted_values = sorted(float(x) for x in candidates if np.isfinite(x) and x > 0)
    out: List[float] = []
    for x in sorted_values:
        if not out or abs(x - out[-1]) > min_distance:
            out.append(x)
    return out


def build_asc_candidates(
    tempo_curve_bpm: Sequence[float],
    onset_env: Sequence[float],
    frame_rate: float,
    runner_cadence_spm: Optional[float] = None,
) -> List[AscCandidate]:
    tempos = np.asarray(tempo_curve_bpm, dtype=float)
    tempos = tempos[np.isfinite(tempos)]
    if tempos.size == 0:
        return []

    tempo_summaries = [
        float(np.percentile(tempos, 20)),
        float(np.median(tempos)),
        float(np.percentile(tempos, 80)),
    ]

    spm_hypotheses: List[float] = []
    for tempo in tempo_summaries:
        spm_hypotheses.extend(map_tempo_to_step_cue_candidates(tempo))

    spm_hypotheses = _dedupe_spm(spm_hypotheses)

    candidates: List[AscCandidate] = []
    for spm in spm_hypotheses:
        strength = autocorr_strength_at_spm(onset_env, frame_rate, spm)
        cadence_prior = 0.50
        if runner_cadence_spm:
            cadence_prior = clamp(1.0 - abs(spm - runner_cadence_spm) / 35.0)
        salience = clamp(0.75 * strength + 0.25 * cadence_prior)
        candidates.append(
            AscCandidate(
                asc_spm=spm,
                strength=strength,
                stability=0.0,
                source="tempo_hypothesis_autocorr",
                salience=salience,
            )
        )
    return candidates


def _choose_primary_candidate(
    candidates: Sequence[AscCandidate],
    runner_cadence_spm: Optional[float],
    current_music_asc_spm: Optional[float],
) -> AscCandidate:
    if not candidates:
        return AscCandidate(asc_spm=0.0, strength=0.0, stability=0.0, source="none")

    def score(c: AscCandidate) -> float:
        s = 0.48 * c.strength + 0.32 * c.stability + 0.20 * c.salience
        if runner_cadence_spm:
            s += 0.18 * clamp(1.0 - abs(c.asc_spm - runner_cadence_spm) / 30.0)
        if current_music_asc_spm and c.asc_spm > current_music_asc_spm:
            s += 0.04
        return s

    return max(candidates, key=score)


def _windowed_asc_curve(
    onset_env: Sequence[float],
    tempo_curve_bpm: Sequence[float],
    frame_rate: float,
    runner_cadence_spm: Optional[float],
    window_sec: float = 8.0,
    hop_sec: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray]:
    onset = np.asarray(onset_env, dtype=float)
    tempo = np.asarray(tempo_curve_bpm, dtype=float)
    n = min(onset.size, tempo.size)
    onset = onset[:n]
    tempo = tempo[:n]
    if n == 0:
        return np.asarray([]), np.asarray([])

    window_frames = min(n, max(4, int(window_sec * frame_rate)))
    hop_frames = max(1, int(hop_sec * frame_rate))

    asc_values: List[float] = []
    strength_values: List[float] = []
    for start in range(0, max(1, n - window_frames + 1), hop_frames):
        end = min(n, start + window_frames)
        cands = build_asc_candidates(tempo[start:end], onset[start:end], frame_rate, runner_cadence_spm)
        primary = _choose_primary_candidate(cands, runner_cadence_spm, None)
        asc_values.append(primary.asc_spm)
        strength_values.append(primary.strength)
        if end >= n:
            break

    return np.asarray(asc_values, dtype=float), np.asarray(strength_values, dtype=float)


def extract_signal_cue_features_from_curves(
    *,
    onset_env: Sequence[float],
    rms_curve: Sequence[float],
    tempo_curve_bpm: Sequence[float],
    frame_rate: float,
    segment_id: str = "",
    track_id: str = "",
    segment_duration_sec: float = 0.0,
    runner_cadence_spm: Optional[float] = None,
    current_music_asc_spm: Optional[float] = None,
) -> SignalCueFeatures:
    onset = robust_normalize(onset_env)
    rms = robust_normalize(rms_curve)
    tempo = np.asarray(tempo_curve_bpm, dtype=float)
    n = min(onset.size, rms.size, tempo.size)
    if n == 0:
        return SignalCueFeatures(segment_id=segment_id, track_id=track_id)

    onset = onset[:n]
    rms = rms[:n]
    tempo = tempo[:n]

    candidates = build_asc_candidates(tempo, onset, frame_rate, runner_cadence_spm)
    asc_curve, strength_curve = _windowed_asc_curve(onset, tempo, frame_rate, runner_cadence_spm)

    # Candidate stability: how often the local primary ASC is near that candidate.
    asc_range = 0.0
    if asc_curve.size:
        asc_range = float(np.max(asc_curve) - np.min(asc_curve))
        for c in candidates:
            local_hit_rate = float(np.mean(np.abs(asc_curve - c.asc_spm) <= 4.0))
            c.stability = clamp(local_hit_rate * (1.0 - min(asc_range / 35.0, 1.0)))

    primary = _choose_primary_candidate(candidates, runner_cadence_spm, current_music_asc_spm)
    if primary.stability == 0 and asc_curve.size:
        primary.stability = clamp(1.0 - asc_range / 25.0)

    a1, a2, a3 = split_thirds(asc_curve if asc_curve.size else [primary.asc_spm])
    start_asc = safe_mean(a1)
    mid_asc = safe_mean(a2)
    end_asc = safe_mean(a3)

    rhythm_predictability = rhythm_predictability_from_onsets(onset)
    pulse_dropout = clamp(0.70 * dropout_risk_from_curve(onset) + 0.30 * dropout_risk_from_curve(rms))
    half_time = half_time_shift_risk_from_asc_curve(asc_curve, strength_curve)
    fake_groove = clamp(0.45 * pulse_dropout + 0.35 * half_time + 0.20 * range_score(rms, 1.0))
    pulse_clarity = clamp(0.60 * safe_mean(strength_curve) + 0.25 * safe_mean(onset) + 0.15 * primary.strength)
    rms_stability = clamp(1.0 - range_score(rms, 1.0))

    confidence = clamp(
        0.25 * primary.strength
        + 0.25 * primary.stability
        + 0.18 * pulse_clarity
        + 0.17 * rhythm_predictability
        + 0.15 * (1.0 - pulse_dropout)
    )

    return SignalCueFeatures(
        segment_id=segment_id,
        track_id=track_id,
        primary_asc_spm=primary.asc_spm,
        asc_candidates=list(candidates),
        asc_strength=primary.strength,
        asc_stability=primary.stability,
        pulse_clarity=pulse_clarity,
        beat_grid_confidence=primary.strength,
        rhythm_predictability=rhythm_predictability,
        start_asc_spm=start_asc,
        mid_asc_spm=mid_asc,
        end_asc_spm=end_asc,
        asc_internal_range_spm=asc_range,
        pulse_dropout_risk=pulse_dropout,
        half_time_shift_risk=half_time,
        fake_groove_risk=fake_groove,
        overcomplexity_risk=clamp(1.0 - rhythm_predictability),
        onset_density=safe_mean(onset),
        rms_stability=rms_stability,
        segment_duration_sec=segment_duration_sec,
        analysis_confidence=confidence,
    )


def analyze_audio_segment_with_librosa(
    audio_path: str | Path,
    *,
    start_sec: float,
    end_sec: float,
    segment_id: str = "",
    track_id: str = "",
    runner_cadence_spm: Optional[float] = None,
    current_music_asc_spm: Optional[float] = None,
    sr: int = 22050,
    hop_length: int = 512,
) -> SignalCueFeatures:
    """
    Real audio segment analyzer.

    Requires librosa. Uses:
    - onset_strength for onset envelope
    - tempogram for local tempo hypotheses
    - beat_track fallback when tempogram is weak
    - RMS for dropout/fake-groove support
    """
    try:
        import librosa
    except ImportError as exc:
        raise ImportError("librosa is required. Install with: pip install librosa") from exc

    duration = max(end_sec - start_sec, 0.1)
    y, sr = librosa.load(str(audio_path), sr=sr, mono=True, offset=max(start_sec, 0.0), duration=duration)
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    rms = librosa.feature.rms(y=y, hop_length=hop_length)[0]

    tempogram = librosa.feature.tempogram(onset_envelope=onset_env, sr=sr, hop_length=hop_length)
    tempo_freqs = librosa.tempo_frequencies(tempogram.shape[0], hop_length=hop_length, sr=sr)

    if tempogram.shape[0] > 1 and tempogram.shape[1] > 0:
        valid_tg = tempogram[1:]
        valid_freqs = tempo_freqs[1:]
        dominant_idx = np.argmax(valid_tg, axis=0)
        local_tempo = valid_freqs[dominant_idx]
    else:
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length)
        tempo_value = float(np.asarray(tempo).reshape(-1)[0])
        local_tempo = np.full_like(onset_env, tempo_value, dtype=float)

    return extract_signal_cue_features_from_curves(
        onset_env=onset_env,
        rms_curve=rms[: len(onset_env)],
        tempo_curve_bpm=local_tempo[: len(onset_env)],
        frame_rate=sr / hop_length,
        segment_id=segment_id,
        track_id=track_id,
        segment_duration_sec=duration,
        runner_cadence_spm=runner_cadence_spm,
        current_music_asc_spm=current_music_asc_spm,
    )


# ---------------------------------------------------------------------------
# AI semantic layer
# ---------------------------------------------------------------------------

class AudioSemanticProvider(Protocol):
    def score_segment(self, *, audio_path: Optional[str], start_sec: float, end_sec: float, signal: SignalCueFeatures) -> AISemanticScores:
        ...


class RuleBasedSemanticProvider:
    """
    Always available fallback. This is not a replacement for CLAP/MERT; it
    provides AI-compatible semantic fields using signal features.
    """
    def score_segment(self, *, audio_path: Optional[str], start_sec: float, end_sec: float, signal: SignalCueFeatures) -> AISemanticScores:
        stable = clamp(0.45 * signal.asc_stability + 0.30 * signal.rhythm_predictability + 0.25 * (1.0 - signal.pulse_dropout_risk))
        clear = clamp(0.50 * signal.asc_strength + 0.30 * signal.pulse_clarity + 0.20 * signal.beat_grid_confidence)
        pace_up = clamp(0.45 * clear + 0.35 * stable + 0.20 * signal.analysis_confidence)
        maintainable = clamp(0.45 * stable + 0.30 * signal.pulse_clarity + 0.25 * signal.rms_stability)

        half_time = signal.half_time_shift_risk
        breakdown = clamp(0.50 * signal.pulse_dropout_risk + 0.30 * (1.0 - signal.pulse_clarity) + 0.20 * (1.0 - signal.rms_stability))
        beatless = clamp(0.60 * signal.pulse_dropout_risk + 0.40 * (1.0 - signal.asc_strength))
        fake = signal.fake_groove_risk
        aggressive = clamp(max(0.0, signal.primary_asc_spm - 185.0) / 25.0 + 0.35 * signal.overcomplexity_risk)
        unclear = clamp(1.0 - clear)

        return AISemanticScores(
            stable_running_groove=stable,
            clear_step_cue=clear,
            pace_up_cue=pace_up,
            maintainable_drive=maintainable,
            half_time_trap=half_time,
            cinematic_breakdown=breakdown,
            beatless_bridge=beatless,
            fake_groove=fake,
            too_aggressive=aggressive,
            unclear_cue=unclear,
            ai_confidence=signal.analysis_confidence,
            provider="rule_fallback",
        )


@dataclass
class EmbeddingSemanticProvider:
    """
    Generic embedding hook for CLAP/MERT-like systems.

    The caller supplies audio embedding and label embeddings.
    This keeps the core backend independent of heavy model installs.

    Expected labels:
    - good_pace_up_cue
    - stable_running_groove
    - clear_step_cue
    - maintainable_drive
    - half_time_trap
    - cinematic_breakdown
    - beatless_bridge
    - fake_groove
    - too_aggressive
    - unclear_cue
    """
    label_embeddings: Dict[str, Sequence[float]]
    audio_embeddings: Dict[str, Sequence[float]]
    provider_name: str = "embedding_provider"

    def _score(self, audio_key: str, label: str) -> float:
        if audio_key not in self.audio_embeddings or label not in self.label_embeddings:
            return 0.0
        sim = cosine_similarity(self.audio_embeddings[audio_key], self.label_embeddings[label])
        # Map cosine [-1,1] to [0,1].
        return clamp((sim + 1.0) / 2.0)

    def score_segment(self, *, audio_path: Optional[str], start_sec: float, end_sec: float, signal: SignalCueFeatures) -> AISemanticScores:
        key = signal.segment_id or f"{audio_path}:{start_sec}:{end_sec}"
        return AISemanticScores(
            stable_running_groove=self._score(key, "stable_running_groove"),
            clear_step_cue=self._score(key, "clear_step_cue"),
            pace_up_cue=self._score(key, "good_pace_up_cue"),
            maintainable_drive=self._score(key, "maintainable_drive"),
            half_time_trap=self._score(key, "half_time_trap"),
            cinematic_breakdown=self._score(key, "cinematic_breakdown"),
            beatless_bridge=self._score(key, "beatless_bridge"),
            fake_groove=self._score(key, "fake_groove"),
            too_aggressive=self._score(key, "too_aggressive"),
            unclear_cue=self._score(key, "unclear_cue"),
            ai_confidence=1.0,
            provider=self.provider_name,
        )


def combine_ai_scores(primary: AISemanticScores, fallback: AISemanticScores, ai_weight: float = 0.65) -> AISemanticScores:
    w = clamp(ai_weight)
    def mix(a: float, b: float) -> float:
        return clamp(w * a + (1.0 - w) * b)

    return AISemanticScores(
        stable_running_groove=mix(primary.stable_running_groove, fallback.stable_running_groove),
        clear_step_cue=mix(primary.clear_step_cue, fallback.clear_step_cue),
        pace_up_cue=mix(primary.pace_up_cue, fallback.pace_up_cue),
        maintainable_drive=mix(primary.maintainable_drive, fallback.maintainable_drive),
        half_time_trap=mix(primary.half_time_trap, fallback.half_time_trap),
        cinematic_breakdown=mix(primary.cinematic_breakdown, fallback.cinematic_breakdown),
        beatless_bridge=mix(primary.beatless_bridge, fallback.beatless_bridge),
        fake_groove=mix(primary.fake_groove, fallback.fake_groove),
        too_aggressive=mix(primary.too_aggressive, fallback.too_aggressive),
        unclear_cue=mix(primary.unclear_cue, fallback.unclear_cue),
        ai_confidence=clamp(w * primary.ai_confidence + (1.0 - w) * fallback.ai_confidence),
        provider=f"{primary.provider}+fallback",
    )


# ---------------------------------------------------------------------------
# Pace assist scoring
# ---------------------------------------------------------------------------

def cue_fit_score(candidate_spm: float, target: PaceLiftTarget) -> float:
    if target.state == "hold_or_stabilize":
        # For fast/enough state, avoid slow-down. Prefer cue near current music/current cadence.
        center = max(target.current_music_asc_spm, target.current_runner_cadence_spm * 0.96)
        return clamp(1.0 - abs(candidate_spm - center) / 10.0)

    if target.min_candidate_asc_spm <= candidate_spm <= target.max_candidate_asc_spm:
        return 1.0
    if candidate_spm < target.min_candidate_asc_spm:
        return clamp(1.0 - (target.min_candidate_asc_spm - candidate_spm) / 8.0)
    return clamp(1.0 - (candidate_spm - target.max_candidate_asc_spm) / 8.0)


def overcue_risk(candidate_spm: float, target: PaceLiftTarget, cfg: PaceAssistConfig) -> float:
    cap = target.current_runner_cadence_spm * (1.0 + cfg.max_lift_pct)
    if candidate_spm <= cap:
        return 0.0
    return clamp((candidate_spm - cap) / 12.0)


def too_weak_lift_risk(candidate_spm: float, target: PaceLiftTarget, cfg: PaceAssistConfig) -> float:
    if target.state == "hold_or_stabilize":
        return 0.0
    lift = candidate_spm - target.current_music_asc_spm
    if lift >= cfg.min_lift_from_current_music_spm:
        return 0.0
    return clamp((cfg.min_lift_from_current_music_spm - lift) / cfg.min_lift_from_current_music_spm)


def ai_negative_risk(ai: AISemanticScores) -> float:
    return clamp(max(
        ai.half_time_trap,
        ai.cinematic_breakdown,
        ai.beatless_bridge,
        ai.fake_groove,
        ai.too_aggressive,
        ai.unclear_cue * 0.7,
    ))


def evaluate_pace_assist_candidate(
    features: SegmentPaceAssistFeatures,
    context: RunnerContext,
    cfg: PaceAssistConfig = PaceAssistConfig(),
) -> PaceAssistEvaluation:
    target = build_pace_lift_target(context, cfg)
    signal = features.signal
    ai = features.ai
    candidate_spm = signal.primary_asc_spm
    lift = candidate_spm - target.current_music_asc_spm

    numeric_fit = cue_fit_score(candidate_spm, target)
    overcue = overcue_risk(candidate_spm, target, cfg)
    weak_lift = too_weak_lift_risk(candidate_spm, target, cfg)
    ai_neg = ai_negative_risk(ai)

    reject: List[str] = []
    if signal.asc_strength < cfg.asc_strength_min:
        reject.append("asc_strength_too_low")
    if signal.asc_stability < cfg.asc_stability_min:
        reject.append("asc_stability_too_low")
    if signal.pulse_clarity < cfg.pulse_clarity_min:
        reject.append("pulse_clarity_too_low")
    if signal.rhythm_predictability < cfg.rhythm_predictability_min:
        reject.append("rhythm_predictability_too_low")
    if signal.pulse_dropout_risk > cfg.pulse_dropout_max:
        reject.append("pulse_dropout_risk")
    if signal.half_time_shift_risk > cfg.half_time_risk_max:
        reject.append("half_time_shift_risk")
    if signal.fake_groove_risk > cfg.fake_groove_risk_max:
        reject.append("fake_groove_risk")
    if target.state != "hold_or_stabilize" and lift < cfg.min_lift_from_current_music_spm:
        reject.append("not_higher_than_current_music")
    if overcue > cfg.overcue_risk_max:
        reject.append("overcue_risk")
    if ai_neg > cfg.ai_half_time_or_breakdown_max:
        reject.append("ai_negative_semantic_risk")
    if target.state != "hold_or_stabilize" and ai.stable_running_groove < cfg.ai_stable_groove_min_for_pace_up:
        reject.append("ai_stable_groove_too_low")
    if target.state != "hold_or_stabilize" and ai.clear_step_cue < cfg.ai_clear_step_cue_min_for_pace_up:
        reject.append("ai_clear_step_cue_too_low")

    score = (
        cfg.w_numeric_cue_fit * numeric_fit
        + cfg.w_asc_strength * signal.asc_strength
        + cfg.w_asc_stability * signal.asc_stability
        + cfg.w_pulse_clarity * signal.pulse_clarity
        + cfg.w_rhythm_predictability * signal.rhythm_predictability
        + cfg.w_ai_pace_up * ai.pace_up_cue
        + cfg.w_ai_stable_groove * ai.stable_running_groove
        + cfg.w_user_response * features.user_response_effect
        - cfg.w_overcue_risk * overcue
        - cfg.w_pulse_dropout_risk * signal.pulse_dropout_risk
        - cfg.w_half_time_risk * signal.half_time_shift_risk
        - cfg.w_ai_negative * ai_neg
        - cfg.w_repetition_fatigue * features.repetition_fatigue
        - 0.06 * weak_lift
    )

    breakdown = {
        "numeric_cue_fit": numeric_fit,
        "asc_strength": signal.asc_strength,
        "asc_stability": signal.asc_stability,
        "pulse_clarity": signal.pulse_clarity,
        "rhythm_predictability": signal.rhythm_predictability,
        "ai_pace_up_cue": ai.pace_up_cue,
        "ai_stable_running_groove": ai.stable_running_groove,
        "user_response_effect": features.user_response_effect,
        "overcue_risk": overcue,
        "pulse_dropout_risk": signal.pulse_dropout_risk,
        "half_time_shift_risk": signal.half_time_shift_risk,
        "ai_negative_risk": ai_neg,
        "repetition_fatigue": features.repetition_fatigue,
        "too_weak_lift_risk": weak_lift,
    }

    explanation = {
        "selected_asc_spm": "후보 음악에서 러너가 발걸음 cue로 쓸 수 있는 주 반복 pulse입니다.",
        "asc_lift_from_current_music": "현재 음악 ASC보다 얼마나 높은 cue인지입니다. pace-up 상황에서는 최소 +2 SPM 이상이어야 합니다.",
        "numeric_cue_fit": "현재 cadence, 현재 음악 ASC, 목표 속도 gap을 기준으로 candidate ASC가 적절한지입니다.",
        "overcue_risk": "후보 cue가 현재 runner cadence보다 너무 높아 과도한 cue가 될 위험입니다.",
        "ai_negative_risk": "AI/semantic layer가 half-time, breakdown, fake groove, unclear cue로 판단한 위험입니다.",
    }

    return PaceAssistEvaluation(
        segment_id=signal.segment_id,
        track_id=signal.track_id,
        pace_assist_score=clamp(score),
        reject_reasons=reject,
        score_breakdown=breakdown,
        target=target,
        selected_asc_spm=candidate_spm,
        asc_lift_from_current_music=lift,
        explanation_ko=explanation,
    )


def build_segment_features(
    *,
    signal: SignalCueFeatures,
    ai_provider: Optional[AudioSemanticProvider] = None,
    audio_path: Optional[str] = None,
    start_sec: float = 0.0,
    end_sec: float = 0.0,
    user_response_effect: float = 0.0,
    repetition_fatigue: float = 0.0,
) -> SegmentPaceAssistFeatures:
    fallback = RuleBasedSemanticProvider().score_segment(
        audio_path=audio_path,
        start_sec=start_sec,
        end_sec=end_sec,
        signal=signal,
    )
    if ai_provider is None:
        ai = fallback
    else:
        primary = ai_provider.score_segment(audio_path=audio_path, start_sec=start_sec, end_sec=end_sec, signal=signal)
        ai = combine_ai_scores(primary, fallback)
    return SegmentPaceAssistFeatures(
        signal=signal,
        ai=ai,
        user_response_effect=clamp(user_response_effect),
        repetition_fatigue=clamp(repetition_fatigue),
    )


# ---------------------------------------------------------------------------
# Outcome learning
# ---------------------------------------------------------------------------

def pace_error(target_speed: float, actual_speed: Optional[float]) -> Optional[float]:
    if actual_speed is None:
        return None
    return abs(float(target_speed) - float(actual_speed))


def pace_error_reduction(target_speed: float, before: float, after: Optional[float]) -> Optional[float]:
    if after is None:
        return None
    return pace_error(target_speed, before) - pace_error(target_speed, after)


def outcome_effect_score(record: PaceOutcomeRecord) -> float:
    """
    Convert one outcome record to [0,1].

    0.50 = neutral
    >0.50 = helped
    <0.50 = hurt
    """
    red30 = pace_error_reduction(record.target_speed_kmh, record.control_speed_before, record.control_speed_after_30s)
    red60 = pace_error_reduction(record.target_speed_kmh, record.control_speed_before, record.control_speed_after_60s)

    vals = []
    if red30 is not None:
        vals.append(red30)
    if red60 is not None:
        vals.append(0.75 * red60)
    if not vals:
        base = 0.50
    else:
        # km/h improvement mapped conservatively: +1 km/h error reduction -> +0.25
        base = clamp(0.50 + 0.25 * safe_mean(vals), 0.0, 1.0)

    if record.user_skip:
        base -= 0.20
    if record.user_dislike:
        base -= 0.25
    if record.manual_bad_segment:
        base -= 0.35

    return clamp(base)


def update_segment_outcome_stats(stats: SegmentOutcomeStats, record: PaceOutcomeRecord) -> SegmentOutcomeStats:
    n = stats.plays
    effect30 = pace_error_reduction(record.target_speed_kmh, record.control_speed_before, record.control_speed_after_30s)
    effect60 = pace_error_reduction(record.target_speed_kmh, record.control_speed_before, record.control_speed_after_60s)

    new = SegmentOutcomeStats(**asdict(stats))
    new.plays += 1

    def update_avg(old: float, value: Optional[float]) -> float:
        if value is None:
            return old
        return (old * n + value) / (n + 1)

    new.avg_pace_error_reduction_30s = update_avg(stats.avg_pace_error_reduction_30s, effect30)
    new.avg_pace_error_reduction_60s = update_avg(stats.avg_pace_error_reduction_60s, effect60)
    new.skip_rate = (stats.skip_rate * n + (1.0 if record.user_skip else 0.0)) / (n + 1)
    new.dislike_rate = (stats.dislike_rate * n + (1.0 if record.user_dislike else 0.0)) / (n + 1)
    new.manual_bad_count = stats.manual_bad_count + (1 if record.manual_bad_segment else 0)
    return new


def user_response_effect_from_stats(stats: SegmentOutcomeStats) -> float:
    if stats.plays <= 0:
        return 0.50
    # Blend 30s and 60s improvements; penalize skips/dislikes/manual bad.
    improvement = 0.65 * stats.avg_pace_error_reduction_30s + 0.35 * stats.avg_pace_error_reduction_60s
    score = 0.50 + 0.25 * improvement - 0.20 * stats.skip_rate - 0.25 * stats.dislike_rate - 0.08 * stats.manual_bad_count
    return clamp(score)


# ---------------------------------------------------------------------------
# Public analysis/evaluation helper
# ---------------------------------------------------------------------------

def analyze_and_evaluate_audio_segment(
    *,
    audio_path: str | Path,
    start_sec: float,
    end_sec: float,
    context: RunnerContext,
    segment_id: str = "",
    track_id: str = "",
    ai_provider: Optional[AudioSemanticProvider] = None,
    user_response_effect: float = 0.50,
    repetition_fatigue: float = 0.0,
    cfg: PaceAssistConfig = PaceAssistConfig(),
) -> Dict[str, Any]:
    signal = analyze_audio_segment_with_librosa(
        audio_path,
        start_sec=start_sec,
        end_sec=end_sec,
        segment_id=segment_id,
        track_id=track_id,
        runner_cadence_spm=context.current_runner_cadence_spm,
        current_music_asc_spm=context.current_music_asc_spm,
    )
    features = build_segment_features(
        signal=signal,
        ai_provider=ai_provider,
        audio_path=str(audio_path),
        start_sec=start_sec,
        end_sec=end_sec,
        user_response_effect=user_response_effect,
        repetition_fatigue=repetition_fatigue,
    )
    evaluation = evaluate_pace_assist_candidate(features, context, cfg)
    return dataclass_to_jsonable({
        "signal": signal,
        "ai": features.ai,
        "evaluation": evaluation,
    })


def segment_features_to_metadata(
    features: SegmentPaceAssistFeatures,
    evaluation: PaceAssistEvaluation | None = None,
) -> Dict[str, Any]:
    signal = features.signal
    ai = features.ai
    score = evaluation.pace_assist_score if evaluation is not None else (
        0.24 * signal.asc_strength
        + 0.20 * signal.asc_stability
        + 0.14 * signal.pulse_clarity
        + 0.12 * signal.rhythm_predictability
        + 0.16 * ai.pace_up_cue
        + 0.14 * ai.stable_running_groove
        - 0.12 * signal.pulse_dropout_risk
        - 0.12 * signal.half_time_shift_risk
        - 0.10 * ai_negative_risk(ai)
    )
    ai_payload = dataclass_to_jsonable(ai)
    metadata: Dict[str, Any] = {
        "primary_ASC_spm": round(signal.primary_asc_spm, 4),
        "ASC_strength": round(signal.asc_strength, 4),
        "ASC_stability": round(signal.asc_stability, 4),
        "pulse_clarity": round(signal.pulse_clarity, 4),
        "rhythm_predictability": round(signal.rhythm_predictability, 4),
        "pulse_dropout_risk": round(signal.pulse_dropout_risk, 4),
        "half_time_shift_risk": round(signal.half_time_shift_risk, 4),
        "fake_groove_risk": round(signal.fake_groove_risk, 4),
        "AI_semantic_scores": ai_payload,
        "ai_semantic_provider": ai.provider,
        "ai_stable_running_groove": round(ai.stable_running_groove, 4),
        "ai_clear_step_cue": round(ai.clear_step_cue, 4),
        "ai_pace_up_cue": round(ai.pace_up_cue, 4),
        "ai_maintainable_drive": round(ai.maintainable_drive, 4),
        "ai_half_time_trap": round(ai.half_time_trap, 4),
        "ai_cinematic_breakdown": round(ai.cinematic_breakdown, 4),
        "ai_beatless_bridge": round(ai.beatless_bridge, 4),
        "ai_fake_groove": round(ai.fake_groove, 4),
        "ai_too_aggressive": round(ai.too_aggressive, 4),
        "ai_unclear_cue": round(ai.unclear_cue, 4),
        "pace_assist_score": round(clamp(score), 4),
        "pace_assist_v3_4_reject_reasons": list(evaluation.reject_reasons) if evaluation else [],
        "pace_assist_v3_4_score_breakdown": {
            key: round(float(value), 4) for key, value in (evaluation.score_breakdown if evaluation else {}).items()
        },
        "pace_assist_v3_4_analysis_confidence": round(signal.analysis_confidence, 4),
        "start_ASC_spm": round(signal.start_asc_spm, 4),
        "mid_ASC_spm": round(signal.mid_asc_spm, 4),
        "end_ASC_spm": round(signal.end_asc_spm, 4),
        "ASC_internal_range_spm": round(signal.asc_internal_range_spm, 4),
        "user_response_effect": round(features.user_response_effect, 4),
    }
    return metadata


def annotate_segments_with_pace_assist_v3_4(
    *,
    segments: Sequence[Any],
    audio_path: str | Path,
    ai_provider: Optional[AudioSemanticProvider] = None,
    runner_cadence_spm: float = 160.0,
) -> List[Any]:
    annotated: List[Any] = []
    for segment in segments:
        try:
            current_music_asc = max(105.0, float(getattr(segment, "bpm", 120.0)))
            signal = analyze_audio_segment_with_librosa(
                audio_path,
                start_sec=float(segment.start_sec),
                end_sec=float(segment.end_sec),
                segment_id=str(segment.segment_id),
                track_id=str(segment.track_id),
                runner_cadence_spm=runner_cadence_spm,
                current_music_asc_spm=current_music_asc,
            )
            features = build_segment_features(
                signal=signal,
                ai_provider=ai_provider,
                audio_path=str(audio_path),
                start_sec=float(segment.start_sec),
                end_sec=float(segment.end_sec),
                user_response_effect=0.50,
            )
            representative_context = RunnerContext(
                current_speed_kmh=8.0,
                target_speed_kmh=10.0,
                current_runner_cadence_spm=runner_cadence_spm,
                current_music_asc_spm=max(105.0, signal.primary_asc_spm - 4.0),
                current_segment_id=str(segment.segment_id),
                current_track_id=str(segment.track_id),
            )
            evaluation = evaluate_pace_assist_candidate(features, representative_context)
            metadata = segment_features_to_metadata(features, evaluation)
            annotated.append(replace(segment, metadata={**segment.metadata, **metadata}))
        except Exception as exc:
            fallback = {
                "primary_ASC_spm": round(float(getattr(segment, "bpm", 120.0)), 4),
                "ASC_strength": 0.0,
                "ASC_stability": 0.0,
                "pulse_clarity": 0.0,
                "rhythm_predictability": 0.0,
                "pulse_dropout_risk": 1.0,
                "half_time_shift_risk": 1.0,
                "fake_groove_risk": 1.0,
                "AI_semantic_scores": {"provider": "analysis_error"},
                "ai_semantic_provider": "analysis_error",
                "pace_assist_score": 0.0,
                "pace_assist_v3_4_reject_reasons": [f"analysis_error:{exc}"],
                "pace_assist_v3_4_score_breakdown": {},
                "pace_assist_v3_4_analysis_confidence": 0.0,
                "start_ASC_spm": 0.0,
                "mid_ASC_spm": 0.0,
                "end_ASC_spm": 0.0,
                "ASC_internal_range_spm": 0.0,
                "user_response_effect": 0.50,
            }
            annotated.append(replace(segment, metadata={**segment.metadata, **fallback}))
    return annotated


def dataclass_to_jsonable(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: dataclass_to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [dataclass_to_jsonable(v) for v in obj]
    if hasattr(obj, "__dataclass_fields__"):
        return {k: dataclass_to_jsonable(v) for k, v in asdict(obj).items()}
    return obj


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("audio_path")
    parser.add_argument("--start", type=float, default=0.0)
    parser.add_argument("--end", type=float, default=30.0)
    parser.add_argument("--current-speed", type=float, required=True)
    parser.add_argument("--target-speed", type=float, required=True)
    parser.add_argument("--current-music-asc", type=float, required=True)
    parser.add_argument("--cadence", type=float, default=0.0)
    parser.add_argument("--segment-id", default="")
    parser.add_argument("--track-id", default="")
    args = parser.parse_args()

    context = RunnerContext(
        current_speed_kmh=args.current_speed,
        target_speed_kmh=args.target_speed,
        current_runner_cadence_spm=args.cadence or None,
        current_music_asc_spm=args.current_music_asc,
    )
    payload = analyze_and_evaluate_audio_segment(
        audio_path=args.audio_path,
        start_sec=args.start,
        end_sec=args.end,
        context=context,
        segment_id=args.segment_id,
        track_id=args.track_id,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
