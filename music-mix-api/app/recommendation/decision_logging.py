from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.domain.models import PlaybackContext, RunningContext, Segment, SegmentRecommendation
from app.paths import DATA_DIR


DECISION_LOG_ROOT = DATA_DIR / "debug" / "decision_logs"


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_day(created_at: str | None = None) -> str:
    value = created_at or now_utc_iso()
    return value[:10].replace("-", "")


def decision_log_path(session_id: str, created_at: str | None = None) -> Path:
    safe_session = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in session_id or "unknown")
    return DECISION_LOG_ROOT / log_day(created_at) / f"{safe_session}.jsonl"


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows


def list_decision_sessions() -> list[str]:
    if not DECISION_LOG_ROOT.exists():
        return []
    sessions = {path.stem for path in DECISION_LOG_ROOT.glob("*/*.jsonl")}
    return sorted(sessions)


def read_decisions(session_id: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
    if session_id:
        paths = sorted(DECISION_LOG_ROOT.glob(f"*/*{session_id}*.jsonl"))
    else:
        paths = sorted(DECISION_LOG_ROOT.glob("*/*.jsonl"))
    rows: list[dict[str, Any]] = []
    for path in paths:
        rows.extend(read_jsonl(path))
    rows = sorted(rows, key=lambda row: str(row.get("created_at", "")), reverse=True)
    return rows[:limit]


def find_decision(decision_id: str) -> dict[str, Any] | None:
    for row in read_decisions(limit=10000):
        if row.get("decision_id") == decision_id:
            return row
    return None


def segment_debug(segment: Segment | None) -> dict[str, Any]:
    if segment is None:
        return {}
    return {
        "track_id": segment.track_id,
        "segment_id": segment.segment_id,
        "music_speed_degree": segment.metadata.get("music_speed_degree"),
        "primary_ASC_spm": segment.metadata.get("primary_ASC_spm"),
        "ASC_strength": segment.metadata.get("ASC_strength"),
        "ASC_stability": segment.metadata.get("ASC_stability"),
        "pulse_clarity": segment.metadata.get("pulse_clarity"),
        "rhythm_predictability": segment.metadata.get("rhythm_predictability"),
        "pulse_dropout_risk": segment.metadata.get("pulse_dropout_risk"),
        "half_time_shift_risk": segment.metadata.get("half_time_shift_risk"),
        "fake_groove_risk": segment.metadata.get("fake_groove_risk"),
        "AI_semantic_scores": segment.metadata.get("AI_semantic_scores", {}),
        "pace_assist_score": segment.metadata.get("pace_assist_score"),
        "track_title": segment.metadata.get("track_title", segment.track_id),
        "audio_file_name": segment.metadata.get("audio_file_name"),
        "segment_clip_path": segment.metadata.get("segment_clip_path"),
    }


def reject_summary(reject_reasons: dict[str, Any]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for group in ("stable_rejected", "connector_rejected"):
        for reasons in (reject_reasons.get(group) or {}).values():
            for reason in reasons or []:
                counts[str(reason)] = counts.get(str(reason), 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[1], reverse=True))


def build_decision_log(
    *,
    session_id: str,
    source: str,
    running_context: RunningContext,
    playback_context: PlaybackContext,
    recommendation: SegmentRecommendation,
    current_segment: Segment | None,
) -> dict[str, Any]:
    created_at = now_utc_iso()
    reason = recommendation.reason or {}
    debug = reason.get("speed_degree_debug") or {}
    selected = recommendation.selected_segment
    selected_debug = segment_debug(selected)
    current_debug = segment_debug(current_segment)
    top_candidates = reason.get("top_candidates", [])
    first_candidate = top_candidates[0] if top_candidates else {}
    reject_reasons = debug.get("reject_reasons") or {}
    current_speed = 3600.0 / max(0.001, running_context.current_pace_sec_per_km)
    target_speed = 3600.0 / max(0.001, running_context.target_pace_sec_per_km)
    current_music_asc = debug.get("current_music_ASC_spm")
    candidate_asc = first_candidate.get("candidate_ASC_spm") or selected_debug.get("primary_ASC_spm")
    desired_asc = debug.get("desired_next_ASC_spm")
    decision_id = f"dec_{uuid.uuid4().hex[:16]}"
    row = {
        "decision_id": decision_id,
        "session_id": session_id,
        "created_at": created_at,
        "source": source,
        "active_tuning_profile": debug.get("active_tuning_profile") or reason.get("active_tuning_profile"),
        "route": debug.get("route") or debug.get("route_type"),
        "current_speed_kmh": round(current_speed, 4),
        "target_speed_kmh": round(target_speed, 4),
        "previous_control_speed_kmh": debug.get("previous_control_speed_kmh"),
        "current_control_speed_kmh": debug.get("control_speed_kmh"),
        "current_runner_cadence_spm": debug.get("current_runner_cadence_spm"),
        "speed_zone": debug.get("speed_zone"),
        "pace_up_required": bool((debug.get("music_pace_control") or 0) > 0.08),
        "fast_or_over_target": bool((debug.get("music_pace_control") or 0) < -0.05),
        "current_track_id": playback_context.current_track_id,
        "current_segment_id": playback_context.current_segment_id,
        "current_music_ASC_spm": current_music_asc,
        "current_music_ASC_strength": current_debug.get("ASC_strength"),
        "current_music_ASC_stability": current_debug.get("ASC_stability"),
        "desired_next_ASC_spm": desired_asc,
        "selected_track_id": selected.track_id if selected else None,
        "selected_segment_id": selected.segment_id if selected else None,
        "candidate_ASC_spm": candidate_asc,
        "ASC_lift_from_current_music": first_candidate.get("ASC_lift_from_current_music"),
        "asc_target_delta": (
            round(float(candidate_asc) - float(desired_asc), 4)
            if candidate_asc is not None and desired_asc is not None
            else None
        ),
        "ASC_strength": first_candidate.get("ASC_strength") or selected_debug.get("ASC_strength"),
        "ASC_stability": first_candidate.get("ASC_stability") or selected_debug.get("ASC_stability"),
        "pulse_clarity": first_candidate.get("pulse_clarity") or selected_debug.get("pulse_clarity"),
        "rhythm_predictability": first_candidate.get("rhythm_predictability") or selected_debug.get("rhythm_predictability"),
        "pulse_dropout_risk": first_candidate.get("pulse_dropout_risk") or selected_debug.get("pulse_dropout_risk"),
        "half_time_shift_risk": first_candidate.get("half_time_shift_risk") or selected_debug.get("half_time_shift_risk"),
        "fake_groove_risk": first_candidate.get("fake_groove_risk") or selected_debug.get("fake_groove_risk"),
        "AI_semantic_scores": first_candidate.get("AI_semantic_scores") or selected_debug.get("AI_semantic_scores", {}),
        "pace_assist_score": first_candidate.get("pace_assist_score") or selected_debug.get("pace_assist_score"),
        "music_speed_degree": first_candidate.get("music_speed_degree") or selected_debug.get("music_speed_degree"),
        "candidate_pool_before_gate": debug.get("candidate_pool_size"),
        "candidate_pool_after_gate": debug.get("stable_pool_size"),
        "top_candidates": top_candidates,
        "reject_summary": reject_summary(reject_reasons),
        "reject_reasons": reject_reasons,
        "fallback_reason": ",".join(debug.get("candidate_pool_warning") or []) or None,
        "asc_gate_passed": not bool(first_candidate.get("reject_reason")),
        "asc_gate_relaxed": not bool(first_candidate.get("AI_semantic_scores")),
        "change_intent_reason": debug.get("change_intent_reason"),
        "change_blocked_reason": debug.get("change_blocked_reason"),
        "estimated_change_latency_sec": debug.get("estimated_change_latency_sec"),
        "max_change_latency_sec": debug.get("max_change_latency_sec"),
        "confirmation_elapsed_sec": debug.get("confirmation_elapsed_sec"),
        "min_hold_remaining_sec": debug.get("min_hold_remaining_sec"),
        "boundary_wait_sec": debug.get("boundary_wait_sec"),
        "crossfade_sec": debug.get("crossfade_sec"),
        "forced_crossfade_used": debug.get("forced_crossfade_used"),
        "preselected_segment_id": debug.get("preselected_segment_id"),
        "current_segment": current_debug,
        "selected_segment": selected_debug,
        "raw_reason": reason,
    }
    return row


def write_decision_log(row: dict[str, Any]) -> dict[str, Any]:
    append_jsonl(decision_log_path(str(row.get("session_id") or "unknown"), str(row.get("created_at") or "")), row)
    return row
