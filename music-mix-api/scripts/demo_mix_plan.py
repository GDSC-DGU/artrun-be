from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.mix.planner import build_transition_mix_plan
from scripts.segment_json import load_segments


def _action_to_dict(action) -> dict:
    return {
        "offset_sec": action.offset_sec,
        "track": action.track,
        "action": action.action,
        **action.params,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build an MVP EDM transition mix plan from two analyzed segments.")
    parser.add_argument("--current-segment", required=True)
    parser.add_argument("--next-segment", required=True)
    parser.add_argument("--segments-dir", default="outputs")
    args = parser.parse_args()

    by_id = {segment.segment_id: segment for segment in load_segments(args.segments_dir)}
    current = by_id[args.current_segment]
    next_segment = by_id[args.next_segment]
    plan = build_transition_mix_plan(current, next_segment)
    output = {
        "method": plan.method.value,
        "current_exit": {"track_id": current.track_id, "time_sec": plan.current_exit_sec},
        "next_entry": {"track_id": next_segment.track_id, "time_sec": plan.next_entry_sec},
        "duration_bars": plan.duration_bars,
        "duration_sec": round(plan.duration_sec, 3),
        "timeline": [_action_to_dict(action) for action in plan.timeline],
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
