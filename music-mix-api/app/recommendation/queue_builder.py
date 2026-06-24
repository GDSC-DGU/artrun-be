from __future__ import annotations

from app.db.repositories import SegmentRepository
from app.domain.models import RunningContext, PlaybackContext, RecommendationConstraints
from app.recommendation.pace_assist_selector import select_pace_assist_segment
from app.recommendation.target_energy import compute_target_energy


def build_segment_queue(
    repository: SegmentRepository,
    running_context: RunningContext,
    playback_context: PlaybackContext,
    queue_size: int = 3,
    constraints: RecommendationConstraints | None = None,
):
    constraints = constraints or RecommendationConstraints()
    target = compute_target_energy(
        running_context.current_pace_sec_per_km,
        running_context.target_pace_sec_per_km,
        running_context.running_mode,
        running_context.fatigue_level,
    )
    candidates = list(getattr(repository, "segments", []) or [])
    if not candidates:
        candidates = repository.query_candidates(target.target_energy_score, constraints)
    if not constraints.allow_same_track and playback_context.current_track_id is not None:
        candidates = [s for s in candidates if s.track_id != playback_context.current_track_id]
    candidates = [
        segment
        for segment in candidates
        if segment.is_good_entry
        and constraints.min_segment_duration_sec <= segment.duration_sec <= constraints.max_segment_duration_sec
        and segment.segment_id != playback_context.current_segment_id
    ]
    selection = select_pace_assist_segment(repository, running_context, playback_context, constraints)
    segment_by_id = selection.segment_by_id or {segment.segment_id: segment for segment in candidates}
    ranked = []
    seen = set()
    for candidate in selection.ranked_candidates:
        if candidate.final_score <= 0 or candidate.segment_id == playback_context.current_segment_id:
            continue
        segment = segment_by_id.get(candidate.segment_id)
        if segment is None or segment.segment_id in seen:
            continue
        ranked.append(segment)
        seen.add(segment.segment_id)
        if len(ranked) >= queue_size:
            break
    if not ranked:
        ranked = sorted(
            candidates,
            key=lambda s: s.phrase_confidence,
            reverse=True,
        )
    return ranked[: max(0, queue_size)]
