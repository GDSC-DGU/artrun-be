from __future__ import annotations

import json
from pathlib import Path

from app.analysis.ai_music_segment_analyzer import AI_SEGMENT_ANALYSIS_KEYS
from app.analysis.multi_model_pace_feature_core import MULTI_MODEL_METADATA_KEYS
from app.analysis.pace_assist_analyzer_v3_4 import PACE_ASSIST_V3_4_FEATURE_KEYS
from app.analysis.pace_assist_features import PACE_ASSIST_FEATURE_KEYS
from app.analysis.speed_degree_pace_features_v2 import SPEED_DEGREE_V2_METADATA_KEYS
from app.db.repositories import InMemorySegmentRepository
from app.domain.models import Segment, SectionType
from app.paths import DATA_DIR
from app.recommendation.pace_assist_outcomes import segment_user_response_effect

BLOCKED_TRACKS_PATH = DATA_DIR / "config" / "blocked_tracks.json"


def load_blocked_tracks(path: str | Path = BLOCKED_TRACKS_PATH) -> dict[str, set[str]]:
    path = Path(path)
    if not path.exists():
        return {"track_ids": set(), "track_titles": set(), "audio_file_names": set()}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = {"track_ids": payload}
    return {
        "track_ids": {str(value).strip().lower() for value in payload.get("track_ids", []) if str(value).strip()},
        "track_titles": {str(value).strip().lower() for value in payload.get("track_titles", []) if str(value).strip()},
        "audio_file_names": {
            str(value).strip().lower() for value in payload.get("audio_file_names", []) if str(value).strip()
        },
    }


def is_blocked_track(data: dict, payload: dict, blocked: dict[str, set[str]]) -> bool:
    metadata = data.get("metadata", {})
    audio_path = str(data.get("audio_path") or payload.get("audio_path") or "")
    audio_file_name = str(
        data.get("audio_file_name")
        or metadata.get("audio_file_name")
        or payload.get("audio_file_name")
        or Path(audio_path).name
    ).lower()
    track_title = str(data.get("track_title") or metadata.get("track_title") or payload.get("track_title") or "").lower()
    track_id = str(data.get("track_id") or payload.get("track_id") or "").lower()
    return (
        track_id in blocked["track_ids"]
        or track_title in blocked["track_titles"]
        or audio_file_name in blocked["audio_file_names"]
    )


def segment_from_dict(data: dict) -> Segment:
    metadata = dict(data.get("metadata", {}))
    for key in PACE_ASSIST_FEATURE_KEYS:
        if key in data:
            metadata[key] = data[key]
    for key in AI_SEGMENT_ANALYSIS_KEYS:
        if key in data:
            metadata[key] = data[key]
    for key in MULTI_MODEL_METADATA_KEYS:
        if key in data:
            metadata[key] = data[key]
    for key in SPEED_DEGREE_V2_METADATA_KEYS:
        if key in data:
            metadata[key] = data[key]
    for key in PACE_ASSIST_V3_4_FEATURE_KEYS:
        if key in data:
            metadata[key] = data[key]
    for key in ("entry_quality", "exit_quality", "loudness_density_score", "segment_clip_path", "phrase_bar_multiple"):
        if key in data:
            metadata[key] = data[key]
    if "pace_assist_debug" in data:
        metadata["pace_assist_debug"] = data["pace_assist_debug"]
    if "section_type_original" in data:
        metadata["section_type_original"] = data["section_type_original"]
    metadata["user_response_effect"] = segment_user_response_effect(data["segment_id"])

    return Segment(
        segment_id=data["segment_id"],
        track_id=data["track_id"],
        audio_url=data.get("audio_url") or data.get("audio_path") or "",
        start_sec=float(data["start_sec"]),
        end_sec=float(data["end_sec"]),
        start_bar=int(data["start_bar"]),
        end_bar=int(data["end_bar"]),
        section_type=SectionType(data["section_type"]),
        energy_score=float(data["energy_score"]),
        energy_level=int(data["energy_level"]),
        bpm=float(data["bpm"]),
        phrase_confidence=float(data.get("phrase_confidence", 0.0)),
        is_good_entry=bool(data.get("is_good_entry", True)),
        is_good_exit=bool(data.get("is_good_exit", True)),
        model_section_label=data.get("model_section_label"),
        final_section_label=data.get("final_section_label"),
        volume_score=float(data.get("volume_score", 0.0)),
        brightness_score=float(data.get("brightness_score", 0.0)),
        onset_density_score=float(data.get("onset_density_score", 0.0)),
        sound_density_score=float(data.get("sound_density_score", 0.0)),
        drum_density_score=data.get("drum_density_score"),
        bass_strength_score=data.get("bass_strength_score"),
        mobile_preload_priority=int(data.get("mobile_preload_priority", 0)),
        metadata=metadata,
    )


def load_segments(segments_dir: str | Path = "outputs") -> list[Segment]:
    segments: list[Segment] = []
    blocked = load_blocked_tracks()
    for path in sorted(Path(segments_dir).glob("*_segments.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for item in payload.get("segments", []):
            item.setdefault("audio_path", payload.get("audio_path", ""))
            if is_blocked_track(item, payload, blocked):
                continue
            segments.append(segment_from_dict(item))
    return segments


def outputs_repository(segments_dir: str | Path = "outputs") -> InMemorySegmentRepository:
    return InMemorySegmentRepository(load_segments(segments_dir))
