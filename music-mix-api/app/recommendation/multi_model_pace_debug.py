from __future__ import annotations

from dataclasses import asdict
from typing import Sequence

from app.analysis.multi_model_pace_feature_core import (
    SegmentAnalysis,
    RunnerState,
    build_target_music_profile,
    route_to_dict,
    recommend_route,
    stable_match_score,
    connector_match_score,
    target_profile_to_dict,
)
from app.analysis.multi_model_pace_features import build_segment_analysis_from_segment
from app.analysis.mert_embedding_adapter import MERTEmbeddingAdapter
from app.analysis.muq_mulan_semantic_adapter import MuQMulanSemanticAdapter
from app.domain.models import PlaybackContext, RunningContext, Segment


def multi_model_debug_payload(
    *,
    segments: Sequence[Segment],
    running_context: RunningContext,
    playback_context: PlaybackContext,
    top_n: int = 5,
) -> dict:
    target = build_target_music_profile(runner_state_from_context(running_context))
    analyses = [
        build_segment_analysis_from_segment(
            segment,
            mert_adapter=MERTEmbeddingAdapter(),
            semantic_adapter=MuQMulanSemanticAdapter(),
        )
        for segment in segments
    ]
    route = recommend_route(
        analyses=analyses,
        target=target,
        current_segment_id=playback_context.current_segment_id,
        recent_segment_ids=playback_context.recent_segment_ids,
        top_n=top_n,
    )
    payload = route_to_dict(route)
    payload["TargetMusicProfile"] = target_profile_to_dict(target)
    payload["target_music_profile"] = payload["TargetMusicProfile"]
    return payload


def multi_model_candidate_debug(
    segment: Segment,
    running_context: RunningContext,
    playback_context: PlaybackContext,
) -> dict:
    target = build_target_music_profile(runner_state_from_context(running_context))
    analysis = build_segment_analysis_from_segment(
        segment,
        mert_adapter=MERTEmbeddingAdapter(),
        semantic_adapter=MuQMulanSemanticAdapter(),
    )
    stable_score, stable_breakdown = stable_match_score(
        analysis=analysis,
        target=target,
        recent_segment_ids=playback_context.recent_segment_ids,
    )
    connector_score, connector_breakdown = connector_match_score(analysis=analysis, target=target)
    reject_reason = stable_breakdown.get("reject_reason") or connector_breakdown.get("reject_reason")
    if segment.segment_id == playback_context.current_segment_id:
        reject_reason = "current_segment_hard_exclude"
    elif segment.segment_id in set(playback_context.recent_segment_ids):
        reject_reason = "recent_segment_hard_exclude"
    return {
        "TargetMusicProfile": target_profile_to_dict(target),
        "PaceFeatureVector": asdict(analysis.pace_vector),
        "fusion_weights": dict(analysis.pace_vector.fusion_weights),
        "stable_score_breakdown": stable_breakdown,
        "connector_score_breakdown": connector_breakdown,
        "stable_score": round(stable_score, 4),
        "connector_score": round(connector_score, 4),
        "reject_reason": reject_reason,
        "segment_use": analysis.structure.segment_use,
        "transition_type": analysis.structure.transition_type,
        "flow_direction": analysis.structure.flow_direction,
    }


def runner_state_from_context(running_context: RunningContext) -> RunnerState:
    cadence = running_context.target_cadence_spm or running_context.current_cadence_spm
    return RunnerState(
        current_pace_sec_per_km=running_context.current_pace_sec_per_km,
        target_pace_sec_per_km=running_context.target_pace_sec_per_km,
        current_cadence_spm=cadence,
        fatigue_score=running_context.fatigue_level or 0.0,
    )
