from app.analysis.edm_pace_v3_core import (
    RunningSample,
    SessionHistory,
    SegmentUse,
    SpeedZone,
    V3Config,
    ZoneMemory,
    build_control_state,
    build_target_profile,
    classify_speed_zone,
    coverage_audit,
    hard_filter_connector,
    make_segment,
    metric_explain_ko,
    recommend_next_block,
)


def samples(speed, start=0, end=60):
    return [RunningSample(timestamp_sec=float(t), speed_kmh=float(speed)) for t in range(start, end + 1)]


def test_speed_zone_deadband_and_push_ranges():
    assert classify_speed_zone(0.00) == SpeedZone.STEADY_DEADBAND.value
    assert classify_speed_zone(0.049) == SpeedZone.STEADY_DEADBAND.value
    assert classify_speed_zone(0.08) == SpeedZone.LIGHT_PUSH.value
    assert classify_speed_zone(0.18) == SpeedZone.PUSH.value
    assert classify_speed_zone(0.30) == SpeedZone.STRONG_PUSH.value
    assert classify_speed_zone(0.38) == SpeedZone.RHYTHM_REBUILD.value
    assert classify_speed_zone(-0.08) == SpeedZone.LIGHT_CONTROL.value
    assert classify_speed_zone(-0.18) == SpeedZone.CONTROL.value
    assert classify_speed_zone(-0.30) == SpeedZone.DEEP_CONTROL.value


def test_control_window_uses_average_not_instant_spike():
    data = [RunningSample(t, 12.0) for t in range(0, 55)]
    data += [RunningSample(t, 8.0) for t in range(55, 61)]
    state, _ = build_control_state(data, target_speed_kmh=12.0, now_sec=60.0)
    assert state.current_speed_kmh == 8.0
    assert state.control_speed_kmh > 10.0
    assert abs(state.speed_gap_ratio) < 0.20


def test_target_profile_holds_in_steady_deadband():
    state, _ = build_control_state(samples(12.1), target_speed_kmh=12.0, now_sec=60.0)
    profile = build_target_profile(state, previous_target_music_speed_degree=0.50, elapsed_since_last_change_sec=90)
    assert profile.should_change_music is False
    assert profile.hold_reason == "within_steady_deadband"


def test_target_profile_changes_after_confirmed_push_zone():
    memory = ZoneMemory(
        active_speed_zone=SpeedZone.PUSH.value,
        candidate_speed_zone=SpeedZone.PUSH.value,
        candidate_since_sec=0.0,
        last_zone_change_sec=0.0,
    )
    state, _ = build_control_state(samples(10.0), target_speed_kmh=12.0, now_sec=60.0, memory=memory)
    profile = build_target_profile(state, previous_target_music_speed_degree=0.50, elapsed_since_last_change_sec=90)
    assert profile.should_change_music is True
    assert profile.target_music_speed_degree > 0.60


def test_pace_up_latency_policy_overrides_long_minimum_hold():
    memory = ZoneMemory(
        active_speed_zone=SpeedZone.PUSH.value,
        candidate_speed_zone=SpeedZone.PUSH.value,
        candidate_since_sec=0.0,
        last_zone_change_sec=0.0,
    )
    state, _ = build_control_state(samples(10.0), target_speed_kmh=12.0, now_sec=60.0, memory=memory)
    profile = build_target_profile(state, previous_target_music_speed_degree=0.50, elapsed_since_last_change_sec=10)
    assert profile.should_change_music is True
    assert profile.latency_route == "CHANGE_NOW"
    assert profile.estimated_change_latency_sec <= 10


def test_pace_up_forced_crossfade_keeps_latency_under_budget():
    config = V3Config(
        latency_policy={
            "pace_up_responsive": {
                "confirmation_sec": 3.0,
                "min_hold_sec": 7.0,
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
        }
    )
    memory = ZoneMemory(
        active_speed_zone=SpeedZone.PUSH.value,
        candidate_speed_zone=SpeedZone.PUSH.value,
        candidate_since_sec=59.0,
        last_zone_change_sec=0.0,
    )
    state, _ = build_control_state(samples(10.0), target_speed_kmh=12.0, now_sec=60.0, memory=memory, config=config)
    profile = build_target_profile(
        state,
        previous_target_music_speed_degree=0.50,
        elapsed_since_last_change_sec=0,
        near_phrase_boundary=False,
        config=config,
    )
    assert profile.should_change_music is True
    assert profile.latency_route == "FORCED_CROSSFADE"
    assert profile.forced_crossfade_used is True
    assert profile.estimated_change_latency_sec <= 10


def test_demo_fast_switching_latency_policy_is_under_three_seconds():
    config = V3Config(active_tuning_profile="demo_fast_switching")
    memory = ZoneMemory(
        active_speed_zone=SpeedZone.PUSH.value,
        candidate_speed_zone=SpeedZone.PUSH.value,
        candidate_since_sec=60.0,
        last_zone_change_sec=0.0,
    )
    state, _ = build_control_state(samples(10.0), target_speed_kmh=12.0, now_sec=60.0, memory=memory, config=config)
    profile = build_target_profile(
        state,
        previous_target_music_speed_degree=0.50,
        elapsed_since_last_change_sec=0,
        near_phrase_boundary=False,
        config=config,
    )
    assert profile.should_change_music is True
    assert profile.estimated_change_latency_sec <= 3
    assert profile.crossfade_sec <= 2


def test_intro_like_connector_is_blocked_runtime():
    memory = ZoneMemory(SpeedZone.PUSH.value, SpeedZone.PUSH.value, 0.0, 0.0)
    state, _ = build_control_state(samples(10.0), 12.0, now_sec=60.0, memory=memory)
    profile = build_target_profile(state, previous_target_music_speed_degree=0.50, elapsed_since_last_change_sec=90)
    connector = make_segment(
        "conn_bad",
        "track_a",
        0.64,
        segment_use=SegmentUse.DRIVE_CONNECTOR.value,
        transition_slope=0.4,
        intro_like=0.50,
    )
    reasons = hard_filter_connector(connector, profile)
    assert "intro_like_connector_blocked" in reasons


def test_recent_segment_hard_excluded_and_diversity_selects_other_track():
    memory = ZoneMemory(SpeedZone.PUSH.value, SpeedZone.PUSH.value, 0.0, 0.0)
    state, _ = build_control_state(samples(10.0), 12.0, now_sec=60.0, memory=memory)
    profile = build_target_profile(state, previous_target_music_speed_degree=0.50, elapsed_since_last_change_sec=90)
    current = make_segment("current", "track_a", 0.50)
    repeated = make_segment("repeat", "track_a", profile.target_music_speed_degree)
    fresh = make_segment("fresh", "track_b", profile.target_music_speed_degree - 0.01)
    history = SessionHistory(recent_track_ids=("track_a",), session_play_counts={"track_a": 2})
    result = recommend_next_block([repeated, fresh], profile, current, history)
    assert result.immediate_segment is not None
    assert result.immediate_segment.track_id == "track_b"


def test_big_direct_jump_uses_drive_connector_when_available():
    memory = ZoneMemory(SpeedZone.RHYTHM_REBUILD.value, SpeedZone.RHYTHM_REBUILD.value, 0.0, 0.0)
    state, _ = build_control_state(samples(7.0), 12.0, now_sec=60.0, memory=memory)
    profile = build_target_profile(state, previous_target_music_speed_degree=0.45, elapsed_since_last_change_sec=90)
    current = make_segment("current", "track_a", 0.30, end_degree=0.30)
    stable = make_segment("stable_high", "track_b", 0.82, start_degree=0.82)
    connector = make_segment(
        "conn_up",
        "track_c",
        0.68,
        segment_use=SegmentUse.DRIVE_CONNECTOR.value,
        start_degree=0.45,
        end_degree=0.72,
        transition_slope=0.55,
    )
    result = recommend_next_block([stable, connector], profile, current, SessionHistory())
    assert result.route_type == "CONNECTOR"
    assert result.immediate_segment.segment_id == "conn_up"
    assert result.target_segment.segment_id == "stable_high"


def test_coverage_audit_warns_sparse_bins():
    segs = [make_segment("s1", "track_a", 0.62), make_segment("s2", "track_a", 0.63)]
    audit = coverage_audit(segs)
    row = [r for r in audit if r.degree_bin == "0.60-0.70"][0]
    assert "stable_pool_too_small" in row.warnings
    assert "unique_track_count_too_small" in row.warnings


def test_metric_explanation_is_korean_and_thresholded():
    info = metric_explain_ko("intro_like_score", 0.51)
    assert info["level"] == "Block"
    assert "runtime" in info["recommendation_impact_ko"]
    assert "?댁꽍" not in info  # Structured data, not prose blob.
    assert "intro" in info["explanation_ko"]
