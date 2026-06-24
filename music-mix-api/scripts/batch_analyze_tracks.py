from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.pipeline import analysis_to_jsonable, analyze_track, segment_to_dict


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze all local mp3 files in a directory.")
    parser.add_argument("samples_dir")
    parser.add_argument("--out-dir", default="outputs")
    parser.add_argument("--profile", default="basic", choices=["basic", "precise"])
    args = parser.parse_args()

    samples_dir = Path(args.samples_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    summary = []
    for audio_path in sorted(samples_dir.glob("*.mp3")):
        track_id = audio_path.stem
        result = analyze_track(track_id, audio_path, args.profile)
        analysis_json = analysis_to_jsonable(result)
        segments_json = {
            "track_id": result["track_id"],
            "audio_path": result["audio_path"],
            "duration_sec": result["duration_sec"],
            "bpm": result["bpm"],
            "segments": [segment_to_dict(segment) for segment in result["segments"]],
        }
        (out_dir / f"{track_id}_analysis.json").write_text(json.dumps(analysis_json, ensure_ascii=False, indent=2), encoding="utf-8")
        (out_dir / f"{track_id}_segments.json").write_text(json.dumps(segments_json, ensure_ascii=False, indent=2), encoding="utf-8")
        levels = [segment.energy_level for segment in result["segments"]]
        summary.append(
            {
                "track_id": track_id,
                "audio_path": str(audio_path),
                "duration_sec": result["duration_sec"],
                "bpm": result["bpm"],
                "segment_count": len(result["segments"]),
                "min_energy_level": min(levels) if levels else None,
                "max_energy_level": max(levels) if levels else None,
                "avg_energy_score": result["avg_energy_score"],
            }
        )
        print(f"analyzed {track_id}: {len(result['segments'])} segments")

    (out_dir / "batch_analysis_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_dir / "batch_analysis_summary.json")


if __name__ == "__main__":
    main()
