from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.analysis.edm_pace_v3_adapter import segments_to_v3_records
from app.analysis.edm_pace_v3_core import SegmentUse, V3Config, coverage_audit, degree_bin
from app.analysis.pipeline import analysis_to_jsonable, analyze_track, segment_to_dict
from app.paths import EDM_AUDIO_DIR, MANIFESTS_DIR, SEGMENTS_DIR


IGNORED_SUFFIXES = {".tmp", ".temp", ".crdownload", ".part", ".download"}


def discover_mp3_files(source_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source_dir.iterdir()):
        if not path.is_file():
            continue
        suffix = path.suffix.lower()
        if suffix in IGNORED_SUFFIXES:
            continue
        if suffix == ".mp3":
            files.append(path)
    return files


def copy_audio_files(source_dir: Path, audio_dir: Path) -> list[Path]:
    audio_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in discover_mp3_files(source_dir):
        target = audio_dir / source.name
        if not target.exists() or target.stat().st_size != source.stat().st_size:
            shutil.copy2(source, target)
        copied.append(target)
    return copied


def track_title_from_file(path: Path) -> str:
    title = path.stem.replace("_", " ").replace("-", " ")
    return " ".join(title.split())


def build_manifest(audio_files: list[Path]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, audio_path in enumerate(audio_files, start=1):
        track_id = f"edm_{index:03d}"
        rows.append(
            {
                "track_id": track_id,
                "track_title": track_title_from_file(audio_path),
                "audio_file_name": audio_path.name,
                "audio_path": str(audio_path),
                "source_url": "",
                "license": "",
            }
        )
    return rows


def write_manifest(rows: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["track_id", "track_title", "audio_file_name", "audio_path", "source_url", "license"],
        )
        writer.writeheader()
        writer.writerows(rows)


def enrich_segments(result: dict[str, Any], manifest_row: dict[str, str]):
    enriched = []
    metadata = {
        "track_title": manifest_row["track_title"],
        "audio_file_name": manifest_row["audio_file_name"],
        "manifest_track_id": manifest_row["track_id"],
        "source_url": manifest_row.get("source_url", ""),
        "license": manifest_row.get("license", ""),
    }
    for segment in result["segments"]:
        enriched.append(replace(segment, metadata={**segment.metadata, **metadata}))
    return enriched


def write_track_outputs(result: dict[str, Any], segments, out_dir: Path) -> dict[str, Any]:
    analysis_json = analysis_to_jsonable({**result, "segments": segments})
    segments_json = {
        "track_id": result["track_id"],
        "audio_path": result["audio_path"],
        "duration_sec": result["duration_sec"],
        "bpm": result["bpm"],
        "segments": [segment_to_dict(segment) for segment in segments],
    }
    (out_dir / f"{result['track_id']}_analysis.json").write_text(
        json.dumps(analysis_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / f"{result['track_id']}_segments.json").write_text(
        json.dumps(segments_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return segments_json


def build_audit(
    manifest_rows: list[dict[str, str]],
    analyzed_rows: list[dict[str, Any]],
    failed_rows: list[dict[str, Any]],
    all_segments,
) -> dict[str, Any]:
    records = segments_to_v3_records(all_segments, V3Config())
    by_bin: dict[str, set[str]] = {}
    for record in records:
        key = degree_bin(record.pace.music_speed_degree, V3Config().degree_bin_size)
        by_bin.setdefault(key, set()).add(record.track_id)
    return {
        "audio_files_count": len(manifest_rows),
        "manifest_track_count": len(manifest_rows),
        "tracks_loaded_count": len({row["track_id"] for row in manifest_rows}),
        "tracks_analyzed_count": len(analyzed_rows),
        "segments_generated_count": len(all_segments),
        "valid_runtime_segments_count": sum(1 for record in records if record.block.valid_runtime_block),
        "stable_segment_count": sum(1 for record in records if record.segment_use == SegmentUse.STABLE.value),
        "drive_connector_count": sum(1 for record in records if record.segment_use == SegmentUse.DRIVE_CONNECTOR.value),
        "unique_track_count": len({segment.track_id for segment in all_segments}),
        "unique_track_count_by_degree_bin": {key: len(value) for key, value in sorted(by_bin.items())},
        "missing_audio_file_paths": [row["audio_path"] for row in manifest_rows if not Path(row["audio_path"]).exists()],
        "unreferenced_audio_files": [],
        "failed_downloads": [],
        "failed_analysis_tracks": failed_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Copy and analyze local EDM MP3 samples into data/.")
    parser.add_argument("--source-dir", default=r"D:\running\SAMPLE_V2")
    parser.add_argument("--audio-dir", default=str(EDM_AUDIO_DIR))
    parser.add_argument("--manifest", default=str(MANIFESTS_DIR / "edm_sample_manifest.csv"))
    parser.add_argument("--segments-dir", default=str(SEGMENTS_DIR))
    parser.add_argument("--profile", default="basic", choices=["basic", "precise"])
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    audio_dir = Path(args.audio_dir)
    manifest_path = Path(args.manifest)
    segments_dir = Path(args.segments_dir)
    segments_dir.mkdir(parents=True, exist_ok=True)

    copied_files = copy_audio_files(source_dir, audio_dir)
    manifest_rows = build_manifest(copied_files)
    write_manifest(manifest_rows, manifest_path)

    analyzed_rows: list[dict[str, Any]] = []
    failed_rows: list[dict[str, Any]] = []
    all_segments = []
    track_payloads = []

    for row in manifest_rows:
        try:
            result = analyze_track(row["track_id"], row["audio_path"], args.profile)
            segments = enrich_segments(result, row)
            track_payloads.append(write_track_outputs(result, segments, segments_dir))
            all_segments.extend(segments)
            levels = [segment.energy_level for segment in segments]
            analyzed_rows.append(
                {
                    "track_id": row["track_id"],
                    "track_title": row["track_title"],
                    "audio_file_name": row["audio_file_name"],
                    "audio_path": row["audio_path"],
                    "duration_sec": result["duration_sec"],
                    "bpm": result["bpm"],
                    "segment_count": len(segments),
                    "min_energy_level": min(levels) if levels else None,
                    "max_energy_level": max(levels) if levels else None,
                    "avg_energy_score": result["avg_energy_score"],
                }
            )
            print(f"analyzed {row['track_id']}: {row['audio_file_name']} -> {len(segments)} segments")
        except Exception as exc:
            failed = {
                "track_id": row["track_id"],
                "track_title": row["track_title"],
                "audio_file_name": row["audio_file_name"],
                "audio_path": row["audio_path"],
                "error": str(exc),
            }
            failed_rows.append(failed)
            print(f"failed {row['track_id']}: {row['audio_file_name']} -> {exc}")

    audit = build_audit(manifest_rows, analyzed_rows, failed_rows, all_segments)
    records = segments_to_v3_records(all_segments, V3Config()) if all_segments else []
    db_payload = {
        "manifest_path": str(manifest_path),
        "audio_dir": str(audio_dir),
        "segments_dir": str(segments_dir),
        "audit": audit,
        "coverage_audit": [row.as_dict() for row in coverage_audit(records, V3Config())],
        "tracks": analyzed_rows,
        "failed_tracks": failed_rows,
        "segments": [segment_to_dict(segment) for segment in all_segments],
    }

    (segments_dir / "batch_analysis_summary.json").write_text(
        json.dumps(analyzed_rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (segments_dir / "edm_segment_db.json").write_text(
        json.dumps(db_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"ingestion_audit": audit}, ensure_ascii=False, indent=2))
    print(json.dumps({"coverage_audit": db_payload["coverage_audit"]}, ensure_ascii=False, indent=2))
    print(segments_dir / "edm_segment_db.json")


if __name__ == "__main__":
    main()
