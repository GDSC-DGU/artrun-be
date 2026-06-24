from app.domain.models import PlaybackContext, RunningContext, SectionType, Segment
from app.recommendation.scoring import score_segment_for_intention
from app.recommendation.target_music_profile import build_target_music_profile


def test_pace_up_mode_escalates_to_sprint_when_gap_is_large():
    profile = build_target_music_profile(
        RunningContext(
            current_pace_sec_per_km=3600 / 7.0,
            target_pace_sec_per_km=3600 / 12.0,
            running_mode="pace_up",
            target_cadence_spm=172,
        )
    )

    assert profile.running_intention == "sprint_push"


def test_target_music_profile_uses_positive_gap_for_slower_runner():
    profile = build_target_music_profile(
        RunningContext(330, 300, "pace_up", target_cadence_spm=172),
    )

    assert profile.pace_gap_ratio == 0.10
    assert profile.running_intention == "pace_up"
    assert profile.desired_music_pulse_range == (132.0, 152.0)


def test_sprint_prefers_half_time_cadence_match_over_fast_light_bpm():
    playback = PlaybackContext(current_segment_played_sec=45, seconds_since_last_switch=60)
    running = RunningContext(360, 300, "sprint", target_cadence_spm=172)
    track4_like = Segment(
        "track4_like",
        "track4",
        "track4.mp3",
        0,
        40,
        1,
        16,
        SectionType.GROOVE,
        0.48,
        3,
        84.7,
        0.9,
        metadata={
            "pace_push_score": 0.53,
            "groove_syncopation_fit": 0.57,
            "bass_drive_score": 0.70,
            "static_low_end_penalty": 0.32,
        },
    )
    track6_like = Segment(
        "track6_like",
        "track6",
        "track6.mp3",
        0,
        40,
        1,
        16,
        SectionType.GROOVE,
        0.59,
        4,
        147.6,
        0.9,
        metadata={
            "pace_push_score": 0.68,
            "groove_syncopation_fit": 0.80,
            "bass_drive_score": 0.89,
            "static_low_end_penalty": 0.43,
        },
    )

    track4_score = score_segment_for_intention(track4_like, running, playback)
    track6_score = score_segment_for_intention(track6_like, running, playback)

    assert track4_score.effective_pulse_relation == "half_time"
    assert track4_score.cadence_alignment_score > track6_score.cadence_alignment_score
    assert track4_score.final_score > track6_score.final_score
