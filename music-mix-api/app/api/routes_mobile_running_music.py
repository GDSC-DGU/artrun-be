from __future__ import annotations

try:
    from fastapi import APIRouter
except Exception:  # pragma: no cover
    APIRouter = None

from app.analysis.ai_music_segment_analyzer import AI_SEGMENT_ANALYSIS_KEYS
from app.analysis.multi_model_pace_feature_core import MULTI_MODEL_METADATA_KEYS
from app.analysis.pace_assist_analyzer_v3_4 import PACE_ASSIST_V3_4_FEATURE_KEYS
from app.analysis.pace_assist_features import PACE_ASSIST_FEATURE_KEYS
from app.analysis.speed_degree_pace_features_v2 import SPEED_DEGREE_V2_METADATA_KEYS
from app.domain.models import (
    RunningContext,
    PlaybackContext,
    ClientContext,
    RecommendationConstraints,
    Segment,
    SectionType,
)
from app.db.json_repository import outputs_repository
from app.db.repositories import InMemorySegmentRepository
from app.paths import preferred_segments_dir
from app.recommendation.segment_selector import get_mobile_next_segment
from app.recommendation.queue_builder import build_segment_queue
from app.recommendation.pace_assist_outcomes import log_outcome
from app.recommendation.decision_logging import build_decision_log, write_decision_log
from app.schemas.mobile import NextSegmentRequest


def demo_repository() -> InMemorySegmentRepository:
    # Replace with PostgreSQL repository in production.
    return InMemorySegmentRepository(
        [
            Segment("seg_drop_001", "track_A", "https://cdn.example.com/track_A.mp3", 58.24, 118.40, 33, 64, SectionType.DROP, 0.91, 5, 128.1, 0.88),
            Segment("seg_build_001", "track_B", "https://cdn.example.com/track_B.mp3", 30.10, 72.00, 17, 40, SectionType.BUILD_UP, 0.76, 4, 126.0, 0.82),
            Segment("seg_groove_001", "track_C", "https://cdn.example.com/track_C.mp3", 15.00, 75.00, 9, 40, SectionType.GROOVE, 0.55, 3, 92.0, 0.75),
            Segment("seg_cool_001", "track_D", "https://cdn.example.com/track_D.mp3", 10.00, 70.00, 5, 36, SectionType.BREAKDOWN, 0.32, 2, 84.0, 0.70),
        ]
    )


def repository() -> InMemorySegmentRepository:
    repo = outputs_repository(preferred_segments_dir())
    if repo.segments:
        return repo
    return demo_repository()


def segment_payload(segment: Segment) -> dict:
    audio_name = segment.metadata.get("audio_file_name")
    if not audio_name:
        audio_name = f"{segment.track_id}.mp3"
    payload = {
        "segment_id": segment.segment_id,
        "track_id": segment.track_id,
        "audio_url": f"/audio/{audio_name}",
        "track_title": segment.metadata.get("track_title", segment.track_id),
        "audio_file_name": audio_name,
        "start_sec": segment.start_sec,
        "end_sec": segment.end_sec,
        "section_type": segment.section_type.value,
        "energy_score": segment.energy_score,
        "energy_level": segment.energy_level,
        "bpm": segment.bpm,
        "phrase_confidence": segment.phrase_confidence,
        "volume_score": segment.volume_score,
        "brightness_score": segment.brightness_score,
        "onset_density_score": segment.onset_density_score,
        "sound_density_score": segment.sound_density_score,
    }
    for key in PACE_ASSIST_FEATURE_KEYS:
        if key in segment.metadata:
            payload[key] = segment.metadata[key]
    for key in AI_SEGMENT_ANALYSIS_KEYS:
        if key in segment.metadata:
            payload[key] = segment.metadata[key]
    for key in MULTI_MODEL_METADATA_KEYS:
        if key in segment.metadata:
            payload[key] = segment.metadata[key]
    for key in SPEED_DEGREE_V2_METADATA_KEYS:
        if key in segment.metadata:
            payload[key] = segment.metadata[key]
    for key in PACE_ASSIST_V3_4_FEATURE_KEYS:
        if key in segment.metadata:
            payload[key] = segment.metadata[key]
    for key in ("entry_quality", "exit_quality", "loudness_density_score", "segment_clip_path", "phrase_bar_multiple"):
        if key in segment.metadata:
            payload[key] = segment.metadata[key]
    if "pace_assist_debug" in segment.metadata:
        payload["pace_assist_debug"] = segment.metadata["pace_assist_debug"]
    if "section_type_original" in segment.metadata:
        payload["section_type_original"] = segment.metadata["section_type_original"]
    return payload


if APIRouter is not None:
    router = APIRouter(prefix="/api/v1/mobile/running-music", tags=["mobile-running-music"])

    @router.post("/next-segment")
    def next_segment(req: NextSegmentRequest):
        repo = repository()
        rc = RunningContext(**req.running_context.model_dump())
        pc = PlaybackContext(**req.playback_context.model_dump())
        cc = ClientContext(**req.client_context.model_dump())
        constraints = RecommendationConstraints(**req.constraints.model_dump())
        rec = get_mobile_next_segment(repo, rc, pc, cc, constraints)
        current_segment = next((segment for segment in repo.segments if segment.segment_id == pc.current_segment_id), None)
        source = "smoke_test" if req.session_id.startswith("smoke") else "mobile"
        decision = write_decision_log(
            build_decision_log(
                session_id=req.session_id,
                source=source,
                running_context=rc,
                playback_context=pc,
                recommendation=rec,
                current_segment=current_segment,
            )
        )
        rec.reason["decision_id"] = decision["decision_id"]
        rec.reason["decision_log"] = {
            key: decision.get(key)
            for key in (
                "decision_id",
                "route",
                "current_music_ASC_spm",
                "desired_next_ASC_spm",
                "candidate_ASC_spm",
                "ASC_lift_from_current_music",
                "asc_target_delta",
                "pace_assist_score",
                "estimated_change_latency_sec",
                "fallback_reason",
                "reject_summary",
            )
        }
        return rec

    @router.post("/segment-queue")
    def segment_queue(req: NextSegmentRequest, queue_size: int = 3):
        repo = repository()
        rc = RunningContext(**req.running_context.model_dump())
        pc = PlaybackContext(**req.playback_context.model_dump())
        constraints = RecommendationConstraints(**req.constraints.model_dump())
        return {"queue": build_segment_queue(repo, rc, pc, queue_size=queue_size, constraints=constraints), "expires_in_sec": 180}

    @router.get("/segments")
    def analyzed_segments():
        repo = repository()
        return {"segments": [segment_payload(segment) for segment in repo.segments]}

    @router.post("/outcomes")
    def pace_assist_outcomes(payload: dict):
        return log_outcome(payload)
else:
    router = None
