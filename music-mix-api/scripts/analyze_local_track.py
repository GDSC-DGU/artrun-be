from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.pipeline import analysis_to_jsonable, analyze_track, segment_to_dict


def main():
    parser = argparse.ArgumentParser(description="Analyze one local music track and emit analysis JSON.")
    parser.add_argument("audio_path")
    parser.add_argument("--track-id", required=True)
    parser.add_argument("--profile", default="basic", choices=["basic", "precise"])
    parser.add_argument("--out-dir", default="outputs")
    args = parser.parse_args()

    result = analyze_track(args.track_id, args.audio_path, args.profile)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    analysis_path = out_dir / f"{args.track_id}_analysis.json"
    segments_path = out_dir / f"{args.track_id}_segments.json"

    analysis_json = analysis_to_jsonable(result)
    segments_json = {
        "track_id": result["track_id"],
        "audio_path": result["audio_path"],
        "duration_sec": result["duration_sec"],
        "bpm": result["bpm"],
        "segments": [segment_to_dict(segment) for segment in result["segments"]],
    }
    analysis_path.write_text(json.dumps(analysis_json, ensure_ascii=False, indent=2), encoding="utf-8")
    segments_path.write_text(json.dumps(segments_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(analysis_path)
    print(segments_path)


if __name__ == "__main__":
    main()
