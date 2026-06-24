from app.analysis.multi_model_pace_features import annotate_segments_with_multi_model_pace_features
from app.db.repositories import InMemorySegmentRepository
from app.domain.models import PlaybackContext, RecommendationConstraints, RunningContext, SectionType, Segment
from app.recommendation.segment_selector import get_mobile_next_segment


def test_annotate_segment_adds_pace_feature_vector_signal_fallback():
    segment = Segment(
        "seg_signal_only",
        "track_a",
        "a.mp3",
        0,
        40,
        1,
        16,
        SectionType.GROOVE,
        0.4,
        3,
        128,
        0.9,
        volume_score=0.4,
        onset_density_score=0.6,
        brightness_score=0.4,
        sound_density_score=0.5,
        metadata={"beat_salience_score": 0.7, "bass_drive_score": 0.65},
    )

    annotated = annotate_segments_with_multi_model_pace_features([segment])[0]

    assert annotated.metadata["segment_use"] == "STABLE"
    assert "pace_feature_vector" in annotated.metadata
    assert annotated.metadata["fusion_weights"]["signal"] == 1.0


def test_recommendation_response_includes_multi_model_debug():
    repo = InMemorySegmentRepository(
        [
            Segment(
                "stable",
                "track_a",
                "a.mp3",
                0,
                40,
                1,
                16,
                SectionType.GROOVE,
                0.55,
                3,
                140,
                0.9,
                metadata={"segment_use": "STABLE", "beat_salience_score": 0.8, "bass_drive_score": 0.7},
            ),
            Segment(
                "connector",
                "track_b",
                "b.mp3",
                0,
                36,
                1,
                16,
                SectionType.BUILD_UP,
                0.65,
                4,
                142,
                0.88,
                metadata={"segment_use": "TRANSITION", "flow_direction": "up", "beat_salience_score": 0.75, "bass_drive_score": 0.72},
            ),
        ]
    )

    rec = get_mobile_next_segment(
        repo,
        RunningContext(330, 300, "pace_up", target_cadence_spm=168),
        PlaybackContext(current_segment_played_sec=45, seconds_since_last_switch=60, previous_target_energy=0.4),
        constraints=RecommendationConstraints(min_segment_duration_sec=20, max_segment_duration_sec=90, allow_same_track=True),
    )

    assert rec.selected_segment is not None
    assert rec.reason["multi_model_debug"]["route_type"] in {"DIRECT", "CONNECTOR", "NONE"}
    assert "TargetMusicProfile" in rec.reason["multi_model_debug"]
    assert "PaceFeatureVector" in rec.reason["top_candidates"][0]
