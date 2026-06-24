from __future__ import annotations

import json
import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover
    APIRouter = None

from app.analysis.edm_pace_v3_adapter import segments_to_v3_records
from app.analysis.edm_pace_v3_core import SegmentUse, V3Config, coverage_audit, degree_bin
from app.config.tuning_profiles import active_profile_name, load_active_v3_config
from app.db.json_repository import outputs_repository
from app.paths import EDM_AUDIO_DIR, MANIFESTS_DIR, ROOT_DIR, SEGMENTS_DIR, preferred_audio_dir, preferred_segments_dir


def _resolve_audio_path(path_value: str) -> Path:
    path = Path(path_value)
    if path.is_absolute():
        return path
    return (ROOT_DIR / path).resolve()


def _analysis_summary() -> list[dict[str, Any]]:
    path = preferred_segments_dir() / "batch_analysis_summary.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_rows() -> list[dict[str, str]]:
    path = MANIFESTS_DIR / "edm_sample_manifest.csv"
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _repo_segments():
    return outputs_repository(preferred_segments_dir()).segments


def _records():
    return segments_to_v3_records(_repo_segments(), load_active_v3_config())


def _track_audio_paths() -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for row in _manifest_rows():
        track_id = str(row.get("track_id", ""))
        audio_path = str(row.get("audio_path", ""))
        if track_id and audio_path:
            paths[track_id] = _resolve_audio_path(audio_path)
    for row in _analysis_summary():
        track_id = str(row.get("track_id", ""))
        audio_path = str(row.get("audio_path", ""))
        if track_id and audio_path and track_id not in paths:
            paths[track_id] = _resolve_audio_path(audio_path)
    for segment in _repo_segments():
        if segment.track_id not in paths and segment.audio_url:
            paths[segment.track_id] = _resolve_audio_path(segment.audio_url)
    return paths


def _library_audit() -> dict[str, Any]:
    segments = _repo_segments()
    config = load_active_v3_config()
    records = segments_to_v3_records(segments, config)
    summary = _analysis_summary()
    manifest = _manifest_rows()
    audio_dir = preferred_audio_dir()
    audio_files = sorted(audio_dir.glob("*.mp3"))
    track_paths = _track_audio_paths()
    unique_tracks = {segment.track_id for segment in segments}
    loaded_paths = {path.resolve() for path in track_paths.values()}
    missing = [str(path) for path in track_paths.values() if not path.exists()]
    unreferenced = [str(path.resolve()) for path in audio_files if path.resolve() not in loaded_paths]
    failed_analysis = [
        str(row.get("track_id") or row.get("audio_path"))
        for row in summary
        if row.get("error") or row.get("failed")
    ]
    by_bin: dict[str, set[str]] = defaultdict(set)
    for record in records:
        by_bin[degree_bin(record.pace.music_speed_degree, config.degree_bin_size)].add(record.track_id)
    return {
        "active_tuning_profile": config.active_tuning_profile,
        "audio_files_count": len(audio_files),
        "manifest_track_count": len(manifest) if manifest else len(summary),
        "tracks_loaded_count": len(unique_tracks),
        "tracks_analyzed_count": len(summary),
        "segments_generated_count": len(segments),
        "valid_runtime_segments_count": sum(1 for record in records if record.block.valid_runtime_block),
        "stable_segment_count": sum(1 for record in records if record.segment_use == SegmentUse.STABLE.value),
        "drive_connector_count": sum(1 for record in records if record.segment_use == SegmentUse.DRIVE_CONNECTOR.value),
        "unique_track_count": len(unique_tracks),
        "unique_track_count_by_degree_bin": {key: len(value) for key, value in sorted(by_bin.items())},
        "missing_audio_file_paths": missing,
        "unreferenced_audio_files": unreferenced,
        "failed_downloads": [],
        "failed_analysis_tracks": failed_analysis,
    }


def _segment_rows() -> list[dict[str, Any]]:
    segments = _repo_segments()
    config = load_active_v3_config()
    records = {record.segment_id: record for record in segments_to_v3_records(segments, config)}
    track_paths = _track_audio_paths()
    rows: list[dict[str, Any]] = []
    for segment in segments:
        record = records[segment.segment_id]
        audio_path = track_paths.get(segment.track_id) or _resolve_audio_path(segment.audio_url)
        rows.append(
            {
                "segment_id": segment.segment_id,
                "track_id": segment.track_id,
                "audio_file_path": str(audio_path),
                "audio_file_exists": audio_path.exists(),
                "source_url": segment.metadata.get("source_url") or segment.metadata.get("source"),
                "license": segment.metadata.get("license") or segment.metadata.get("license_name"),
                "segment_start_sec": segment.start_sec,
                "segment_end_sec": segment.end_sec,
                "segment_use": record.segment_use,
                "music_speed_degree": round(record.pace.music_speed_degree, 4),
                "valid_runtime_block": record.block.valid_runtime_block,
                "disabled_from_runtime": record.manual_disabled or record.segment_use == SegmentUse.REJECT.value,
            }
        )
    return rows


if APIRouter is not None:
    router = APIRouter(prefix="/debug", tags=["debug"])

    @router.get("/audio-library")
    def audio_library():
        return {
            **_library_audit(),
            "audio_dir": str(preferred_audio_dir()),
            "segments_dir": str(preferred_segments_dir()),
            "using_data_audio_dir": preferred_audio_dir() == EDM_AUDIO_DIR,
            "using_data_segments_dir": preferred_segments_dir() == SEGMENTS_DIR,
        }

    @router.get("/segment-db")
    def segment_db():
        rows = _segment_rows()
        use_counts = Counter(row["segment_use"] for row in rows)
        return {
            **_library_audit(),
            "segment_use_counts": dict(use_counts),
            "segments": rows,
        }

    @router.get("/coverage-audit")
    def coverage():
        records = _records()
        return {
            **_library_audit(),
            "coverage_audit": [row.as_dict() for row in coverage_audit(records, load_active_v3_config())],
        }
else:
    router = None
