from app.analysis.pace_assist_analyzer_v3_4 import (
    RunnerContext,
    PaceOutcomeRecord,
    SegmentOutcomeStats,
    SignalCueFeatures,
    AISemanticScores,
    SegmentPaceAssistFeatures,
    build_pace_lift_target,
    evaluate_pace_assist_candidate,
    extract_signal_cue_features_from_curves,
    outcome_effect_score,
    update_segment_outcome_stats,
    user_response_effect_from_stats,
    RuleBasedSemanticProvider,
)


def test_current_music_asc_lift_is_required_for_slow_state():
    ctx = RunnerContext(current_speed_kmh=8, target_speed_kmh=10, current_runner_cadence_spm=160, current_music_asc_spm=158)
    signal = SignalCueFeatures(
        segment_id="weak",
        primary_asc_spm=159,
        asc_strength=0.9,
        asc_stability=0.9,
        pulse_clarity=0.9,
        rhythm_predictability=0.9,
        analysis_confidence=0.9,
    )
    ai = RuleBasedSemanticProvider().score_segment(audio_path=None, start_sec=0, end_sec=30, signal=signal)
    features = SegmentPaceAssistFeatures(signal=signal, ai=ai, user_response_effect=0.5)
    result = evaluate_pace_assist_candidate(features, ctx)
    assert "not_higher_than_current_music" in result.reject_reasons


def test_5_to_7_and_8_to_10_have_different_targets():
    a = build_pace_lift_target(RunnerContext(5, 7, 135, 134))
    b = build_pace_lift_target(RunnerContext(8, 10, 160, 158))
    assert a.state == "strong_lift"
    assert b.state == "medium_lift"
    assert a.desired_next_asc_spm < b.desired_next_asc_spm


def test_good_pace_up_candidate_scores_high():
    ctx = RunnerContext(current_speed_kmh=8, target_speed_kmh=10, current_runner_cadence_spm=160, current_music_asc_spm=158)
    signal = SignalCueFeatures(
        segment_id="good",
        primary_asc_spm=165,
        asc_strength=0.86,
        asc_stability=0.84,
        pulse_clarity=0.82,
        rhythm_predictability=0.80,
        analysis_confidence=0.85,
        pulse_dropout_risk=0.04,
        half_time_shift_risk=0.03,
        fake_groove_risk=0.04,
    )
    ai = AISemanticScores(
        stable_running_groove=0.80,
        clear_step_cue=0.85,
        pace_up_cue=0.83,
        maintainable_drive=0.78,
        ai_confidence=0.9,
        provider="test",
    )
    features = SegmentPaceAssistFeatures(signal=signal, ai=ai, user_response_effect=0.65)
    result = evaluate_pace_assist_candidate(features, ctx)
    assert result.reject_reasons == []
    assert result.pace_assist_score > 0.70


def test_overcue_is_rejected():
    ctx = RunnerContext(current_speed_kmh=5, target_speed_kmh=7, current_runner_cadence_spm=135, current_music_asc_spm=134)
    signal = SignalCueFeatures(
        segment_id="over",
        primary_asc_spm=160,
        asc_strength=0.9,
        asc_stability=0.9,
        pulse_clarity=0.9,
        rhythm_predictability=0.9,
        analysis_confidence=0.9,
    )
    ai = AISemanticScores(stable_running_groove=0.9, clear_step_cue=0.9, pace_up_cue=0.9)
    features = SegmentPaceAssistFeatures(signal=signal, ai=ai)
    result = evaluate_pace_assist_candidate(features, ctx)
    assert "overcue_risk" in result.reject_reasons


def test_ai_negative_semantic_risk_rejects_candidate():
    ctx = RunnerContext(current_speed_kmh=8, target_speed_kmh=10, current_runner_cadence_spm=160, current_music_asc_spm=158)
    signal = SignalCueFeatures(
        segment_id="bad_ai",
        primary_asc_spm=165,
        asc_strength=0.9,
        asc_stability=0.9,
        pulse_clarity=0.9,
        rhythm_predictability=0.9,
        analysis_confidence=0.9,
    )
    ai = AISemanticScores(
        stable_running_groove=0.9,
        clear_step_cue=0.9,
        pace_up_cue=0.9,
        half_time_trap=0.8,
    )
    features = SegmentPaceAssistFeatures(signal=signal, ai=ai)
    result = evaluate_pace_assist_candidate(features, ctx)
    assert "ai_negative_semantic_risk" in result.reject_reasons


def test_synthetic_signal_extracts_asc_near_150():
    # 150 SPM cue at 50 frame/s -> period 20 frames.
    frame_rate = 50
    n = 1000
    onset = [1.0 if i % 20 == 0 else 0.05 for i in range(n)]
    rms = [0.7] * n
    tempo = [150] * n
    f = extract_signal_cue_features_from_curves(
        onset_env=onset,
        rms_curve=rms,
        tempo_curve_bpm=tempo,
        frame_rate=frame_rate,
        runner_cadence_spm=150,
        current_music_asc_spm=145,
    )
    assert abs(f.primary_asc_spm - 150) <= 2
    assert f.asc_strength > 0.45
    assert f.pulse_dropout_risk < 0.30


def test_outcome_effect_and_stats_update():
    rec = PaceOutcomeRecord(
        segment_id="s1",
        track_id="t1",
        speed_state="medium_lift",
        target_speed_kmh=10,
        control_speed_before=8,
        control_speed_after_30s=8.8,
        control_speed_after_60s=9.2,
    )
    assert outcome_effect_score(rec) > 0.5

    stats = SegmentOutcomeStats(segment_id="s1", track_id="t1")
    stats = update_segment_outcome_stats(stats, rec)
    assert stats.plays == 1
    assert user_response_effect_from_stats(stats) > 0.5


def test_fast_or_enough_state_does_not_seek_slowdown_music():
    target = build_pace_lift_target(RunnerContext(10.2, 10.0, 164, 162))
    assert target.state == "hold_or_stabilize"
    assert target.desired_next_asc_spm == 162
