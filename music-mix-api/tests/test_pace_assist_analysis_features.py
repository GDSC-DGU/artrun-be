from app.db.json_repository import segment_from_dict
from app.domain.models import PlaybackContext, RunningContext, SectionType, Segment
from app.recommendation.scoring import score_segment_for_intention


def test_json_repository_promotes_pace_assist_feature_fields_to_metadata():
    segment = segment_from_dict(
        {
            "segment_id": "s",
            "track_id": "t",
            "audio_url": "t.mp3",
            "start_sec": 0,
            "end_sec": 32,
            "start_bar": 1,
            "end_bar": 16,
            "section_type": "groove",
            "energy_score": 0.5,
            "energy_level": 3,
            "bpm": 140,
            "phrase_confidence": 0.8,
            "beat_salience_score": 0.7,
            "rhythmic_activity_score": 0.8,
            "static_low_end_penalty": 0.2,
            "pace_push_score": 0.75,
            "drop_likelihood_score": 0.6,
            "corrected_section_type": "groove",
            "pace_role_hint": "pace_up",
        }
    )

    assert segment.metadata["beat_salience_score"] == 0.7
    assert segment.metadata["pace_push_score"] == 0.75
    assert segment.metadata["pace_role_hint"] == "pace_up"


def test_static_low_end_penalty_suppresses_false_drop_for_sprint_push():
    runner = RunningContext(360, 300, "pace_up", target_cadence_spm=172)
    playback = PlaybackContext(current_segment_played_sec=45, seconds_since_last_switch=60)
    static_segment = Segment(
        "static",
        "track_static",
        "static.mp3",
        60,
        100,
        33,
        48,
        SectionType.DROP,
        0.85,
        5,
        100,
        0.9,
        metadata={
            "beat_salience_score": 0.12,
            "rhythmic_activity_score": 1.0,
            "rhythmic_predictability_score": 0.95,
            "syncopation_score": 0.74,
            "bass_drive_score": 0.55,
            "section_contrast_score": 0.96,
            "static_low_end_penalty": 0.61,
            "pace_push_score": 0.48,
            "drop_likelihood_score": 0.20,
        },
    )
    pulse_segment = Segment(
        "pulse",
        "track_pulse",
        "pulse.mp3",
        70,
        100,
        49,
        64,
        SectionType.GROOVE,
        0.65,
        4,
        148,
        0.9,
        metadata={
            "beat_salience_score": 0.41,
            "rhythmic_activity_score": 1.0,
            "rhythmic_predictability_score": 0.91,
            "syncopation_score": 0.57,
            "groove_syncopation_fit": 0.74,
            "bass_drive_score": 0.77,
            "section_contrast_score": 0.20,
            "static_low_end_penalty": 0.51,
            "pace_push_score": 0.58,
            "drop_likelihood_score": 0.15,
            "pace_role_hint": "pace_up",
        },
    )

    static_score = score_segment_for_intention(static_segment, runner, playback, intention="sprint_push").final_score
    pulse_score = score_segment_for_intention(pulse_segment, runner, playback, intention="sprint_push").final_score

    assert pulse_score > static_score
