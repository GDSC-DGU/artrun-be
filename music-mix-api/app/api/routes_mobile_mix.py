from __future__ import annotations

try:
    from fastapi import APIRouter, HTTPException
except Exception:  # pragma: no cover
    APIRouter = None
    HTTPException = Exception

from app.db.json_repository import outputs_repository
from app.mix.planner import build_transition_mix_plan
from app.paths import preferred_segments_dir
from app.schemas.mobile import MixPlanRequest


def _action_to_dict(action) -> dict:
    return {
        "offset_sec": action.offset_sec,
        "track": action.track,
        "action": action.action,
        **action.params,
    }


if APIRouter is not None:
    router = APIRouter(prefix="/api/v1/mobile", tags=["mobile-mix"])

    @router.post("/mix-plans")
    def mix_plan(req: MixPlanRequest):
        repo = outputs_repository(preferred_segments_dir())
        current = repo.get_segment(req.current_segment_id)
        next_segment = repo.get_segment(req.next_segment_id)
        if current is None:
            raise HTTPException(status_code=404, detail=f"Unknown current_segment_id: {req.current_segment_id}")
        if next_segment is None:
            raise HTTPException(status_code=404, detail=f"Unknown next_segment_id: {req.next_segment_id}")

        plan = build_transition_mix_plan(current, next_segment, req.current_position_sec)
        return {
            "method": plan.method.value,
            "current_exit": {"track_id": current.track_id, "time_sec": plan.current_exit_sec},
            "next_entry": {"track_id": next_segment.track_id, "time_sec": plan.next_entry_sec},
            "duration_bars": plan.duration_bars,
            "duration_sec": round(plan.duration_sec, 3),
            "timeline": [_action_to_dict(action) for action in plan.timeline],
        }
else:
    router = None
