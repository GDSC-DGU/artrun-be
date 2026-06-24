from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.analysis.edm_pace_v3_core import CandidateScore, RecommendationResult, RouteType
from app.db.repositories import SegmentRepository
from app.domain.models import PlaybackContext, RecommendationConstraints, RunningContext, Segment
from app.recommendation.edm_pace_v3_selector import (
    candidate_payload as v3_candidate_payload,
    result_debug_payload,
    select_edm_pace_v3_block,
)
from app.recommendation.multi_model_pace_debug import multi_model_debug_payload


@dataclass(frozen=True)
class PaceAssistSelection:
    target: object
    selected_segment: Segment | None
    breakdown: CandidateScore | None
    ranked_candidates: list[CandidateScore]
    multi_model_debug: dict | None = None
    speed_degree_debug: dict | None = None
    route_selection: RecommendationResult | None = None
    segment_by_id: dict[str, Segment] | None = None
    record_by_id: dict[str, object] | None = None


def _all_candidates(repository: SegmentRepository, constraints: RecommendationConstraints) -> list[Segment]:
    segments = list(getattr(repository, "segments", []) or [])
    if not segments:
        wide_constraints = RecommendationConstraints(
            min_segment_duration_sec=constraints.min_segment_duration_sec,
            max_segment_duration_sec=constraints.max_segment_duration_sec,
            allow_same_track=constraints.allow_same_track,
            prefer_preloaded_audio=constraints.prefer_preloaded_audio,
            energy_window=1.0,
        )
        segments = repository.query_candidates(0.5, wide_constraints)
    return [
        segment
        for segment in segments
        if segment.is_good_entry
        and constraints.min_segment_duration_sec <= segment.duration_sec <= constraints.max_segment_duration_sec
    ]


def select_pace_assist_segment(
    repository: SegmentRepository,
    running_context: RunningContext,
    playback_context: PlaybackContext,
    constraints: RecommendationConstraints,
) -> PaceAssistSelection:
    candidates = _all_candidates(repository, constraints)
    if not constraints.allow_same_track and playback_context.current_track_id is not None:
        candidates = [segment for segment in candidates if segment.track_id != playback_context.current_track_id]

    result, segment_by_id, record_by_id = select_edm_pace_v3_block(
        candidates,
        running_context,
        playback_context,
    )
    selected_segment = segment_by_id.get(result.immediate_segment.segment_id) if result.immediate_segment else None
    breakdown = result.top_candidates[0] if result.top_candidates else None
    multi_debug = multi_model_debug_payload(
        segments=candidates,
        running_context=running_context,
        playback_context=playback_context,
        top_n=5,
    )
    return PaceAssistSelection(
        target=result.target_profile,
        selected_segment=selected_segment,
        breakdown=breakdown,
        ranked_candidates=list(result.top_candidates),
        multi_model_debug=multi_debug,
        speed_degree_debug=result_debug_payload(result),
        route_selection=result,
        segment_by_id=segment_by_id,
        record_by_id=record_by_id,
    )


def pace_assist_reason_payload(breakdown: CandidateScore | None) -> dict:
    if breakdown is None:
        return {"main_reason": "no_candidate_segment"}
    return {
        "main_reason": "; ".join(breakdown.why_selected_ko) or "edm_pace_v3_selected",
        "running_intention": "edm_pace_v3",
        "pace_assist_score": round(breakdown.final_score, 4),
        "target_music_profile": {},
        "score_breakdown": {
            **{key: round(value, 4) for key, value in breakdown.score_breakdown.items()},
            "base_score": round(breakdown.base_score, 4),
            "final_score": round(breakdown.final_score, 4),
            "diversity_penalty": round(sum(breakdown.diversity_penalties.values()), 4),
        },
    }


def enrich_reason_with_selection(reason: dict[str, Any], selection: PaceAssistSelection) -> dict[str, Any]:
    debug = selection.speed_degree_debug or {}
    reason.update(
        {
            "running_intention": debug.get("speed_zone", "edm_pace_v3"),
            "active_tuning_profile": debug.get("active_tuning_profile"),
            "preferred_degree_range": debug.get("preferred_degree_range", []),
            "fake_groove_thresholds": debug.get("fake_groove_thresholds", {}),
            "score_weights": debug.get("score_weights", {}),
            "debug_intention_label": (selection.route_selection.target_profile.debug_intention_label if selection.route_selection else None),
            "speed_gap_ratio": debug.get("speed_gap_ratio"),
            "speed_trend_ratio": debug.get("speed_trend_ratio"),
            "control_speed_kmh": debug.get("control_speed_kmh"),
            "previous_control_speed_kmh": debug.get("previous_control_speed_kmh"),
            "control_speed_stability": debug.get("control_speed_stability"),
            "speed_zone": debug.get("speed_zone"),
            "zone_stable_duration_sec": debug.get("zone_stable_duration_sec"),
            "music_pace_control": debug.get("music_pace_control"),
            "target_music_speed_degree": debug.get("target_music_speed_degree"),
            "target_degree_delta": debug.get("target_degree_delta"),
            "current_runner_cadence_spm": debug.get("current_runner_cadence_spm"),
            "current_music_ASC_spm": debug.get("current_music_ASC_spm"),
            "desired_next_ASC_spm": debug.get("desired_next_ASC_spm"),
            "pace_lift_state": debug.get("pace_lift_state"),
            "pace_assist_v3_4_thresholds": debug.get("pace_assist_v3_4_thresholds", {}),
            "route": debug.get("route"),
            "latency_route": debug.get("latency_route"),
            "max_change_latency_sec": debug.get("max_change_latency_sec"),
            "estimated_change_latency_sec": debug.get("estimated_change_latency_sec"),
            "confirmation_elapsed_sec": debug.get("confirmation_elapsed_sec"),
            "min_hold_remaining_sec": debug.get("min_hold_remaining_sec"),
            "boundary_wait_sec": debug.get("boundary_wait_sec"),
            "crossfade_sec": debug.get("crossfade_sec"),
            "preselected_segment_id": debug.get("preselected_segment_id"),
            "change_intent_reason": debug.get("change_intent_reason"),
            "change_blocked_reason": debug.get("change_blocked_reason"),
            "forced_crossfade_used": debug.get("forced_crossfade_used"),
            "should_change_music": debug.get("should_change_music"),
            "hold_reason": debug.get("hold_reason"),
            "change_reason": debug.get("change_reason"),
            "candidate_pool_warning": debug.get("candidate_pool_warning", []),
            "route_type": debug.get("route_type"),
            "immediate_segment": debug.get("immediate_segment"),
            "target_segment": debug.get("target_segment"),
            "speed_degree_debug": debug,
            "metric_explanations_ko": debug.get("metric_explanations_ko", {}),
        }
    )
    return reason


def pace_assist_candidate_payload(
    candidate: CandidateScore,
    rank: int,
    segment_by_id: dict[str, Segment] | None = None,
    record_by_id: dict[str, object] | None = None,
) -> dict:
    record_by_id = record_by_id or {}
    segment_by_id = segment_by_id or {}
    payload = v3_candidate_payload(candidate, record_by_id, rank)
    segment = segment_by_id.get(candidate.segment_id)
    if segment is not None:
        payload.update(
            {
                "section_type_signal": segment.metadata.get("section_type_signal", segment.section_type.value),
                "section_type_ai": segment.metadata.get("section_type_ai", segment.metadata.get("ai_corrected_section_type", segment.section_type.value)),
                "ai_segment_role": segment.metadata.get("ai_segment_role", "unknown"),
                "recommended_for": segment.metadata.get("recommended_for", []),
                "avoid_for": segment.metadata.get("avoid_for", []),
                "bpm": round(segment.bpm, 3),
                "energy_score_debug_only": round(segment.energy_score, 4),
            }
        )
    return payload


def pace_assist_top_candidates_payload(
    ranked_candidates: list[CandidateScore],
    limit: int = 5,
    running_context: RunningContext | None = None,
    playback_context: PlaybackContext | None = None,
    segment_by_id: dict[str, Segment] | None = None,
    record_by_id: dict[str, object] | None = None,
) -> list[dict]:
    return [
        pace_assist_candidate_payload(candidate, rank, segment_by_id, record_by_id)
        for rank, candidate in enumerate(ranked_candidates[:limit], start=1)
    ]


def is_hold_route(selection: PaceAssistSelection) -> bool:
    return bool(selection.route_selection and selection.route_selection.route_type == RouteType.HOLD.value)
