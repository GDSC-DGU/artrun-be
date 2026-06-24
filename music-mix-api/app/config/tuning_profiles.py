from __future__ import annotations

import json
import shutil
from dataclasses import asdict
from pathlib import Path
from typing import Any

from app.analysis.edm_pace_v3_core import V3Config
from app.config.edm_pace_tuning_config_v3_2_1 import (
    PaceTuningConfig,
    default_profiles,
    load_config,
    save_config,
)
from app.paths import DATA_DIR


PROFILE_DIR = DATA_DIR / "config" / "pace_tuning_profiles"
ACTIVE_PROFILE_PATH = DATA_DIR / "config" / "active_tuning_profile.json"
PACKAGED_PROFILE_DIR = Path(__file__).resolve().parents[2] / "data" / "config" / "pace_tuning_profiles"


def ensure_tuning_profiles() -> None:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    ACTIVE_PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    for name, config in default_profiles().items():
        path = PROFILE_DIR / f"{name}.json"
        if not path.exists():
            save_config(config, path)
    if not ACTIVE_PROFILE_PATH.exists():
        ACTIVE_PROFILE_PATH.write_text(json.dumps({"active_profile": "default"}, indent=2), encoding="utf-8")


def list_profile_names() -> list[str]:
    ensure_tuning_profiles()
    return sorted(path.stem for path in PROFILE_DIR.glob("*.json"))


def active_profile_name() -> str:
    ensure_tuning_profiles()
    try:
        payload = json.loads(ACTIVE_PROFILE_PATH.read_text(encoding="utf-8"))
        name = str(payload.get("active_profile") or "default")
    except Exception:
        name = "default"
    if name not in list_profile_names():
        return "default"
    return name


def profile_path(profile_name: str) -> Path:
    safe_name = Path(profile_name).stem
    return PROFILE_DIR / f"{safe_name}.json"


def load_tuning_profile(profile_name: str | None = None) -> PaceTuningConfig:
    ensure_tuning_profiles()
    name = profile_name or active_profile_name()
    path = profile_path(name)
    if not path.exists():
        raise FileNotFoundError(f"Unknown tuning profile: {name}")
    return load_config(path)


def load_active_tuning_profile() -> PaceTuningConfig:
    return load_tuning_profile(active_profile_name())


def activate_profile(profile_name: str) -> PaceTuningConfig:
    config = load_tuning_profile(profile_name)
    ACTIVE_PROFILE_PATH.write_text(
        json.dumps({"active_profile": config.profile_name}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config


def save_profile(profile_name: str, payload: dict[str, Any]) -> PaceTuningConfig:
    from app.config.edm_pace_tuning_config_v3_2_1 import parse_config

    config = parse_config({**payload, "profile_name": profile_name})
    save_config(config, profile_path(profile_name))
    return config


def reset_profile(profile_name: str) -> PaceTuningConfig:
    defaults = default_profiles()
    if profile_name not in defaults:
        raise FileNotFoundError(f"No built-in default for tuning profile: {profile_name}")
    config = defaults[profile_name]
    save_config(config, profile_path(profile_name))
    return config


def tuning_profile_payload(config: PaceTuningConfig) -> dict[str, Any]:
    def jsonable(value: Any) -> Any:
        if isinstance(value, tuple):
            return list(value)
        if isinstance(value, dict):
            return {key: jsonable(item) for key, item in value.items()}
        if isinstance(value, list):
            return [jsonable(item) for item in value]
        return value

    return jsonable(asdict(config))


def v3_config_from_tuning(config: PaceTuningConfig) -> V3Config:
    zones = config.speed_zones
    connector = config.connector
    diversity = config.diversity
    coverage = config.coverage
    weights = config.weights
    fake = config.fake_groove
    pace34 = config.pace_assist_v3_4
    latency = config.latency_policy

    return V3Config(
        active_tuning_profile=config.profile_name,
        speed_zone_boundaries={
            "deep_control_max": zones.deep_control_max,
            "control_max": zones.control_max,
            "light_control_max": zones.light_control_max,
            "steady_min": zones.steady_min,
            "steady_max": zones.steady_max,
            "light_push_max": zones.light_push_max,
            "push_max": zones.push_max,
            "strong_push_max": zones.strong_push_max,
        },
        preferred_degree_ranges=zones.preferred_degree_ranges,
        control_window_sec=float(zones.control_window_sec),
        previous_control_window_sec=float(zones.control_window_sec),
        short_trend_window_sec=float(zones.short_trend_window_sec),
        steady_deadband_ratio=max(abs(zones.steady_min), abs(zones.steady_max)),
        zone_change_confirm_sec=float(zones.zone_confirmation_sec),
        zone_return_confirm_sec=float(zones.zone_confirmation_sec),
        stable_hold_bars_min=int(zones.min_music_hold_bars),
        min_hold_sec=float(zones.min_music_hold_sec),
        target_degree_change_threshold=zones.target_degree_delta_threshold,
        music_pace_control_divisor=zones.music_pace_control_denominator,
        trend_compensation=zones.trend_weight,
        target_degree_center=zones.target_degree_center,
        target_degree_span=zones.target_degree_span,
        target_degree_min=zones.target_degree_min,
        target_degree_max=zones.target_degree_max,
        connector_intro_like_block=connector.intro_like_block,
        connector_pulse_drop_block=connector.pulse_drop_block,
        connector_pulse_continuity_min=connector.pulse_continuity_min,
        connector_drive_preservation_min=connector.drive_preservation_min,
        connector_cadence_lock_continuity_min=connector.cadence_lock_continuity_min,
        degree_bin_size=coverage.degree_bin_size,
        min_stable_candidates_per_bin=coverage.stable_min_per_bin,
        min_connector_candidates_per_bin=coverage.connector_min_per_bin,
        ideal_stable_candidates_per_bin=coverage.stable_recommended_per_bin,
        ideal_connector_candidates_per_bin=coverage.connector_recommended_per_bin,
        min_unique_tracks_per_bin=coverage.unique_track_min_per_bin,
        ideal_unique_tracks_per_bin=coverage.unique_track_recommended_per_bin,
        controlled_diversity_score_margin=diversity.eligible_diversity_score_gap,
        recent_track_cooldown_count=diversity.recent_track_cooldown_count,
        recent_track_penalty=abs(diversity.recent_track_penalty),
        same_degree_bin_penalty=abs(diversity.same_degree_bin_repeat_penalty),
        same_section_label_penalty=abs(diversity.same_section_label_repeat_penalty),
        session_play_count_penalty=abs(diversity.session_track_play_count_penalty_each),
        session_play_count_penalty_max=abs(diversity.session_track_play_count_penalty_max),
        fake_groove_thresholds={
            "tempo_feel_drop_block": fake.tempo_feel_drop_block,
            "pulse_density_drop_block": fake.pulse_density_drop_block,
            "drive_cliff_block": fake.drive_cliff_block,
            "half_time_shift_block": fake.half_time_shift_block,
            "internal_degree_range_block": fake.internal_degree_range_block,
            "effective_pulse_stability_min": fake.effective_pulse_stability_min,
            "min_internal_degree_margin": fake.min_internal_degree_margin,
        },
        score_weights={
            "music_speed_degree_match": weights.music_speed_degree_match,
            "speed_zone_contrast_score": weights.speed_zone_contrast_score,
            "current_to_candidate_smoothness": weights.current_to_candidate_smoothness,
            "degree_step_smoothness": weights.degree_step_smoothness,
            "pulse_continuity_score": weights.pulse_continuity_score,
            "drive_preservation_score": weights.drive_preservation_score,
            "cadence_lock_support": weights.cadence_lock_support,
            "flow_momentum_score": weights.flow_momentum_score,
            "block_stability_score": weights.block_stability_score,
            "pulse_drop_penalty": weights.pulse_density_drop_penalty,
            "intro_like_penalty": weights.intro_like_penalty,
            "overpush_penalty": weights.overpush_penalty,
            "pace_assist_score": weights.pace_assist_score,
            "asc_cue_fit": weights.asc_cue_fit,
            "asc_quality_score": weights.asc_quality_score,
            "asc_risk_safety": weights.asc_risk_safety,
        },
        pace_assist_v3_4={
            "asc_strength_min": pace34.asc_strength_min,
            "asc_stability_min": pace34.asc_stability_min,
            "pulse_clarity_min": pace34.pulse_clarity_min,
            "rhythm_predictability_min": pace34.rhythm_predictability_min,
            "pulse_dropout_max": pace34.pulse_dropout_max,
            "half_time_risk_max": pace34.half_time_risk_max,
            "fake_groove_risk_max": pace34.fake_groove_risk_max,
            "min_lift_from_current_music_spm": pace34.min_lift_from_current_music_spm,
            "asc_tolerance_spm": pace34.asc_tolerance_spm,
            "max_cadence_overcue_pct": pace34.max_cadence_overcue_pct,
            "ai_negative_semantic_risk_max": pace34.ai_negative_semantic_risk_max,
            "fast_min_asc_floor_from_current_music": pace34.fast_min_asc_floor_from_current_music,
        },
        latency_policy={
            "pace_up_responsive": {
                "confirmation_sec": latency.pace_up_confirmation_sec,
                "min_hold_sec": latency.pace_up_min_hold_sec,
                "boundary_max_wait_sec": latency.pace_up_boundary_max_wait_sec,
                "crossfade_sec": latency.pace_up_crossfade_sec,
                "max_change_latency_sec": latency.pace_up_max_change_latency_sec,
                "allowed_boundary_bars": latency.pace_up_allowed_boundary_bars,
            },
            "demo_fast_switching": {
                "confirmation_sec": latency.demo_confirmation_sec,
                "min_hold_sec": latency.demo_min_hold_sec,
                "boundary_max_wait_sec": latency.demo_boundary_max_wait_sec,
                "crossfade_sec": latency.demo_crossfade_sec,
                "max_change_latency_sec": latency.demo_max_change_latency_sec,
                "allowed_boundary_bars": latency.demo_allowed_boundary_bars,
            },
        },
    )


def load_active_v3_config() -> V3Config:
    return v3_config_from_tuning(load_active_tuning_profile())
