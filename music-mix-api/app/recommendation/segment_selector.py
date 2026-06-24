from __future__ import annotations

from app.domain.models import (
    RunningContext,
    PlaybackContext,
    ClientContext,
    RecommendationConstraints,
    SegmentRecommendation,
    PlaybackPlan,
    TransitionMethod,
)
from app.db.repositories import SegmentRepository
from app.recommendation.target_energy import compute_target_energy
from app.recommendation.pace_assist_selector import (
    enrich_reason_with_selection,
    is_hold_route,
    pace_assist_reason_payload,
    pace_assist_top_candidates_payload,
    select_pace_assist_segment,
)


def select_best_segment(
    repository: SegmentRepository,
    running_context: RunningContext,
    playback_context: PlaybackContext,
    constraints: RecommendationConstraints,
):
    selection = select_pace_assist_segment(repository, running_context, playback_context, constraints)
    return selection.target, selection.selected_segment, selection.breakdown


def get_mobile_next_segment(
    repository: SegmentRepository,
    running_context: RunningContext,
    playback_context: PlaybackContext,
    client_context: ClientContext | None = None,
    constraints: RecommendationConstraints | None = None,
) -> SegmentRecommendation:
    constraints = constraints or RecommendationConstraints()
    target = compute_target_energy(
        current_pace_sec_per_km=running_context.current_pace_sec_per_km,
        target_pace_sec_per_km=running_context.target_pace_sec_per_km,
        running_mode=running_context.running_mode,
        fatigue_level=running_context.fatigue_level,
    )

    selection = select_pace_assist_segment(repository, running_context, playback_context, constraints)
    selected = selection.selected_segment
    breakdown = selection.breakdown
    if is_hold_route(selection):
        reason = pace_assist_reason_payload(breakdown)
        reason = enrich_reason_with_selection(reason, selection)
        reason["top_candidates"] = pace_assist_top_candidates_payload(
            selection.ranked_candidates,
            limit=10,
            running_context=running_context,
            playback_context=playback_context,
            segment_by_id=selection.segment_by_id,
            record_by_id=selection.record_by_id,
        )
        reason["multi_model_debug"] = selection.multi_model_debug
        return SegmentRecommendation(
            should_switch=False,
            decision=target,
            selected_segment=selected,
            retry_after_sec=15,
            reason=reason,
        )
    if selected is None or breakdown is None:
        reason = {
            "main_reason": "no_candidate_segment",
            "speed_degree_debug": selection.speed_degree_debug,
            "multi_model_debug": selection.multi_model_debug,
        }
        if selection.route_selection is not None:
            reason["top_candidates"] = pace_assist_top_candidates_payload(
                selection.ranked_candidates,
                limit=10,
                running_context=running_context,
                playback_context=playback_context,
                segment_by_id=selection.segment_by_id,
                record_by_id=selection.record_by_id,
            )
        return SegmentRecommendation(
            should_switch=False,
            decision=target,
            retry_after_sec=15,
            reason=reason,
        )

    crossfade_sec = float(getattr(selection.target, "crossfade_sec", None) or 2.0)
    plan = PlaybackPlan(
        start_at_sec=selected.start_sec,
        recommended_play_until_sec=selected.end_sec,
        fade_out_current_sec=crossfade_sec,
        fade_in_next_sec=crossfade_sec,
        preload_required=True,
        transition_method=TransitionMethod.DIRECT_FADE,
    )

    reason = pace_assist_reason_payload(breakdown)
    reason = enrich_reason_with_selection(reason, selection)
    reason["top_candidates"] = pace_assist_top_candidates_payload(
        selection.ranked_candidates,
        limit=10,
        running_context=running_context,
        playback_context=playback_context,
        segment_by_id=selection.segment_by_id,
        record_by_id=selection.record_by_id,
    )
    reason["multi_model_debug"] = selection.multi_model_debug

    return SegmentRecommendation(
        should_switch=True,
        decision=target,
        selected_segment=selected,
        playback_plan=plan,
        reason=reason,
    )
