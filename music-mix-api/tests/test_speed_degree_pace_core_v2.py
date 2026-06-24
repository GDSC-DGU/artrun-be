from app.analysis.speed_degree_pace_core_v2 import (
    ModelFeatureScoresV2,
    RhythmSignalFeaturesV2,
    RunnerSpeedState,
    SegmentAnalysisV2,
    SegmentUse,
    StructureFieldsV2,
    TimbreEnergyFeaturesV2,
    TransitionType,
    build_pace_feature_vector_v2,
    build_target_music_profile_v2,
    connector_score_v2,
    stable_score_v2,
)


def make_analysis(segment_id="seg", segment_use="STABLE", transition_slope=0.0, effective_pulse=140.0, model_speed_degree=None):
    structure = StructureFieldsV2(
        segment_id=segment_id,
        track_id="track",
        start_sec=0.0,
        end_sec=30.0,
        start_bar=0,
        end_bar=16,
        duration_bars=16,
        segment_use=segment_use,
        transition_type=TransitionType.BUILD_TO_DROP.value if transition_slope > 0.25 else TransitionType.NONE.value,
        transition_slope=transition_slope,
        flow_direction="up" if transition_slope > 0.25 else "down" if transition_slope < -0.25 else "flat",
        entry_quality=0.82,
        exit_quality=0.80,
        phrase_confidence=0.86,
        is_contiguous_original_audio=True,
    )
    rhythm = RhythmSignalFeaturesV2(
        bpm=effective_pulse,
        effective_pulse_bpm=effective_pulse,
        pulse_relation="direct",
        beat_confidence=0.92,
        downbeat_confidence=0.86,
        cadence_lock_support=0.80,
        beat_salience_score=0.84,
        onset_density_score=0.74,
        rhythm_predictability_score=0.82,
        groove_stability_score=0.78,
        tempogram_strength_score=0.83,
    )
    timbre = TimbreEnergyFeaturesV2(
        bass_energy_score=0.72,
        bass_modulation_score=0.80,
        low_end_stability_score=0.76,
        loudness_density_score=0.62,
        loudness_change_score=0.18,
        spectral_brightness_score=0.63,
        brightness_change_score=0.20,
        static_loop_penalty=0.10,
        static_low_end_penalty=0.08,
        chaos_penalty=0.12,
    )
    model = ModelFeatureScoresV2(
        model_speed_degree=model_speed_degree,
        model_drive_score=0.76,
        model_groove_score=0.74,
        model_transition_score=0.80,
        model_stability_score=0.72,
        model_confidence=0.82 if model_speed_degree is not None else 0.0,
    )
    vector = build_pace_feature_vector_v2(structure=structure, rhythm=rhythm, timbre=timbre, model=model)
    return SegmentAnalysisV2(structure=structure, rhythm=rhythm, timbre=timbre, model=model, pace_vector=vector)


def test_target_music_speed_degree_changes_continuously_for_demo_speeds():
    target = 12.0
    speeds = [7.0, 10.0, 12.0, 15.0, 18.0]
    profiles = [build_target_music_profile_v2(RunnerSpeedState(current_speed_kmh=s, target_speed_kmh=target)) for s in speeds]
    degrees = [p.target_music_speed_degree for p in profiles]
    labels = [p.debug_intention_label for p in profiles]

    assert degrees[0] > degrees[1] > degrees[2] > degrees[3] > degrees[4]
    assert labels == ["rhythm_rebuild", "controlled_push", "steady", "recovery", "deep_recovery"]
    assert round(profiles[0].speed_gap_ratio, 3) == 0.417
    assert round(profiles[4].speed_gap_ratio, 3) == -0.5


def test_speed_trend_reduces_intervention_when_runner_is_recovering_speed():
    no_trend = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0))
    accelerating = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0, speed_20s_ago_kmh=9.5))

    assert accelerating.music_pace_control < no_trend.music_pace_control
    assert accelerating.target_music_speed_degree < no_trend.target_music_speed_degree


def test_music_speed_degree_uses_signal_only_without_model():
    analysis = make_analysis(model_speed_degree=None)

    assert analysis.pace_vector.fusion_weights["signal"] == 1.0
    assert 0.0 <= analysis.pace_vector.music_speed_degree <= 1.0
    assert analysis.pace_vector.model_confidence == 0.0


def test_music_speed_degree_uses_model_when_available():
    signal_only = make_analysis(model_speed_degree=None)
    with_model = make_analysis(model_speed_degree=0.90)

    assert with_model.pace_vector.fusion_weights["model"] > 0
    assert with_model.pace_vector.music_speed_degree > signal_only.pace_vector.music_speed_degree


def test_stable_score_prefers_segment_closer_to_target_degree():
    target = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0))
    close = make_analysis(segment_id="close", segment_use=SegmentUse.STABLE.value, model_speed_degree=target.target_music_speed_degree)
    far = make_analysis(segment_id="far", segment_use=SegmentUse.STABLE.value, model_speed_degree=0.15)

    close_score, close_debug = stable_score_v2(analysis=close, target=target)
    far_score, far_debug = stable_score_v2(analysis=far, target=target)

    assert close_score > far_score
    assert close_debug["music_speed_degree_match"] > far_debug["music_speed_degree_match"]


def test_connector_blocks_negative_slope_when_music_control_is_positive():
    target = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0))
    down_connector = make_analysis(segment_id="down", segment_use=SegmentUse.TRANSITION.value, transition_slope=-0.8, model_speed_degree=target.target_music_speed_degree)

    score, debug = connector_score_v2(analysis=down_connector, target=target)

    assert score == 0.0
    assert debug["reject_reason"] == "negative_transition_slope_blocked_for_positive_control"


def test_connector_scores_positive_slope_for_positive_control():
    target = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0))
    up_connector = make_analysis(segment_id="up", segment_use=SegmentUse.TRANSITION.value, transition_slope=0.75, model_speed_degree=target.target_music_speed_degree)

    score, debug = connector_score_v2(analysis=up_connector, target=target)

    assert score > 0.55
    assert "transition_slope_match" in debug


def test_reject_current_segment_hard_exclude():
    target = build_target_music_profile_v2(RunnerSpeedState(12.0, 12.0))
    analysis = make_analysis(segment_id="current", segment_use=SegmentUse.STABLE.value)

    score, debug = stable_score_v2(analysis=analysis, target=target, current_segment_id="current")

    assert score == 0.0
    assert debug["reject_reason"] == "current_segment_hard_exclude"


def test_entry_only_connector_blocked_during_runtime():
    target = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0))
    entry = make_analysis(
        segment_id="entry",
        segment_use=SegmentUse.ENTRY_ONLY.value,
        transition_slope=0.5,
        model_speed_degree=target.target_music_speed_degree,
    )

    runtime_score, runtime_debug = connector_score_v2(analysis=entry, target=target)
    initial_score, _ = connector_score_v2(analysis=entry, target=target, runtime_context="initial_entry")

    assert runtime_score == 0.0
    assert runtime_debug["reject_reason"] == "ENTRY_ONLY_blocked_during_runtime"
    assert initial_score > 0.0


def test_connector_rejects_low_drive_signals():
    target = build_target_music_profile_v2(RunnerSpeedState(10.0, 12.0))
    low_drive = make_analysis(
        segment_id="low_drive",
        segment_use=SegmentUse.TRANSITION.value,
        transition_slope=0.6,
        model_speed_degree=0.2,
    )
    low_drive = SegmentAnalysisV2(
        structure=low_drive.structure,
        rhythm=RhythmSignalFeaturesV2(
            bpm=low_drive.rhythm.bpm,
            effective_pulse_bpm=low_drive.rhythm.effective_pulse_bpm,
            pulse_relation=low_drive.rhythm.pulse_relation,
            beat_confidence=low_drive.rhythm.beat_confidence,
            downbeat_confidence=low_drive.rhythm.downbeat_confidence,
            cadence_lock_support=0.40,
            beat_salience_score=0.40,
            onset_density_score=low_drive.rhythm.onset_density_score,
            rhythm_predictability_score=low_drive.rhythm.rhythm_predictability_score,
            groove_stability_score=low_drive.rhythm.groove_stability_score,
            tempogram_strength_score=low_drive.rhythm.tempogram_strength_score,
        ),
        timbre=low_drive.timbre,
        model=low_drive.model,
        pace_vector=build_pace_feature_vector_v2(
            structure=low_drive.structure,
            rhythm=RhythmSignalFeaturesV2(
                bpm=low_drive.rhythm.bpm,
                effective_pulse_bpm=low_drive.rhythm.effective_pulse_bpm,
                pulse_relation=low_drive.rhythm.pulse_relation,
                beat_confidence=low_drive.rhythm.beat_confidence,
                downbeat_confidence=low_drive.rhythm.downbeat_confidence,
                cadence_lock_support=0.40,
                beat_salience_score=0.40,
                onset_density_score=low_drive.rhythm.onset_density_score,
                rhythm_predictability_score=low_drive.rhythm.rhythm_predictability_score,
                groove_stability_score=low_drive.rhythm.groove_stability_score,
                tempogram_strength_score=low_drive.rhythm.tempogram_strength_score,
            ),
            timbre=low_drive.timbre,
            model=low_drive.model,
        ),
    )

    score, debug = connector_score_v2(analysis=low_drive, target=target)

    assert score == 0.0
    assert debug["reject_reason"] in {"connector_low_beat_salience", "connector_low_cadence_lock"}
