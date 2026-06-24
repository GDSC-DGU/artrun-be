from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.repositories import InMemorySegmentRepository
from app.domain.models import PlaybackContext, RecommendationConstraints, RunningContext
from app.recommendation.segment_selector import get_mobile_next_segment
from scripts.segment_json import load_segments, segment_to_plain_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Select a pre-analyzed segment for a running state.")
    parser.add_argument("--segments-dir", default="outputs")
    parser.add_argument("--current-pace", type=float, required=True)
    parser.add_argument("--target-pace", type=float, required=True)
    parser.add_argument("--mode", default="steady_run")
    parser.add_argument("--target-cadence", type=float, default=172.0)
    args = parser.parse_args()

    segments = load_segments(args.segments_dir)
    repo = InMemorySegmentRepository(segments)
    running = RunningContext(
        current_pace_sec_per_km=args.current_pace,
        target_pace_sec_per_km=args.target_pace,
        running_mode=args.mode,
        target_cadence_spm=args.target_cadence,
    )
    playback = PlaybackContext(
        current_segment_played_sec=45.0,
        seconds_since_last_switch=60.0,
        previous_target_energy=0.55 if args.mode == "cool_down" else 0.35,
    )
    constraints = RecommendationConstraints(
        min_segment_duration_sec=20.0,
        max_segment_duration_sec=90.0,
        allow_same_track=True,
        energy_window=0.35,
    )
    rec = get_mobile_next_segment(repo, running, playback, constraints=constraints)
    output = {
        "target_energy_score": round(rec.decision.target_energy_score, 4),
        "target_energy_level": rec.decision.target_energy_level,
        "speed_gap_ratio": round(rec.decision.speed_gap_ratio, 4),
        "selected_segment": segment_to_plain_dict(rec.selected_segment) if rec.selected_segment else None,
        "selection_reason": rec.reason,
    }
    if rec.selected_segment:
        output["selection_reason"] = {
            **rec.reason,
            "target_energy_reason": rec.decision.main_reason,
        }
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
