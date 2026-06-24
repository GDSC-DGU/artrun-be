from app.analysis.ai_music_segment_analyzer import annotate_segments_with_ai_running_feel
from app.domain.models import SectionType, Segment


def test_ai_running_feel_fields_are_merged_into_segment_metadata():
    segment = Segment(
        "track6_seg_004",
        "track6",
        "track6.mp3",
        64,
        96,
        33,
        48,
        SectionType.GROOVE,
        0.64,
        4,
        147.6,
        0.9,
        onset_density_score=1.0,
        metadata={
            "beat_salience_score": 0.41,
            "rhythmic_activity_score": 1.0,
            "rhythmic_predictability_score": 0.91,
            "groove_syncopation_fit": 0.74,
            "bass_drive_score": 0.77,
            "static_low_end_penalty": 0.51,
            "pace_push_score": 0.58,
            "entry_quality": 0.95,
            "exit_quality": 0.95,
            "loudness_density_score": 0.84,
        },
    )

    annotated = annotate_segments_with_ai_running_feel([segment])[0]

    assert annotated.metadata["ai_segment_role"] == "steady_to_pace_up_bridge"
    assert "pace_up" in annotated.metadata["recommended_for"]
    assert "sprint_push" in annotated.metadata["avoid_for"]
    assert annotated.metadata["ai_pace_push_score"] > 0.0
    assert annotated.metadata["section_type_signal"] == "groove"
    assert annotated.metadata["section_type_ai"] == "groove"


def test_ai_running_feel_marks_static_low_drive_as_avoid_for_pace_up():
    segment = Segment(
        "track1_seg_003",
        "track1",
        "track1.mp3",
        60,
        90,
        33,
        48,
        SectionType.GROOVE,
        0.84,
        5,
        99.4,
        0.9,
        onset_density_score=1.0,
        metadata={
            "beat_salience_score": 0.12,
            "rhythmic_activity_score": 1.0,
            "rhythmic_predictability_score": 0.97,
            "groove_syncopation_fit": 0.35,
            "bass_drive_score": 0.55,
            "static_low_end_penalty": 0.61,
            "pace_push_score": 0.48,
        },
    )

    annotated = annotate_segments_with_ai_running_feel([segment])[0]

    assert annotated.metadata["ai_segment_role"] == "low_drive_or_static"
    assert "pace_up" in annotated.metadata["avoid_for"]
    assert "sprint_push" in annotated.metadata["avoid_for"]
    assert annotated.metadata["ai_pace_push_score"] < 0.55
