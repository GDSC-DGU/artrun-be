from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.analysis.pace_assist_analyzer_v3_4 import (
    PaceOutcomeRecord,
    SegmentOutcomeStats,
    outcome_effect_score,
    update_segment_outcome_stats,
    user_response_effect_from_stats,
)
from app.paths import DATA_DIR


OUTCOME_DIR = DATA_DIR / "outcomes"
OUTCOME_LOG_PATH = OUTCOME_DIR / "pace_assist_outcomes.jsonl"
SEGMENT_EFFECT_PATH = OUTCOME_DIR / "segment_user_response_effect.json"


@dataclass(frozen=True)
class OutcomeLogPayload:
    segment_id: str
    track_id: str
    speed_state: str
    target_speed_kmh: float
    control_speed_before: float
    decision_id: str | None = None
    session_id: str | None = None
    played_at: str | None = None
    control_speed_after_30s: float | None = None
    control_speed_after_60s: float | None = None
    cadence_before_spm: float | None = None
    cadence_after_30s_spm: float | None = None
    cadence_after_60s_spm: float | None = None
    speed_variability_before: float | None = None
    speed_variability_after: float | None = None
    user_skip: bool = False
    user_dislike: bool = False
    manual_bad_segment: bool = False
    manual_label: str | None = None


def _read_effects() -> dict[str, Any]:
    if not SEGMENT_EFFECT_PATH.exists():
        return {}
    try:
        return json.loads(SEGMENT_EFFECT_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_effects(payload: dict[str, Any]) -> None:
    OUTCOME_DIR.mkdir(parents=True, exist_ok=True)
    SEGMENT_EFFECT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def log_outcome(payload: OutcomeLogPayload | dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict):
        allowed = set(OutcomeLogPayload.__dataclass_fields__)
        payload = OutcomeLogPayload(**{key: value for key, value in payload.items() if key in allowed})
    record_payload = {
        "segment_id": payload.segment_id,
        "track_id": payload.track_id,
        "speed_state": payload.speed_state,
        "target_speed_kmh": payload.target_speed_kmh,
        "control_speed_before": payload.control_speed_before,
        "control_speed_after_30s": payload.control_speed_after_30s,
        "control_speed_after_60s": payload.control_speed_after_60s,
        "cadence_before_spm": payload.cadence_before_spm,
        "cadence_after_30s_spm": payload.cadence_after_30s_spm,
        "cadence_after_60s_spm": payload.cadence_after_60s_spm,
        "user_skip": payload.user_skip,
        "user_dislike": payload.user_dislike,
        "manual_bad_segment": payload.manual_bad_segment,
    }
    record = PaceOutcomeRecord(**record_payload)
    OUTCOME_DIR.mkdir(parents=True, exist_ok=True)
    outcome_id = f"out_{uuid.uuid4().hex[:16]}"
    played_at = payload.played_at or datetime.now(timezone.utc).isoformat()
    log_row = {
        "outcome_id": outcome_id,
        **asdict(payload),
        "played_at": played_at,
        "pace_error_before": abs(payload.target_speed_kmh - payload.control_speed_before),
        "pace_error_after_30s": (
            abs(payload.target_speed_kmh - payload.control_speed_after_30s)
            if payload.control_speed_after_30s is not None
            else None
        ),
        "pace_error_after_60s": (
            abs(payload.target_speed_kmh - payload.control_speed_after_60s)
            if payload.control_speed_after_60s is not None
            else None
        ),
        "pace_error_reduction_30s": (
            abs(payload.target_speed_kmh - payload.control_speed_before)
            - abs(payload.target_speed_kmh - payload.control_speed_after_30s)
            if payload.control_speed_after_30s is not None
            else None
        ),
        "pace_error_reduction_60s": (
            abs(payload.target_speed_kmh - payload.control_speed_before)
            - abs(payload.target_speed_kmh - payload.control_speed_after_60s)
            if payload.control_speed_after_60s is not None
            else None
        ),
        "outcome_effect_score": outcome_effect_score(record),
    }
    with OUTCOME_LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(log_row, ensure_ascii=False) + "\n")

    effects = _read_effects()
    raw = effects.get(payload.segment_id, {})
    success_by_zone = dict(raw.get("success_rate_by_speed_zone", {}))
    zone = payload.speed_state or "unknown"
    zone_raw = success_by_zone.get(zone, {"plays": 0, "successes": 0, "success_rate": 0.0})
    zone_plays = int(zone_raw.get("plays", 0)) + 1
    success = (log_row["pace_error_reduction_30s"] or 0.0) > 0 or (log_row["pace_error_reduction_60s"] or 0.0) > 0
    zone_successes = int(zone_raw.get("successes", 0)) + (1 if success else 0)
    success_by_zone[zone] = {
        "plays": zone_plays,
        "successes": zone_successes,
        "success_rate": round(zone_successes / max(1, zone_plays), 4),
    }
    stats = SegmentOutcomeStats(
        segment_id=payload.segment_id,
        track_id=payload.track_id,
        plays=int(raw.get("plays", 0)),
        avg_pace_error_reduction_30s=float(raw.get("avg_pace_error_reduction_30s", 0.0)),
        avg_pace_error_reduction_60s=float(raw.get("avg_pace_error_reduction_60s", 0.0)),
        skip_rate=float(raw.get("skip_rate", 0.0)),
        dislike_rate=float(raw.get("dislike_rate", 0.0)),
        manual_bad_count=int(raw.get("manual_bad_count", 0)),
    )
    stats = update_segment_outcome_stats(stats, record)
    effects[payload.segment_id] = {
        **asdict(stats),
        "success_rate_by_speed_zone": success_by_zone,
        "user_response_effect": round(user_response_effect_from_stats(stats), 4),
    }
    _write_effects(effects)
    return {"logged": True, "outcome": log_row, "segment_user_response_effect": effects[payload.segment_id]}


def segment_user_response_effect(segment_id: str) -> float:
    raw = _read_effects().get(segment_id, {})
    try:
        return float(raw.get("user_response_effect", 0.50))
    except Exception:
        return 0.50


def read_outcome_logs(limit: int = 1000) -> list[dict[str, Any]]:
    if not OUTCOME_LOG_PATH.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in OUTCOME_LOG_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except Exception:
            continue
    return rows[-limit:]


def outcomes_by_decision_id() -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for row in read_outcome_logs():
        decision_id = row.get("decision_id")
        if decision_id:
            out.setdefault(str(decision_id), []).append(row)
    return out
