from app.analysis.multi_model_pace_feature_core import *


def make_segment(segment_use="STABLE", flow="flat", transition_type="NONE", mert=True, semantic=False):
    structure = StructureFields(
        "seg1",
        "track1",
        0,
        30,
        0,
        16,
        16,
        segment_use,
        transition_type,
        flow,
        "drop" if transition_type == "BUILD_TO_DROP" else None,
        0.82,
        0.78,
        0.86,
        True,
    )
    rhythm = RhythmSignalFeatures(140, 140, "direct", 0.92, 0.85, 0.86, 0.74, 0.81, 0.77, 0.83)
    timbre = TimbreEnergyFeatures(0.72, 0.80, 0.76, 0.68, 0.22, 0.64, 0.31, 0.12, 0.08, 0.15)
    mert_scores = MERTScores(
        "mert1" if mert else None,
        drive_score=0.78 if mert else None,
        groove_score=0.73 if mert else None,
        transition_score=0.81 if mert else None,
        stability_score=0.69 if mert else None,
        confidence=0.82 if mert else None,
    )
    sem = SemanticScores(
        semantic,
        {
            "steady_running_groove": 0.66,
            "pace_up_driving_section": 0.82,
            "sprint_push_drop": 0.74,
            "recovery_control_section": 0.18,
            "build_up_to_drop_transition": 0.87,
            "chaotic_unstable_section": 0.12,
            "static_low_drive_loop": 0.09,
        }
        if semantic
        else {},
        0.78 if semantic else None,
    )
    vector = fuse_pace_feature_vector(structure=structure, rhythm=rhythm, timbre=timbre, mert=mert_scores, semantic=sem)
    return SegmentAnalysis(structure, rhythm, timbre, mert_scores, sem, vector)


def test_target_music_profile_pace_up():
    profile = build_target_music_profile(RunnerState(330, 300, 168))
    assert profile.running_intention == "pace_up"
    assert profile.assist_degree > 0.5
    assert profile.target_transition_direction == "up"


def test_fusion_uses_signal_only_when_mert_missing():
    analysis = make_segment(mert=False, semantic=False)
    assert analysis.pace_vector.fusion_weights["signal"] == 1.0
    assert analysis.pace_vector.model_confidence == 0.0
    assert analysis.pace_vector.combined_confidence > 0.5


def test_fusion_uses_multiple_models_when_available():
    analysis = make_segment(mert=True, semantic=True)
    assert analysis.pace_vector.fusion_weights["signal"] > 0
    assert analysis.pace_vector.fusion_weights["mert"] > 0
    assert analysis.pace_vector.fusion_weights["semantic"] > 0
    assert analysis.pace_vector.pace_push_score > 0.6


def test_stable_match_for_pace_up():
    profile = build_target_music_profile(RunnerState(330, 300, 168))
    analysis = make_segment(segment_use="STABLE")
    score, breakdown = stable_match_score(analysis=analysis, target=profile)
    assert score > 0.5
    assert "final_score" in breakdown


def test_connector_match_blocks_down_transition_for_pace_up():
    profile = build_target_music_profile(RunnerState(330, 300, 168))
    analysis = make_segment(segment_use="TRANSITION", flow="down", transition_type=TransitionType.DROP_TO_BREAKDOWN.value)
    score, breakdown = connector_match_score(analysis=analysis, target=profile)
    assert score == 0.0
    assert breakdown["reject_reason"] == "down_transition_blocked_for_upward_intention"


def test_connector_match_build_to_drop_for_pace_up():
    profile = build_target_music_profile(RunnerState(330, 300, 168))
    analysis = make_segment(segment_use="TRANSITION", flow="up", transition_type=TransitionType.BUILD_TO_DROP.value, semantic=True)
    score, breakdown = connector_match_score(analysis=analysis, target=profile)
    assert score > 0.55
    assert "transition_usefulness_score" in breakdown


def test_recommend_route_can_return_connector():
    profile = build_target_music_profile(RunnerState(330, 300, 168))
    connector = make_segment(segment_use="TRANSITION", flow="up", transition_type=TransitionType.BUILD_TO_DROP.value, semantic=True)
    stable = make_segment(segment_use="STABLE", semantic=True)
    route = recommend_route(analyses=[connector, stable], target=profile)
    assert route.route_type in {"DIRECT", "CONNECTOR"}
    assert route.immediate_segment is not None
    assert route.target_segment is not None
