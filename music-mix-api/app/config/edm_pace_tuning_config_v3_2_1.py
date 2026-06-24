"""
EDM Pace v3.2.1 tuning config layer.

Purpose:
- Move hard-coded thresholds/weights/ranges into versioned JSON config.
- Allow detailed fine tuning without rewriting recommendation or MIR code.
- Support admin UI sliders, A/B profiles, and threshold calibration from review labels.

Integrate this module before wiring final thresholds into:
- edm_pace_v3_1_core.py
- edm_mir_feature_extractor_v3_2.py
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict, replace
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


@dataclass
class SpeedZoneConfig:
    # speed_gap_ratio boundaries
    deep_control_max: float = -0.25
    control_max: float = -0.12
    light_control_max: float = -0.05
    steady_min: float = -0.05
    steady_max: float = 0.05
    light_push_max: float = 0.12
    push_max: float = 0.25
    strong_push_max: float = 0.35

    # preferred music_speed_degree by zone
    preferred_degree_ranges: Dict[str, Tuple[float, float]] = field(default_factory=lambda: {
        "deep_control": (0.15, 0.40),
        "control": (0.15, 0.40),
        "light_control": (0.35, 0.50),
        "steady_deadband": (0.45, 0.60),
        "light_push": (0.58, 0.72),
        "push": (0.65, 0.80),
        "strong_push": (0.75, 0.90),
        "rhythm_rebuild": (0.75, 0.90),
    })

    # control-window behavior
    control_window_sec: int = 30
    short_trend_window_sec: int = 10
    zone_confirmation_sec: int = 20
    min_music_hold_bars: int = 16
    min_music_hold_sec: int = 30
    target_degree_delta_threshold: float = 0.08

    # target degree formula
    music_pace_control_denominator: float = 0.35
    trend_weight: float = 0.50
    target_degree_center: float = 0.50
    target_degree_span: float = 0.35
    target_degree_min: float = 0.15
    target_degree_max: float = 0.85


@dataclass
class FakeGrooveThresholds:
    tempo_feel_drop_block: float = 0.35
    pulse_density_drop_block: float = 0.35
    drive_cliff_block: float = 0.35
    half_time_shift_block: float = 0.40
    internal_degree_range_block: float = 0.28
    effective_pulse_stability_min: float = 0.55
    min_internal_degree_margin: float = 0.25


@dataclass
class ConnectorThresholds:
    intro_like_block: float = 0.45
    pulse_drop_block: float = 0.35
    pulse_continuity_min: float = 0.60
    drive_preservation_min: float = 0.55
    cadence_lock_continuity_min: float = 0.55
    tempo_feel_drop_block: float = 0.35
    drive_cliff_block: float = 0.35


@dataclass
class DiversityConfig:
    recent_segment_hard_exclude_count: int = 10
    recent_track_cooldown_count: int = 4
    recent_track_penalty: float = -0.15
    same_degree_bin_repeat_penalty: float = -0.06
    same_section_label_repeat_penalty: float = -0.04
    same_transition_type_repeat_penalty: float = -0.04
    session_track_play_count_penalty_each: float = -0.03
    session_track_play_count_penalty_max: float = -0.12
    eligible_diversity_score_gap: float = 0.08
    softmax_temperature: float = 0.08
    use_weighted_rotation: bool = False


@dataclass
class CoverageConfig:
    degree_bin_size: float = 0.10
    stable_min_per_bin: int = 5
    stable_recommended_per_bin: int = 10
    connector_min_per_bin: int = 2
    connector_recommended_per_bin: int = 4
    unique_track_min_per_bin: int = 2
    unique_track_recommended_per_bin: int = 3


@dataclass
class ScoreWeights:
    music_speed_degree_match: float = 0.08
    speed_zone_contrast_score: float = 0.16
    current_to_candidate_smoothness: float = 0.13
    degree_step_smoothness: float = 0.10
    pulse_continuity_score: float = 0.11
    drive_preservation_score: float = 0.10
    cadence_lock_support: float = 0.08
    flow_momentum_score: float = 0.07
    block_stability_score: float = 0.07

    tempo_feel_drop_penalty: float = 0.14
    pulse_density_drop_penalty: float = 0.12
    drive_cliff_penalty: float = 0.12
    half_time_shift_penalty: float = 0.10
    intro_like_penalty: float = 0.08
    overpush_penalty: float = 0.06
    pace_assist_score: float = 0.34
    asc_cue_fit: float = 0.18
    asc_quality_score: float = 0.16
    asc_risk_safety: float = 0.12


@dataclass
class PaceAssistV34Config:
    asc_strength_min: float = 0.65
    asc_stability_min: float = 0.70
    pulse_clarity_min: float = 0.35
    rhythm_predictability_min: float = 0.10
    pulse_dropout_max: float = 0.25
    half_time_risk_max: float = 0.25
    fake_groove_risk_max: float = 0.35
    min_lift_from_current_music_spm: float = 2.0
    asc_tolerance_spm: float = 3.0
    max_cadence_overcue_pct: float = 0.07
    ai_negative_semantic_risk_max: float = 0.40
    fast_min_asc_floor_from_current_music: float = -1.0


@dataclass
class LatencyPolicyConfig:
    pace_up_confirmation_sec: float = 3.0
    pace_up_min_hold_sec: float = 3.0
    pace_up_boundary_max_wait_sec: float = 4.0
    pace_up_crossfade_sec: float = 2.0
    pace_up_max_change_latency_sec: float = 10.0
    pace_up_allowed_boundary_bars: float = 4.0
    demo_confirmation_sec: float = 0.0
    demo_min_hold_sec: float = 0.0
    demo_boundary_max_wait_sec: float = 1.0
    demo_crossfade_sec: float = 1.5
    demo_max_change_latency_sec: float = 3.0
    demo_allowed_boundary_bars: float = 1.0


@dataclass
class PaceTuningConfig:
    version: str = "v3.2.1"
    profile_name: str = "default"
    speed_zones: SpeedZoneConfig = field(default_factory=SpeedZoneConfig)
    fake_groove: FakeGrooveThresholds = field(default_factory=FakeGrooveThresholds)
    connector: ConnectorThresholds = field(default_factory=ConnectorThresholds)
    diversity: DiversityConfig = field(default_factory=DiversityConfig)
    coverage: CoverageConfig = field(default_factory=CoverageConfig)
    weights: ScoreWeights = field(default_factory=ScoreWeights)
    pace_assist_v3_4: PaceAssistV34Config = field(default_factory=PaceAssistV34Config)
    latency_policy: LatencyPolicyConfig = field(default_factory=LatencyPolicyConfig)


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, tuple):
        return list(obj)
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_to_jsonable(v) for v in obj]
    return obj


def save_config(config: PaceTuningConfig, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(_to_jsonable(config), ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def load_config(path: str | Path) -> PaceTuningConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return parse_config(data)


def parse_config(data: Dict[str, Any]) -> PaceTuningConfig:
    def tuple_ranges(d: Dict[str, Any]) -> Dict[str, Tuple[float, float]]:
        return {k: (float(v[0]), float(v[1])) for k, v in d.items()}

    speed_data = data.get("speed_zones", {})
    if "preferred_degree_ranges" in speed_data:
        speed_data = dict(speed_data)
        speed_data["preferred_degree_ranges"] = tuple_ranges(speed_data["preferred_degree_ranges"])

    return PaceTuningConfig(
        version=data.get("version", "v3.2.1"),
        profile_name=data.get("profile_name", "default"),
        speed_zones=SpeedZoneConfig(**speed_data),
        fake_groove=FakeGrooveThresholds(**data.get("fake_groove", {})),
        connector=ConnectorThresholds(**data.get("connector", {})),
        diversity=DiversityConfig(**data.get("diversity", {})),
        coverage=CoverageConfig(**data.get("coverage", {})),
        weights=ScoreWeights(**data.get("weights", {})),
        pace_assist_v3_4=PaceAssistV34Config(**data.get("pace_assist_v3_4", {})),
        latency_policy=LatencyPolicyConfig(**data.get("latency_policy", {})),
    )


def speed_zone_from_gap(speed_gap_ratio: float, config: SpeedZoneConfig) -> str:
    g = float(speed_gap_ratio)
    if g <= config.deep_control_max:
        return "deep_control"
    if g <= config.control_max:
        return "control"
    if g <= config.light_control_max:
        return "light_control"
    if config.steady_min <= g < config.steady_max:
        return "steady_deadband"
    if g < config.light_push_max:
        return "light_push"
    if g < config.push_max:
        return "push"
    if g < config.strong_push_max:
        return "strong_push"
    return "rhythm_rebuild"


def compute_target_music_degree(
    *,
    speed_gap_ratio: float,
    speed_trend_ratio: float,
    config: SpeedZoneConfig,
) -> Dict[str, Any]:
    control = clamp(
        (speed_gap_ratio - config.trend_weight * speed_trend_ratio)
        / max(config.music_pace_control_denominator, 1e-6),
        -1.0,
        1.0,
    )
    target_degree = clamp(
        config.target_degree_center + config.target_degree_span * control,
        config.target_degree_min,
        config.target_degree_max,
    )
    zone = speed_zone_from_gap(speed_gap_ratio, config)
    return {
        "speed_zone": zone,
        "music_pace_control": control,
        "target_music_speed_degree": target_degree,
        "preferred_degree_range": config.preferred_degree_ranges[zone],
    }


def fake_groove_reasons_from_values(values: Dict[str, float], config: FakeGrooveThresholds) -> List[str]:
    reasons: List[str] = []
    if values.get("tempo_feel_drop_score", 0.0) >= config.tempo_feel_drop_block:
        reasons.append("tempo_feel_drop")
    if values.get("pulse_density_drop_score", 0.0) >= config.pulse_density_drop_block:
        reasons.append("pulse_density_drop")
    if values.get("drive_cliff_score", 0.0) >= config.drive_cliff_block:
        reasons.append("drive_cliff")
    if values.get("half_time_shift_score", 0.0) >= config.half_time_shift_block:
        reasons.append("half_time_shift_risk")
    if values.get("internal_degree_range", 0.0) >= config.internal_degree_range_block:
        reasons.append("unstable_internal_speed_degree")
    if values.get("effective_pulse_stability", 1.0) < config.effective_pulse_stability_min:
        reasons.append("low_effective_pulse_stability")
    return reasons


def make_profile(base: PaceTuningConfig, profile_name: str, overrides: Dict[str, Any]) -> PaceTuningConfig:
    data = _to_jsonable(base)
    data["profile_name"] = profile_name

    def deep_update(dst: Dict[str, Any], src: Dict[str, Any]) -> None:
        for k, v in src.items():
            if isinstance(v, dict) and isinstance(dst.get(k), dict):
                deep_update(dst[k], v)
            else:
                dst[k] = v

    deep_update(data, overrides)
    return parse_config(data)


def default_profiles() -> Dict[str, PaceTuningConfig]:
    base = PaceTuningConfig()
    return {
        "default": base,
        "pace_up_responsive": make_profile(base, "pace_up_responsive", {
            "speed_zones": {
                "zone_confirmation_sec": 3,
                "min_music_hold_sec": 3
            },
            "latency_policy": {
                "pace_up_confirmation_sec": 3.0,
                "pace_up_min_hold_sec": 3.0,
                "pace_up_boundary_max_wait_sec": 4.0,
                "pace_up_crossfade_sec": 2.0,
                "pace_up_max_change_latency_sec": 10.0,
                "pace_up_allowed_boundary_bars": 4.0
            }
        }),
        "more_contrast": make_profile(base, "more_contrast", {
            "speed_zones": {
                "preferred_degree_ranges": {
                    "deep_control": [0.12, 0.35],
                    "control": [0.15, 0.36],
                    "light_control": [0.30, 0.46],
                    "steady_deadband": [0.44, 0.58],
                    "light_push": [0.60, 0.74],
                    "push": [0.68, 0.83],
                    "strong_push": [0.78, 0.92],
                    "rhythm_rebuild": [0.80, 0.95]
                }
            },
            "weights": {
                "speed_zone_contrast_score": 0.22,
                "music_speed_degree_match": 0.15
            }
        }),
        "strict_no_fake_groove": make_profile(base, "strict_no_fake_groove", {
            "fake_groove": {
                "tempo_feel_drop_block": 0.28,
                "pulse_density_drop_block": 0.28,
                "drive_cliff_block": 0.28,
                "half_time_shift_block": 0.35,
                "internal_degree_range_block": 0.22,
                "effective_pulse_stability_min": 0.62
            },
            "pace_assist_v3_4": {
                "fake_groove_risk_max": 0.28,
                "pulse_dropout_max": 0.22,
                "half_time_risk_max": 0.22,
                "ai_negative_semantic_risk_max": 0.35
            }
        }),
        "less_repetition": make_profile(base, "less_repetition", {
            "diversity": {
                "recent_segment_hard_exclude_count": 12,
                "recent_track_cooldown_count": 5,
                "recent_track_penalty": -0.22,
                "session_track_play_count_penalty_each": -0.05,
                "session_track_play_count_penalty_max": -0.20,
                "eligible_diversity_score_gap": 0.10
            }
        }),
        "demo_fast_switching": make_profile(base, "demo_fast_switching", {
            "speed_zones": {
                "zone_confirmation_sec": 0,
                "min_music_hold_bars": 0,
                "min_music_hold_sec": 0,
                "target_degree_delta_threshold": 0.02
            },
            "pace_assist_v3_4": {
                "asc_tolerance_spm": 4.5
            },
            "latency_policy": {
                "demo_confirmation_sec": 0.0,
                "demo_min_hold_sec": 0.0,
                "demo_boundary_max_wait_sec": 0.5,
                "demo_crossfade_sec": 1.5,
                "demo_max_change_latency_sec": 3.0,
                "demo_allowed_boundary_bars": 1.0
            }
        }),
    }


def write_default_profile_files(out_dir: str | Path) -> List[str]:
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths: List[str] = []
    for name, cfg in default_profiles().items():
        path = save_config(cfg, root / f"{name}.json")
        paths.append(str(path))
    return paths


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="data/config/pace_tuning_profiles")
    args = parser.parse_args()
    for p in write_default_profile_files(args.out_dir):
        print(p)
