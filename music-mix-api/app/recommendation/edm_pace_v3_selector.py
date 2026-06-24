from __future__ import annotations

from collections import Counter
from dataclasses import asdict, replace
from typing import Any, Sequence

from app.analysis.edm_pace_v3_adapter import segments_to_v3_records
from app.analysis.edm_pace_v3_core import (
    CandidateScore,
    RecommendationResult,
    RunningSample,
    RuntimeContext,
    SegmentRecord,
    SessionHistory,
    V3Config,
    ZoneMemory,
    build_control_state,
    build_target_profile,
    classify_speed_zone,
    coverage_audit,
    metric_explain_ko,
    recommend_next_block,
)
from app.analysis.pace_assist_analyzer_v3_4 import (
    RunnerContext as PaceAssistRunnerContext,
    build_pace_lift_target,
    estimate_runner_cadence_spm,
)
from app.config.tuning_profiles import load_active_v3_config
from app.domain.models import PlaybackContext, RunningContext, Segment


def select_edm_pace_v3_block(
    segments: Sequence[Segment],
    running_context: RunningContext,
    playback_context: PlaybackContext,
    *,
    runtime_context: str = RuntimeContext.RUNTIME.value,
    config: V3Config | None = None,
) -> tuple[RecommendationResult, dict[str, Segment], dict[str, SegmentRecord]]:
    config = config or load_active_v3_config()
    records = segments_to_v3_records(list(segments), config)
    segment_by_id = {segment.segment_id: segment for segment in segments}
    record_by_id = {record.segment_id: record for record in records}
    samples = running_samples_from_context(running_context)
    target_speed = 3600.0 / max(0.001, running_context.target_pace_sec_per_km)
    memory = zone_memory_from_context(running_context, samples[-1].timestamp_sec, config)
    control_state, _ = build_control_state(samples, target_speed_kmh=target_speed, memory=memory, config=config)
    current_record = record_by_id.get(playback_context.current_segment_id or "")
    previous_degree = running_context.previous_target_music_speed_degree
    if previous_degree is None and current_record is not None:
        previous_degree = current_record.pace.music_speed_degree
    target = build_target_profile(
        control_state,
        previous_target_music_speed_degree=previous_degree,
        elapsed_since_last_change_sec=playback_context.seconds_since_last_switch,
        near_phrase_boundary=running_context.near_phrase_boundary,
        config=config,
    )
    current_speed = 3600.0 / max(0.001, running_context.current_pace_sec_per_km)
    current_runner_cadence = resolve_runner_cadence(running_context, current_speed)
    current_music_asc = resolve_current_music_asc(playback_context, current_record, current_runner_cadence)
    pace_lift_target = build_pace_lift_target(
        PaceAssistRunnerContext(
            current_speed_kmh=current_speed,
            target_speed_kmh=target_speed,
            current_runner_cadence_spm=current_runner_cadence,
            current_music_asc_spm=current_music_asc,
            current_segment_id=playback_context.current_segment_id,
            current_track_id=playback_context.current_track_id,
        )
    )
    has_current_music = current_record is not None or getattr(playback_context, "current_music_ASC_spm", None) is not None
    target = replace(
        target,
        current_runner_cadence_spm=round(pace_lift_target.current_runner_cadence_spm, 4),
        current_music_ASC_spm=round(pace_lift_target.current_music_asc_spm, 4) if has_current_music else None,
        desired_next_ASC_spm=round(pace_lift_target.desired_next_asc_spm, 4) if has_current_music else None,
        pace_lift_state=pace_lift_target.state if has_current_music else "initial_entry",
    )
    force_adjust = bool(getattr(playback_context, "force_adjust", False))
    if force_adjust:
        target = replace(
            target,
            should_change_music=True,
            hold_reason=None,
            change_reason="demo_force_adjust",
        )
    if current_record is None and not target.should_change_music:
        target = replace(
            target,
            should_change_music=True,
            hold_reason=None,
            change_reason="initial_entry",
        )
        runtime_context = RuntimeContext.INITIAL_ENTRY.value
    recent_segment_ids = list(playback_context.recent_segment_ids)
    if force_adjust and playback_context.current_segment_id:
        recent_segment_ids.insert(0, playback_context.current_segment_id)
    history = SessionHistory(
        recent_segment_ids=tuple(dict.fromkeys(recent_segment_ids)),
        recent_track_ids=tuple(playback_context.recent_track_ids),
        recent_degree_bins=(),
        recent_section_labels=(),
        last_change_sec=max(0.0, control_state.now_sec - playback_context.seconds_since_last_switch),
        session_play_counts=dict(Counter(playback_context.recent_track_ids)),
    )
    result = recommend_next_block(
        records,
        target,
        current_segment=current_record,
        history=history,
        runtime_context=runtime_context,
        config=config,
    )
    result.debug["control_state"] = control_state.as_dict()
    result.debug["coverage_audit"] = [row.as_dict() for row in coverage_audit(records, config)]
    result.debug["metric_explanations_ko"] = metric_explanations_for_result(result)
    result.debug["active_tuning_profile"] = config.active_tuning_profile
    result.debug["speed_zone_boundaries"] = dict(config.speed_zone_boundaries)
    result.debug["preferred_degree_range"] = list(
        config.preferred_degree_ranges.get(target.speed_zone, (config.target_degree_min, config.target_degree_max))
    )
    result.debug["fake_groove_thresholds"] = dict(config.fake_groove_thresholds)
    result.debug["score_weights"] = dict(config.score_weights)
    result.debug["latency_policy"] = dict(config.latency_policy)
    result.debug["anti_repeat_settings"] = {
        "recent_track_cooldown_count": config.recent_track_cooldown_count,
        "recent_track_penalty": config.recent_track_penalty,
        "same_degree_bin_penalty": config.same_degree_bin_penalty,
        "same_section_label_penalty": config.same_section_label_penalty,
        "session_play_count_penalty": config.session_play_count_penalty,
    }
    result.debug["force_adjust"] = force_adjust
    result.debug["current_segment_id"] = playback_context.current_segment_id
    result.debug["recent_track_ids"] = list(playback_context.recent_track_ids)
    result.debug["recent_segment_ids"] = list(playback_context.recent_segment_ids)
    result.debug["selected_segment_id"] = result.immediate_segment.segment_id if result.immediate_segment else None
    result.debug["pace_assist_v3_4"] = {
        "current_runner_cadence_spm": target.current_runner_cadence_spm,
        "current_music_ASC_spm": target.current_music_ASC_spm,
        "desired_next_ASC_spm": target.desired_next_ASC_spm,
        "pace_lift_state": target.pace_lift_state,
        "thresholds": dict(config.pace_assist_v3_4),
    }
    result.debug["current_segment_excluded"] = bool(
        playback_context.current_segment_id
        and (
            playback_context.current_segment_id in result.debug.get("stable_rejected", {})
            or playback_context.current_segment_id in result.debug.get("connector_rejected", {})
        )
    )
    result.debug["candidate_pool_size"] = len(records)
    result.debug["unique_track_count_in_pool"] = len({record.track_id for record in records})
    stable_rejected = result.debug.get("stable_rejected", {})
    connector_rejected = result.debug.get("connector_rejected", {})
    result.debug["stable_pool_size"] = sum(
        1
        for record in records
        if record.segment_use == "STABLE" and record.segment_id not in stable_rejected
    )
    result.debug["connector_pool_size"] = sum(
        1
        for record in records
        if record.segment_use != "STABLE" and record.segment_id not in connector_rejected
    )
    result.debug["same_music_unavoidable_due_to_sparse_pool"] = (
        bool(result.immediate_segment and result.immediate_segment.segment_id == playback_context.current_segment_id)
        and len({record.track_id for record in records}) <= 1
    )
    return result, segment_by_id, record_by_id


def running_samples_from_context(running_context: RunningContext) -> list[RunningSample]:
    raw_samples = running_context.running_samples or []
    samples: list[RunningSample] = []
    for item in raw_samples:
        if isinstance(item, RunningSample):
            samples.append(item)
        elif isinstance(item, dict):
            samples.append(
                RunningSample(
                    timestamp_sec=float(item.get("timestamp_sec", 0.0)),
                    speed_kmh=float(item.get("speed_kmh", 0.0)),
                    cadence_spm=item.get("cadence_spm"),
                )
            )
        else:
            timestamp = getattr(item, "timestamp_sec", 0.0)
            speed = getattr(item, "speed_kmh", 0.0)
            cadence = getattr(item, "cadence_spm", None)
            samples.append(RunningSample(float(timestamp), float(speed), cadence))
    samples = [sample for sample in samples if sample.speed_kmh > 0]
    if samples:
        return sorted(samples, key=lambda sample: sample.timestamp_sec)

    current_speed = 3600.0 / max(0.001, running_context.current_pace_sec_per_km)
    previous_speed = running_context.speed_20s_ago_kmh or current_speed
    return [
        RunningSample(timestamp_sec=0.0, speed_kmh=previous_speed, cadence_spm=running_context.current_cadence_spm),
        RunningSample(timestamp_sec=30.0, speed_kmh=previous_speed, cadence_spm=running_context.current_cadence_spm),
        RunningSample(timestamp_sec=60.0, speed_kmh=current_speed, cadence_spm=running_context.current_cadence_spm),
    ]


def resolve_runner_cadence(running_context: RunningContext, current_speed_kmh: float) -> float:
    if running_context.current_cadence_spm:
        return float(running_context.current_cadence_spm)
    for item in reversed(running_context.running_samples or []):
        cadence = item.get("cadence_spm") if isinstance(item, dict) else getattr(item, "cadence_spm", None)
        if cadence:
            return float(cadence)
    if running_context.target_cadence_spm:
        return float(running_context.target_cadence_spm)
    return estimate_runner_cadence_spm(current_speed_kmh)


def resolve_current_music_asc(
    playback_context: PlaybackContext,
    current_record: SegmentRecord | None,
    current_runner_cadence_spm: float,
) -> float:
    explicit = getattr(playback_context, "current_music_ASC_spm", None)
    if explicit:
        return float(explicit)
    if current_record is not None and current_record.pace_assist.primary_ASC_spm > 0:
        return current_record.pace_assist.primary_ASC_spm
    return max(105.0, current_runner_cadence_spm - 6.0)


def zone_memory_from_context(running_context: RunningContext, now_sec: float, config: V3Config = V3Config()) -> ZoneMemory:
    if running_context.active_speed_zone is None and running_context.candidate_speed_zone is None:
        current_speed = 3600.0 / max(0.001, running_context.current_pace_sec_per_km)
        target_speed = 3600.0 / max(0.001, running_context.target_pace_sec_per_km)
        zone = classify_speed_zone((target_speed - current_speed) / target_speed, config)
        return ZoneMemory(
            active_speed_zone=zone,
            candidate_speed_zone=zone,
            candidate_since_sec=max(0.0, now_sec - 30.0),
            last_zone_change_sec=max(0.0, now_sec - 30.0),
        )
    return ZoneMemory(
        active_speed_zone=running_context.active_speed_zone or "steady_deadband",
        candidate_speed_zone=running_context.candidate_speed_zone or (running_context.active_speed_zone or "steady_deadband"),
        candidate_since_sec=running_context.candidate_since_sec if running_context.candidate_since_sec is not None else max(0.0, now_sec - 30.0),
        last_zone_change_sec=running_context.last_zone_change_sec if running_context.last_zone_change_sec is not None else max(0.0, now_sec - 30.0),
    )


def result_debug_payload(result: RecommendationResult) -> dict[str, Any]:
    target = result.target_profile
    control = result.debug.get("control_state", {})
    stable_rejected = result.debug.get("stable_rejected", {})
    connector_rejected = result.debug.get("connector_rejected", {})
    stable_pool_size = result.debug.get("stable_pool_size")
    connector_pool_size = result.debug.get("connector_pool_size")
    if stable_pool_size is None:
        stable_pool_size = sum(1 for candidate in result.top_candidates if candidate.segment_use == "STABLE")
    if connector_pool_size is None:
        connector_pool_size = sum(1 for candidate in result.top_candidates if candidate.segment_use != "STABLE")
    return {
        "force_adjust": bool(result.debug.get("force_adjust", False)),
        "active_tuning_profile": result.debug.get("active_tuning_profile", "default"),
        "speed_zone_boundaries": result.debug.get("speed_zone_boundaries", {}),
        "preferred_degree_range": result.debug.get("preferred_degree_range", []),
        "fake_groove_thresholds": result.debug.get("fake_groove_thresholds", {}),
        "score_weights": result.debug.get("score_weights", {}),
        "latency_policy": result.debug.get("latency_policy", {}),
        "anti_repeat_settings": result.debug.get("anti_repeat_settings", {}),
        "recent_track_ids": result.debug.get("recent_track_ids", []),
        "recent_segment_ids": result.debug.get("recent_segment_ids", []),
        "route_type": result.route_type,
        "current_speed_kmh": control.get("current_speed_kmh"),
        "target_speed_kmh": control.get("target_speed_kmh"),
        "control_speed_kmh": control.get("control_speed_kmh"),
        "previous_control_speed_kmh": control.get("previous_control_speed_kmh"),
        "speed_gap_ratio": round(target.speed_gap_ratio, 4),
        "speed_trend_ratio": round(target.speed_trend_ratio, 4),
        "control_speed_stability": control.get("control_speed_stability"),
        "speed_zone": target.speed_zone,
        "zone_stable_duration_sec": round(target.zone_stable_duration_sec, 4),
        "music_pace_control": round(target.music_pace_control, 4),
        "target_music_speed_degree": round(target.target_music_speed_degree, 4),
        "target_degree_delta": round(target.target_degree_delta, 4),
        "current_runner_cadence_spm": target.current_runner_cadence_spm,
        "current_music_ASC_spm": target.current_music_ASC_spm,
        "desired_next_ASC_spm": target.desired_next_ASC_spm,
        "pace_lift_state": target.pace_lift_state,
        "pace_assist_v3_4_thresholds": result.debug.get("pace_assist_v3_4", {}).get("thresholds", {}),
        "route": target.latency_route,
        "latency_route": target.latency_route,
        "max_change_latency_sec": target.max_change_latency_sec,
        "estimated_change_latency_sec": target.estimated_change_latency_sec,
        "confirmation_elapsed_sec": target.confirmation_elapsed_sec,
        "min_hold_remaining_sec": target.min_hold_remaining_sec,
        "boundary_wait_sec": target.boundary_wait_sec,
        "crossfade_sec": target.crossfade_sec,
        "preselected_segment_id": result.debug.get("preselected_segment_id"),
        "change_intent_reason": target.change_intent_reason,
        "change_blocked_reason": target.change_blocked_reason,
        "forced_crossfade_used": target.forced_crossfade_used,
        "should_change_music": target.should_change_music,
        "hold_reason": result.hold_reason,
        "change_reason": result.change_reason,
        "candidate_pool_warning": list(result.candidate_pool_warning),
        "current_segment_id": result.debug.get("current_segment_id"),
        "selected_segment_id": result.debug.get("selected_segment_id"),
        "current_segment_excluded": bool(result.debug.get("current_segment_excluded", False)),
        "candidate_pool_size": int(result.debug.get("candidate_pool_size", 0)),
        "unique_track_count_in_pool": int(result.debug.get("unique_track_count_in_pool", 0)),
        "target_degree_bin": result.debug.get("target_degree_bin"),
        "stable_pool_size": int(stable_pool_size or 0),
        "connector_pool_size": int(connector_pool_size or 0),
        "same_music_unavoidable_due_to_sparse_pool": bool(result.debug.get("same_music_unavoidable_due_to_sparse_pool", False)),
        "immediate_segment": segment_ref(result.immediate_segment),
        "target_segment": segment_ref(result.target_segment),
        "score_breakdown": result.debug,
        "reject_reasons": {
            "stable_rejected": stable_rejected,
            "connector_rejected": connector_rejected,
        },
        "diversity_penalties": [candidate.diversity_penalties for candidate in result.top_candidates],
        "metric_explanations_ko": result.debug.get("metric_explanations_ko", {}),
        "coverage_audit": result.debug.get("coverage_audit", []),
    }


def candidate_payload(candidate: CandidateScore, record_by_id: dict[str, SegmentRecord], rank: int) -> dict[str, Any]:
    record = record_by_id[candidate.segment_id]
    breakdown = candidate.score_breakdown
    return {
        "rank": rank,
        "segment_id": candidate.segment_id,
        "track_id": candidate.track_id,
        "segment_use": candidate.segment_use,
        "section_type": record.section_label,
        "music_speed_degree": round(record.pace.music_speed_degree, 4),
        "transition_slope": round(record.transition.transition_slope, 4),
        "intro_like_score": round(record.risk.intro_like_score, 4),
        "pulse_drop_score": round(record.risk.pulse_drop_score, 4),
        "drive_preservation_score": round(record.drive.drive_preservation_score, 4),
        "connector_drive_score": round(record.transition.drive_connector_score, 4),
        "pulse_continuity_score": round(record.pulse.pulse_continuity_score, 4),
        "cadence_lock_support": round(record.pulse.cadence_lock_support, 4),
        "beat_salience_score": round(record.pulse.beat_salience_score, 4),
        "candidate_ASC_spm": round(record.pace_assist.primary_ASC_spm, 4),
        "ASC_lift_from_current_music": round(float(breakdown.get("ASC_lift_from_current_music", 0.0)), 4),
        "ASC_strength": round(record.pace_assist.ASC_strength, 4),
        "ASC_stability": round(record.pace_assist.ASC_stability, 4),
        "pulse_clarity": round(record.pace_assist.pulse_clarity, 4),
        "rhythm_predictability": round(record.pace_assist.rhythm_predictability, 4),
        "pulse_dropout_risk": round(record.pace_assist.pulse_dropout_risk, 4),
        "half_time_shift_risk": round(record.pace_assist.half_time_shift_risk, 4),
        "fake_groove_risk": round(record.pace_assist.fake_groove_risk, 4),
        "AI_semantic_scores": dict(record.pace_assist.ai_semantic_scores),
        "pace_assist_score": round(record.pace_assist.pace_assist_score, 4),
        "base_score": round(candidate.base_score, 4),
        "final_score": round(candidate.final_score, 4),
        "score_breakdown": candidate.score_breakdown,
        "reject_reason": ", ".join(candidate.reject_reasons) if candidate.reject_reasons else None,
        "diversity_penalty": round(sum(candidate.diversity_penalties.values()), 4),
        "diversity_penalties": candidate.diversity_penalties,
        "why_selected_ko": list(candidate.why_selected_ko),
        "PaceFeatureVector": {
            "music_speed_degree": round(record.pace.music_speed_degree, 4),
            "pulse_continuity_score": round(record.pulse.pulse_continuity_score, 4),
            "drive_preservation_score": round(record.drive.drive_preservation_score, 4),
            "cadence_lock_support": round(record.pulse.cadence_lock_support, 4),
            "intro_like_score": round(record.risk.intro_like_score, 4),
            "pulse_drop_score": round(record.risk.pulse_drop_score, 4),
            "primary_ASC_spm": round(record.pace_assist.primary_ASC_spm, 4),
            "pace_assist_score": round(record.pace_assist.pace_assist_score, 4),
        },
    }


def reject_reasons_payload(result: RecommendationResult) -> dict[str, Any]:
    return {
        "stable_rejected": result.debug.get("stable_rejected", {}),
        "connector_rejected": result.debug.get("connector_rejected", {}),
    }


def segment_ref(record: SegmentRecord | None) -> dict[str, Any] | None:
    if record is None:
        return None
    return {
        "segment_id": record.segment_id,
        "track_id": record.track_id,
        "segment_use": record.segment_use,
        "music_speed_degree": round(record.pace.music_speed_degree, 4),
        "primary_ASC_spm": round(record.pace_assist.primary_ASC_spm, 4),
        "pace_assist_score": round(record.pace_assist.pace_assist_score, 4),
        "section_label": record.section_label,
    }


def metric_explanations_for_result(result: RecommendationResult) -> dict[str, Any]:
    metrics: dict[str, float] = {
        "target_music_speed_degree": result.target_profile.target_music_speed_degree,
        "speed_gap_ratio": abs(result.target_profile.speed_gap_ratio),
    }
    segment = result.immediate_segment
    if segment is not None:
        metrics.update(
            {
                "music_speed_degree": segment.pace.music_speed_degree,
                "pulse_continuity_score": segment.pulse.pulse_continuity_score,
                "drive_preservation_score": segment.drive.drive_preservation_score,
                "cadence_lock_support": segment.pulse.cadence_lock_support,
                "intro_like_score": segment.risk.intro_like_score,
                "pulse_drop_score": segment.risk.pulse_drop_score,
                "primary_ASC_spm": segment.pace_assist.primary_ASC_spm,
                "pace_assist_score": segment.pace_assist.pace_assist_score,
                "ASC_strength": segment.pace_assist.ASC_strength,
                "ASC_stability": segment.pace_assist.ASC_stability,
                "pulse_dropout_risk": segment.pace_assist.pulse_dropout_risk,
                "half_time_shift_risk": segment.pace_assist.half_time_shift_risk,
            }
        )
    return {key: metric_explain_ko(key, value) for key, value in metrics.items()}
