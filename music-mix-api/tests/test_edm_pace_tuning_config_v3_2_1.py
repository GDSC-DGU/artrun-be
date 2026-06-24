from app.config.edm_pace_tuning_config_v3_2_1 import (
    PaceTuningConfig,
    compute_target_music_degree,
    fake_groove_reasons_from_values,
    default_profiles,
    save_config,
    load_config,
)


def test_default_target_degree_is_clamped():
    cfg = PaceTuningConfig()
    out = compute_target_music_degree(speed_gap_ratio=10, speed_trend_ratio=-10, config=cfg.speed_zones)
    assert -1 <= out["music_pace_control"] <= 1
    assert 0.15 <= out["target_music_speed_degree"] <= 0.85


def test_more_contrast_profile_changes_ranges():
    profiles = default_profiles()
    default_push = profiles["default"].speed_zones.preferred_degree_ranges["rhythm_rebuild"]
    contrast_push = profiles["more_contrast"].speed_zones.preferred_degree_ranges["rhythm_rebuild"]
    assert contrast_push[0] > default_push[0]


def test_strict_fake_groove_profile_rejects_earlier():
    profiles = default_profiles()
    values = {
        "tempo_feel_drop_score": 0.30,
        "pulse_density_drop_score": 0.0,
        "drive_cliff_score": 0.0,
        "half_time_shift_score": 0.0,
        "internal_degree_range": 0.0,
        "effective_pulse_stability": 0.8,
    }
    assert fake_groove_reasons_from_values(values, profiles["default"].fake_groove) == []
    assert "tempo_feel_drop" in fake_groove_reasons_from_values(values, profiles["strict_no_fake_groove"].fake_groove)


def test_save_load_roundtrip(tmp_path):
    cfg = default_profiles()["less_repetition"]
    p = save_config(cfg, tmp_path / "less_repetition.json")
    loaded = load_config(p)
    assert loaded.profile_name == "less_repetition"
    assert loaded.diversity.recent_track_penalty == -0.22
