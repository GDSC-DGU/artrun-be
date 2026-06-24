from app.domain.models import RunningContext, PlaybackContext, ClientContext, RecommendationConstraints
from app.api.routes_mobile_running_music import demo_repository
from app.recommendation.segment_selector import get_mobile_next_segment


if __name__ == "__main__":
    repo = demo_repository()
    rec = get_mobile_next_segment(
        repository=repo,
        running_context=RunningContext(
            current_pace_sec_per_km=360,
            target_pace_sec_per_km=300,
            current_cadence_spm=160,
            target_cadence_spm=172,
            running_mode="pace_up",
        ),
        playback_context=PlaybackContext(
            current_track_id="track_X",
            current_segment_played_sec=42,
            seconds_since_last_switch=60,
            previous_target_energy=0.62,
            recent_track_ids=["track_B", "track_C"],
        ),
        client_context=ClientContext(platform="ios", app_version="1.0.0"),
        constraints=RecommendationConstraints(),
    )
    print(rec)
