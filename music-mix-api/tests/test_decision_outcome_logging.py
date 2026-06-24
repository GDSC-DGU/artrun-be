from app.db.repositories import InMemorySegmentRepository
from app.domain.models import PlaybackContext, RecommendationConstraints, RunningContext, SectionType, Segment
from app.recommendation.decision_logging import build_decision_log
from app.recommendation.pace_assist_outcomes import log_outcome
from app.recommendation.segment_selector import get_mobile_next_segment


def test_decision_log_has_required_latency_and_asc_fields():
    current = Segment("mid", "track_mid", "mid.mp3", 0, 40, 1, 16, SectionType.GROOVE, 0.55, 3, 128, 0.9)
    candidate = Segment("high", "track_high", "high.mp3", 40, 80, 17, 32, SectionType.DROP, 0.85, 5, 140, 0.9)
    repo = InMemorySegmentRepository([current, candidate])
    running = RunningContext(360, 300, "pace_up", target_cadence_spm=172, near_phrase_boundary=False)
    playback = PlaybackContext(current_segment_id="mid", current_track_id="track_mid", current_segment_played_sec=45, seconds_since_last_switch=3)
    rec = get_mobile_next_segment(repo, running, playback, constraints=RecommendationConstraints(allow_same_track=True))

    row = build_decision_log(
        session_id="test-session",
        source="speed_demo",
        running_context=running,
        playback_context=playback,
        recommendation=rec,
        current_segment=current,
    )

    assert row["decision_id"].startswith("dec_")
    assert row["route"] in {"WAIT_BOUNDARY", "CHANGE_NOW", "FORCED_CROSSFADE", "PRESELECT", "HOLD"}
    assert row["estimated_change_latency_sec"] <= row["max_change_latency_sec"]
    assert "top_candidates" in row
    assert "reject_summary" in row


def test_outcome_log_links_to_decision_id():
    result = log_outcome(
        {
            "decision_id": "dec_test_link",
            "session_id": "test-session",
            "segment_id": "seg_x",
            "track_id": "track_x",
            "speed_state": "push",
            "target_speed_kmh": 10.0,
            "control_speed_before": 8.0,
            "control_speed_after_30s": 8.8,
            "control_speed_after_60s": 9.1,
            "manual_label": "good_pace_up",
        }
    )

    assert result["outcome"]["decision_id"] == "dec_test_link"
    assert result["outcome"]["outcome_id"].startswith("out_")
    assert result["segment_user_response_effect"]["success_rate_by_speed_zone"]["push"]["success_rate"] > 0
