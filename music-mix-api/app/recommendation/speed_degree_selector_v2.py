from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.analysis.speed_degree_pace_core_v2 import (
    RunnerSpeedState,
    SegmentAnalysisV2,
    TargetMusicProfileV2,
    build_target_music_profile_v2,
    connector_score_v2,
    profile_to_dict,
    stable_score_v2,
)
from app.analysis.speed_degree_pace_features_v2 import build_segment_analysis_v2_from_segment, pace_vector_v2_to_dict
from app.domain.models import PlaybackContext, RunningContext, Segment


@dataclass(frozen=True)
class SpeedDegreeCandidateV2:
    segment: Segment
    analysis: SegmentAnalysisV2
    stable_score: float
    connector_score: float
    stable_breakdown: dict[str, Any]
    connector_breakdown: dict[str, Any]

    @property
    def best_score(self) -> float:
        return max(self.stable_score, self.connector_score)

    @property
    def reject_reason(self) -> str | None:
        if self.analysis.structure.segment_use != "STABLE":
            connector_reason = self.connector_breakdown.get("reject_reason")
            if connector_reason and connector_reason != "not_connector_candidate":
                return connector_reason
        return self.stable_breakdown.get("reject_reason") or self.connector_breakdown.get("reject_reason")


@dataclass(frozen=True)
class SpeedDegreeSelectionV2:
    target: TargetMusicProfileV2
    route_type: str
    selected_segment: Segment | None
    target_segment: Segment | None
    selected_candidate: SpeedDegreeCandidateV2 | None
    target_candidate: SpeedDegreeCandidateV2 | None
    ranked_candidates: list[SpeedDegreeCandidateV2]
    top_stable_candidates: list[SpeedDegreeCandidateV2]
    top_connector_candidates: list[SpeedDegreeCandidateV2]
    rejected_candidates: list[SpeedDegreeCandidateV2]
    score_breakdown: dict[str, Any]


def select_speed_degree_segment_v2(
    segments: Sequence[Segment],
    running_context: RunningContext,
    playback_context: PlaybackContext,
    *,
    top_n: int = 10,
    runtime_context: str = "runtime",
) -> SpeedDegreeSelectionV2:
    target = build_target_music_profile_v2(runner_speed_state_from_context(running_context))
    rows: list[SpeedDegreeCandidateV2] = []
    for segment in segments:
        analysis = build_segment_analysis_v2_from_segment(segment)
        stable_score, stable_breakdown = stable_score_v2(
            analysis=analysis,
            target=target,
            current_segment_id=playback_context.current_segment_id,
            recent_segment_ids=playback_context.recent_segment_ids,
        )
        connector_score, connector_breakdown = connector_score_v2(
            analysis=analysis,
            target=target,
            current_segment_id=playback_context.current_segment_id,
            recent_segment_ids=playback_context.recent_segment_ids,
            runtime_context=runtime_context,
        )
        rows.append(
            SpeedDegreeCandidateV2(
                segment=segment,
                analysis=analysis,
                stable_score=stable_score,
                connector_score=connector_score,
                stable_breakdown=stable_breakdown,
                connector_breakdown=connector_breakdown,
            )
        )

    stable_rows = sorted([row for row in rows if row.stable_score > 0], key=lambda row: row.stable_score, reverse=True)
    connector_rows = sorted([row for row in rows if row.connector_score > 0], key=lambda row: row.connector_score, reverse=True)
    rejected_rows = sorted([row for row in rows if row.best_score <= 0], key=lambda row: row.segment.segment_id)

    best_stable = stable_rows[0] if stable_rows else None
    best_connector = connector_rows[0] if connector_rows else None

    route_type = "NONE"
    selected = None
    target_segment = None
    selected_candidate = None
    target_candidate = None
    score_breakdown: dict[str, Any] = {}

    if best_stable is not None:
        route_type = "DIRECT"
        selected = best_stable.segment
        target_segment = best_stable.segment
        selected_candidate = best_stable
        target_candidate = best_stable
        score_breakdown = {
            "stable_score": round(best_stable.stable_score, 4),
            "route_score": round(best_stable.stable_score, 4),
        }

    if best_connector is not None and best_stable is not None and target.allow_connector:
        route_score = 0.58 * best_connector.connector_score + 0.42 * best_stable.stable_score
        direct_score = best_stable.stable_score
        prefer_connector = (
            abs(target.music_pace_control) >= 0.20
            and best_connector.connector_score >= direct_score - 0.04
        ) or route_score > direct_score + 0.03
        if target.music_pace_control < -0.20 and best_connector.analysis.structure.transition_slope < -0.25:
            prefer_connector = best_connector.connector_score >= 0.35
        if prefer_connector:
            route_type = "CONNECTOR"
            selected = best_connector.segment
            target_segment = best_stable.segment
            selected_candidate = best_connector
            target_candidate = best_stable
            score_breakdown = {
                "connector_score": round(best_connector.connector_score, 4),
                "target_stable_score": round(best_stable.stable_score, 4),
                "route_score": round(route_score, 4),
                "direct_score": round(direct_score, 4),
            }

    ranked = sorted(rows, key=lambda row: row.best_score, reverse=True)
    return SpeedDegreeSelectionV2(
        target=target,
        route_type=route_type,
        selected_segment=selected,
        target_segment=target_segment,
        selected_candidate=selected_candidate,
        target_candidate=target_candidate,
        ranked_candidates=ranked[:top_n],
        top_stable_candidates=stable_rows[:top_n],
        top_connector_candidates=connector_rows[:top_n],
        rejected_candidates=rejected_rows[:top_n],
        score_breakdown=score_breakdown,
    )


def runner_speed_state_from_context(running_context: RunningContext) -> RunnerSpeedState:
    current_speed = 3600.0 / max(0.001, running_context.current_pace_sec_per_km)
    target_speed = 3600.0 / max(0.001, running_context.target_pace_sec_per_km)
    cadence = running_context.target_cadence_spm or running_context.current_cadence_spm
    return RunnerSpeedState(
        current_speed_kmh=current_speed,
        target_speed_kmh=target_speed,
        speed_20s_ago_kmh=running_context.speed_20s_ago_kmh,
        current_cadence_spm=cadence,
        fatigue_score=running_context.fatigue_level or 0.0,
    )


def selection_debug_payload(selection: SpeedDegreeSelectionV2) -> dict[str, Any]:
    return {
        "route_type": selection.route_type,
        "TargetMusicProfileV2": profile_to_dict(selection.target),
        "current_speed_kmh": round(selection.target.current_speed_kmh, 4),
        "target_speed_kmh": round(selection.target.target_speed_kmh, 4),
        "speed_20s_ago_kmh": selection.target.speed_20s_ago_kmh,
        "speed_gap_ratio": round(selection.target.speed_gap_ratio, 4),
        "speed_trend_ratio": round(selection.target.speed_trend_ratio, 4),
        "music_pace_control": round(selection.target.music_pace_control, 4),
        "target_music_speed_degree": round(selection.target.target_music_speed_degree, 4),
        "debug_intention_label": selection.target.debug_intention_label,
        "immediate_segment": segment_ref(selection.selected_candidate),
        "target_segment": segment_ref(selection.target_candidate),
        "score_breakdown": selection.score_breakdown,
        "top_stable_candidates": [candidate_payload(row, rank) for rank, row in enumerate(selection.top_stable_candidates[:5], 1)],
        "top_connector_candidates": [candidate_payload(row, rank) for rank, row in enumerate(selection.top_connector_candidates[:5], 1)],
        "rejected_candidates": [candidate_payload(row, rank) for rank, row in enumerate(selection.rejected_candidates[:5], 1)],
    }


def candidate_payload(row: SpeedDegreeCandidateV2, rank: int) -> dict[str, Any]:
    vector = row.analysis.pace_vector
    stable_debug = row.stable_breakdown
    connector_debug = row.connector_breakdown
    return {
        "rank": rank,
        "segment_id": row.segment.segment_id,
        "track_id": row.segment.track_id,
        "segment_use": row.analysis.structure.segment_use,
        "transition_type": row.analysis.structure.transition_type,
        "transition_slope": round(row.analysis.structure.transition_slope, 4),
        "music_speed_degree": round(vector.music_speed_degree, 4),
        "intro_like_score": round(vector.intro_like_score, 4),
        "pulse_drop_score": round(vector.pulse_drop_score, 4),
        "drive_preservation_score": round(vector.drive_preservation_score, 4),
        "connector_drive_score": round(vector.connector_drive_score, 4),
        "stable_score": round(row.stable_score, 4),
        "connector_score": round(row.connector_score, 4),
        "stable_score_breakdown": stable_debug,
        "connector_score_breakdown": connector_debug,
        "reject_reason": row.reject_reason,
        "PaceFeatureVectorV2": pace_vector_v2_to_dict(vector),
        "PaceFeatureVector": pace_vector_v2_to_dict(vector),
        "fusion_weights_v2": dict(vector.fusion_weights),
        "fusion_weights": dict(vector.fusion_weights),
    }


def segment_ref(row: SpeedDegreeCandidateV2 | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "segment_id": row.segment.segment_id,
        "track_id": row.segment.track_id,
        "segment_use": row.analysis.structure.segment_use,
        "transition_slope": round(row.analysis.structure.transition_slope, 4),
        "music_speed_degree": round(row.analysis.pace_vector.music_speed_degree, 4),
        "stable_score": round(row.stable_score, 4),
        "connector_score": round(row.connector_score, 4),
    }
