from app.db.repositories import InMemorySegmentRepository
from app.domain.models import PlaybackContext, RecommendationConstraints, RunningContext, SectionType, Segment
from app.recommendation.segment_selector import get_mobile_next_segment


def test_pace_assist_prefers_bass_drive_over_energy_only():
    repo = InMemorySegmentRepository(
        [
            Segment(
                "energy_only",
                "track_a",
                "a.mp3",
                0,
                40,
                1,
                16,
                SectionType.DROP,
                0.92,
                5,
                118,
                0.6,
                metadata={"bass_drive_score": 0.25, "syncopation_score": 0.2},
            ),
            Segment(
                "pace_assist",
                "track_b",
                "b.mp3",
                0,
                40,
                1,
                16,
                SectionType.DROP,
                0.76,
                4,
                136,
                0.9,
                metadata={"bass_drive_score": 0.85, "syncopation_score": 0.55},
            ),
        ]
    )

    rec = get_mobile_next_segment(
        repo,
        RunningContext(340, 300, "pace_up", target_cadence_spm=172),
        PlaybackContext(current_segment_played_sec=45, seconds_since_last_switch=60, previous_target_energy=0.4),
        constraints=RecommendationConstraints(min_segment_duration_sec=20, max_segment_duration_sec=90, allow_same_track=True),
    )

    assert rec.selected_segment is not None
    assert rec.selected_segment.segment_id == "pace_assist"
    assert rec.reason["debug_intention_label"] in {"gentle_push", "controlled_push"}
    assert rec.reason["target_music_speed_degree"] > 0.5
    assert "score_breakdown" in rec.reason


def test_light_control_uses_speed_degree_not_recovery_bucket():
    repo = InMemorySegmentRepository(
        [
            Segment("push", "track_a", "a.mp3", 0, 40, 1, 16, SectionType.DROP, 0.85, 5, 136, 0.9, metadata={"bass_drive_score": 0.9}),
            Segment("calm", "track_b", "b.mp3", 0, 40, 1, 16, SectionType.BREAKDOWN, 0.30, 2, 100, 0.85, metadata={"bass_drive_score": 0.2}),
        ]
    )

    rec = get_mobile_next_segment(
        repo,
        RunningContext(280, 300, "cool_down", target_cadence_spm=160),
        PlaybackContext(current_segment_played_sec=45, seconds_since_last_switch=60, previous_target_energy=0.55),
        constraints=RecommendationConstraints(min_segment_duration_sec=20, max_segment_duration_sec=90, allow_same_track=True),
    )

    assert rec.selected_segment is not None
    assert rec.selected_segment.segment_id == "push"
    assert rec.reason["debug_intention_label"] == "light_control"
    assert rec.reason["target_music_speed_degree"] < 0.5
