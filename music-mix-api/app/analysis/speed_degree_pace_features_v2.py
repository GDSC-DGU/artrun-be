from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any, Iterable

from app.analysis.multi_model_pace_features import effective_pulse_from_bpm
from app.analysis.speed_degree_pace_core_v2 import (
    ModelFeatureScoresV2,
    PaceFeatureVectorV2,
    RhythmSignalFeaturesV2,
    SegmentAnalysisV2,
    SegmentUse,
    StructureFieldsV2,
    TimbreEnergyFeaturesV2,
    TransitionType,
    build_pace_feature_vector_v2,
    clamp,
    clamp01,
)
from app.domain.models import Segment


SPEED_DEGREE_V2_METADATA_KEYS = (
    "music_speed_degree",
    "transition_slope",
    "pace_feature_vector_v2",
    "speed_degree_v2_analysis",
    "intro_like_score",
    "pulse_drop_score",
    "drive_preservation_score",
    "connector_drive_score",
)


def annotate_segments_with_speed_degree_v2(segments: Iterable[Segment]) -> list[Segment]:
    annotated: list[Segment] = []
    for segment in segments:
        analysis = build_segment_analysis_v2_from_segment(segment)
        metadata = {
            **segment.metadata,
            "music_speed_degree": round(analysis.pace_vector.music_speed_degree, 4),
            "transition_slope": round(analysis.pace_vector.transition_slope, 4),
            "pace_feature_vector_v2": pace_vector_v2_to_dict(analysis.pace_vector),
            "speed_degree_v2_analysis": asdict(analysis),
            "intro_like_score": round(analysis.pace_vector.intro_like_score, 4),
            "pulse_drop_score": round(analysis.pace_vector.pulse_drop_score, 4),
            "drive_preservation_score": round(analysis.pace_vector.drive_preservation_score, 4),
            "connector_drive_score": round(analysis.pace_vector.connector_drive_score, 4),
        }
        annotated.append(replace(segment, metadata=metadata))
    return annotated


def build_segment_analysis_v2_from_segment(segment: Segment) -> SegmentAnalysisV2:
    structure = structure_v2_from_segment(segment)
    rhythm = rhythm_v2_from_segment(segment)
    timbre = timbre_v2_from_segment(segment)
    model = model_v2_from_segment(segment)
    vector = build_pace_feature_vector_v2(structure=structure, rhythm=rhythm, timbre=timbre, model=model)
    return SegmentAnalysisV2(structure=structure, rhythm=rhythm, timbre=timbre, model=model, pace_vector=vector)


def structure_v2_from_segment(segment: Segment) -> StructureFieldsV2:
    segment_use = str(segment.metadata.get("segment_use") or infer_segment_use(segment))
    transition_type = str(segment.metadata.get("transition_type") or infer_transition_type(segment, segment_use))
    slope = _raw_float(segment.metadata.get("transition_slope"), slope_from_segment(segment, segment_use))
    flow_direction = "up" if slope > 0.25 else "down" if slope < -0.25 else "flat"
    duration_bars = max(1, int(segment.end_bar - segment.start_bar + 1))
    return StructureFieldsV2(
        segment_id=segment.segment_id,
        track_id=segment.track_id,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        start_bar=segment.start_bar,
        end_bar=segment.end_bar,
        duration_bars=duration_bars,
        segment_use=segment_use,
        transition_type=transition_type,
        transition_slope=round(clamp(slope, -1.0, 1.0), 4),
        flow_direction=flow_direction,
        target_after_transition=segment.metadata.get("target_after_transition"),
        entry_quality=_score(segment.metadata.get("entry_quality"), segment.phrase_confidence),
        exit_quality=_score(segment.metadata.get("exit_quality"), segment.phrase_confidence),
        phrase_confidence=clamp01(segment.phrase_confidence),
        is_contiguous_original_audio=bool(segment.metadata.get("is_contiguous_original_audio", True)),
    )


def rhythm_v2_from_segment(segment: Segment) -> RhythmSignalFeaturesV2:
    effective, relation = effective_pulse_from_bpm(segment.bpm)
    vector = segment.metadata.get("pace_feature_vector")
    if not isinstance(vector, dict):
        vector = {}
    return RhythmSignalFeaturesV2(
        bpm=float(segment.bpm),
        effective_pulse_bpm=_raw_float(segment.metadata.get("effective_pulse_bpm"), effective),
        pulse_relation=str(segment.metadata.get("pulse_relation") or relation),
        beat_confidence=_score(segment.metadata.get("beat_confidence"), max(0.45, segment.phrase_confidence)),
        downbeat_confidence=_score(segment.metadata.get("downbeat_confidence"), max(0.40, segment.phrase_confidence - 0.05)),
        cadence_lock_support=_score(
            vector.get("cadence_lock_support"),
            _score(segment.metadata.get("ai_cadence_lock_score"), segment.phrase_confidence),
        ),
        beat_salience_score=_score(segment.metadata.get("beat_salience_score"), segment.onset_density_score),
        onset_density_score=clamp01(segment.onset_density_score),
        rhythm_predictability_score=_score(
            segment.metadata.get("rhythm_predictability_score"),
            _score(segment.metadata.get("rhythmic_predictability_score"), segment.phrase_confidence),
        ),
        groove_stability_score=_score(
            segment.metadata.get("groove_stability_score"),
            _score(segment.metadata.get("ai_groove_score"), segment.phrase_confidence),
        ),
        tempogram_strength_score=_score(
            segment.metadata.get("tempogram_strength_score"),
            _score(segment.metadata.get("rhythmic_activity_score"), segment.onset_density_score),
        ),
    )


def timbre_v2_from_segment(segment: Segment) -> TimbreEnergyFeaturesV2:
    bass = _score(segment.metadata.get("bass_modulation_score"), _score(segment.metadata.get("ai_bass_drive_score"), 0.35))
    static_low = _score(segment.metadata.get("static_low_end_penalty"), _score(segment.metadata.get("ai_static_low_end_penalty"), 0.0))
    loudness_density = _score(
        segment.metadata.get("loudness_density_score"),
        0.55 * segment.volume_score + 0.45 * segment.sound_density_score,
    )
    return TimbreEnergyFeaturesV2(
        bass_energy_score=_score(segment.metadata.get("bass_energy_score"), bass),
        bass_modulation_score=bass,
        low_end_stability_score=_score(segment.metadata.get("low_end_stability_score"), 1.0 - static_low),
        loudness_density_score=loudness_density,
        loudness_change_score=_score(segment.metadata.get("loudness_change_score"), _score(segment.metadata.get("section_contrast_score"), 0.2)),
        spectral_brightness_score=_score(segment.metadata.get("spectral_brightness_score"), segment.brightness_score),
        brightness_change_score=_score(segment.metadata.get("brightness_change_score"), _score(segment.metadata.get("section_contrast_score"), 0.2)),
        static_loop_penalty=_score(segment.metadata.get("static_loop_penalty"), _score(segment.metadata.get("ai_static_loop_penalty"), static_low * 0.7)),
        static_low_end_penalty=static_low,
        chaos_penalty=_score(segment.metadata.get("chaos_penalty"), _score(segment.metadata.get("ai_chaos_penalty"), 0.08)),
    )


def model_v2_from_segment(segment: Segment) -> ModelFeatureScoresV2:
    model_speed = _optional_score(segment.metadata.get("model_speed_degree"))
    if model_speed is None and isinstance(segment.metadata.get("pace_feature_vector"), dict):
        vector = segment.metadata["pace_feature_vector"]
        push = _optional_score(vector.get("pace_push_score"))
        flow = _optional_score(vector.get("flow_momentum_score"))
        sprint = _optional_score(vector.get("sprint_support_score"))
        if push is not None and flow is not None:
            model_speed = clamp01(0.45 * push + 0.40 * flow + 0.15 * (sprint or push))
    semantic_speed = _semantic_speed_degree(segment)
    return ModelFeatureScoresV2(
        model_speed_degree=model_speed,
        model_drive_score=_optional_score(segment.metadata.get("mert_drive_score")),
        model_groove_score=_optional_score(segment.metadata.get("mert_groove_score")),
        model_transition_score=_optional_score(segment.metadata.get("mert_transition_score")),
        model_stability_score=_optional_score(segment.metadata.get("mert_stability_score")),
        model_confidence=_score(segment.metadata.get("mert_confidence"), 0.0) if model_speed is not None else 0.0,
        semantic_speed_degree=semantic_speed,
        semantic_confidence=_score(segment.metadata.get("semantic_confidence"), 0.0) if semantic_speed is not None else 0.0,
    )


def infer_segment_use(segment: Segment) -> str:
    section = str(segment.metadata.get("ai_corrected_section_type") or segment.section_type.value).split(".")[-1].lower()
    if segment.phrase_confidence < 0.45:
        return SegmentUse.REJECT.value
    if section == "build_up":
        return SegmentUse.TRANSITION.value
    if section == "intro":
        return SegmentUse.ENTRY_ONLY.value
    if section in {"breakdown", "outro"}:
        return SegmentUse.EXIT_ONLY.value
    return SegmentUse.STABLE.value


def infer_transition_type(segment: Segment, segment_use: str) -> str:
    section = str(segment.metadata.get("ai_corrected_section_type") or segment.section_type.value).split(".")[-1].lower()
    if segment_use == SegmentUse.TRANSITION.value and section == "build_up":
        return TransitionType.BUILD_TO_DROP.value
    if segment_use == SegmentUse.ENTRY_ONLY.value:
        return TransitionType.INTRO_TO_GROOVE.value
    if segment_use == SegmentUse.EXIT_ONLY.value:
        return TransitionType.DROP_TO_BREAKDOWN.value
    return TransitionType.NONE.value


def slope_from_segment(segment: Segment, segment_use: str) -> float:
    flow = str(segment.metadata.get("flow_direction") or "").lower()
    if flow == "up":
        return 0.72
    if flow == "down":
        return -0.72
    if segment_use == SegmentUse.TRANSITION.value:
        return 0.65
    if segment_use == SegmentUse.ENTRY_ONLY.value:
        return 0.35
    if segment_use == SegmentUse.EXIT_ONLY.value:
        return -0.65
    return 0.0


def pace_vector_v2_to_dict(vector: PaceFeatureVectorV2) -> dict[str, Any]:
    data = asdict(vector)
    for key, value in list(data.items()):
        if isinstance(value, float):
            data[key] = round(value, 4)
    return data


def _semantic_speed_degree(segment: Segment) -> float | None:
    scores = segment.metadata.get("semantic_scores")
    if not isinstance(scores, dict) or not scores:
        return None
    push = max(float(scores.get("pace_up_driving_section", 0.0)), float(scores.get("sprint_push_drop", 0.0)))
    recovery = float(scores.get("recovery_control_section", 0.0))
    static = float(scores.get("static_low_drive_loop", 0.0))
    return clamp01(0.50 + 0.30 * push - 0.22 * recovery - 0.12 * static)


def _score(value: Any, default: float) -> float:
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)


def _optional_score(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return clamp01(float(value))
    except (TypeError, ValueError):
        return None


def _raw_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
