from app.db.repositories import InMemorySegmentRepository
from app.domain.models import Segment, SectionType, RunningContext, PlaybackContext, RecommendationConstraints
from app.recommendation.segment_selector import get_mobile_next_segment


def make_repo():
    return InMemorySegmentRepository([
        Segment("low", "track_low", "low.mp3", 0, 60, 1, 32, SectionType.BREAKDOWN, 0.30, 2, 84, 0.7),
        Segment("mid", "track_mid", "mid.mp3", 0, 60, 1, 32, SectionType.GROOVE, 0.55, 3, 92, 0.7),
        Segment("high", "track_high", "high.mp3", 60, 120, 33, 64, SectionType.DROP, 0.91, 5, 128, 0.9),
    ])


def test_slow_runner_prefers_speed_degree_compatible_push_segment():
    rec = get_mobile_next_segment(
        make_repo(),
        RunningContext(360, 300, "pace_up", target_cadence_spm=172),
        PlaybackContext(current_segment_played_sec=40, seconds_since_last_switch=60, previous_target_energy=0.50),
        constraints=RecommendationConstraints(),
    )
    assert rec.should_switch is True
    assert rec.selected_segment is not None
    assert rec.reason["debug_intention_label"] == "push"
    assert rec.reason["target_music_speed_degree"] > 0.5
    assert rec.selected_segment.segment_id == "high"


def test_slow_runner_changes_with_latency_budget_even_when_segment_is_young():
    rec = get_mobile_next_segment(
        make_repo(),
        RunningContext(360, 300, "pace_up", target_cadence_spm=172),
        PlaybackContext(current_segment_id="mid", current_track_id="track_mid", current_segment_played_sec=5, seconds_since_last_switch=60, previous_target_energy=0.50),
        constraints=RecommendationConstraints(),
    )
    assert rec.should_switch is True
    assert rec.selected_segment is not None
    assert rec.reason["speed_degree_debug"]["estimated_change_latency_sec"] <= 10
    assert rec.reason["speed_degree_debug"]["route"] in {"CHANGE_NOW", "FORCED_CROSSFADE"}


def test_enough_state_holds_and_preselects_next_candidate():
    rec = get_mobile_next_segment(
        make_repo(),
        RunningContext(300, 300, "steady_run", target_cadence_spm=172),
        PlaybackContext(current_segment_id="mid", current_track_id="track_mid", current_segment_played_sec=45, seconds_since_last_switch=60, previous_target_energy=0.50),
        constraints=RecommendationConstraints(allow_same_track=True),
    )
    assert rec.should_switch is False
    assert rec.selected_segment is not None
    assert rec.reason["speed_degree_debug"]["route"] == "HOLD"
    assert rec.reason["speed_degree_debug"]["preselected_segment_id"] is not None


def test_fast_state_does_not_select_slow_down_music():
    rec = get_mobile_next_segment(
        make_repo(),
        RunningContext(280, 300, "cool_down", target_cadence_spm=172),
        PlaybackContext(
            current_segment_id="high",
            current_track_id="track_high",
            current_segment_played_sec=45,
            seconds_since_last_switch=60,
            previous_target_energy=0.50,
            force_adjust=True,
            current_music_ASC_spm=128,
        ),
        constraints=RecommendationConstraints(allow_same_track=True),
    )
    assert rec.selected_segment is not None
    assert rec.selected_segment.segment_id != "low"


def test_force_adjust_bypasses_runtime_hold_and_excludes_current_segment():
    rec = get_mobile_next_segment(
        make_repo(),
        RunningContext(360, 300, "pace_up", target_cadence_spm=172),
        PlaybackContext(
            current_segment_id="mid",
            current_track_id="track_mid",
            current_segment_played_sec=5,
            seconds_since_last_switch=1,
            previous_target_energy=0.50,
            force_adjust=True,
        ),
        constraints=RecommendationConstraints(allow_same_track=True),
    )
    assert rec.should_switch is True
    assert rec.selected_segment is not None
    assert rec.selected_segment.segment_id != "mid"
    assert rec.reason["speed_degree_debug"]["force_adjust"] is True
    assert rec.reason["speed_degree_debug"]["change_reason"] == "demo_force_adjust"
    assert rec.reason["speed_degree_debug"]["current_segment_excluded"] is True
