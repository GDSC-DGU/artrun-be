from __future__ import annotations

from dataclasses import replace
from typing import Any, Iterable

from app.analysis.allinone_adapter import AllInOneStructureAdapter
from app.analysis.mert_embedding_adapter import MERTEmbeddingAdapter
from app.analysis.multi_model_pace_feature_core import (
    MULTI_MODEL_METADATA_KEYS,
    MERTScores,
    RhythmSignalFeatures,
    SegmentAnalysis,
    SemanticScores,
    StructureFields,
    TimbreEnergyFeatures,
    analysis_to_dict,
    clamp01,
    fuse_pace_feature_vector,
    pace_vector_to_dict,
)
from app.analysis.muq_mulan_semantic_adapter import MuQMulanSemanticAdapter
from app.domain.models import Segment


def annotate_segments_with_multi_model_pace_features(
    segments: Iterable[Segment],
    *,
    allinone: AllInOneStructureAdapter | None = None,
    mert: MERTEmbeddingAdapter | None = None,
    semantic: MuQMulanSemanticAdapter | None = None,
) -> list[Segment]:
    allinone = allinone or AllInOneStructureAdapter()
    mert = mert or MERTEmbeddingAdapter()
    semantic = semantic or MuQMulanSemanticAdapter()
    annotated: list[Segment] = []
    for segment in segments:
        analysis = build_segment_analysis_from_segment(
            segment,
            structure=allinone.structure_for_segment(segment),
            mert_scores=None,
            semantic_scores=None,
            mert_adapter=mert,
            semantic_adapter=semantic,
        )
        metadata = {**segment.metadata, **multi_model_metadata_from_analysis(analysis)}
        annotated.append(replace(segment, metadata=metadata))
    return annotated


def build_segment_analysis_from_segment(
    segment: Segment,
    *,
    structure: StructureFields | None = None,
    mert_scores: MERTScores | None = None,
    semantic_scores: SemanticScores | None = None,
    mert_adapter: MERTEmbeddingAdapter | None = None,
    semantic_adapter: MuQMulanSemanticAdapter | None = None,
) -> SegmentAnalysis:
    structure = structure or structure_from_metadata(segment)
    rhythm = rhythm_from_segment(segment)
    timbre = timbre_from_segment(segment)
    if mert_scores is None:
        mert_scores = mert_from_metadata(segment)
    if not _mert_complete(mert_scores) and mert_adapter is not None:
        mert_scores = mert_adapter.scores_for_segment(segment, structure)
    if semantic_scores is None:
        semantic_scores = semantic_from_metadata(segment)
    if not semantic_scores.enabled and semantic_adapter is not None:
        semantic_scores = semantic_adapter.scores_for_segment(segment, structure)
    pace_vector = fuse_pace_feature_vector(
        structure=structure,
        rhythm=rhythm,
        timbre=timbre,
        mert=mert_scores,
        semantic=semantic_scores,
    )
    return SegmentAnalysis(structure, rhythm, timbre, mert_scores, semantic_scores, pace_vector)


def multi_model_metadata_from_analysis(analysis: SegmentAnalysis) -> dict[str, Any]:
    structure = analysis.structure
    rhythm = analysis.rhythm
    timbre = analysis.timbre
    mert = analysis.mert
    semantic = analysis.semantic
    vector = pace_vector_to_dict(analysis.pace_vector)
    return {
        "segment_use": structure.segment_use,
        "transition_type": structure.transition_type,
        "flow_direction": structure.flow_direction,
        "target_after_transition": structure.target_after_transition,
        "is_contiguous_original_audio": structure.is_contiguous_original_audio,
        "beat_confidence": round(rhythm.beat_confidence, 4),
        "downbeat_confidence": round(rhythm.downbeat_confidence, 4),
        "effective_pulse_bpm": round(rhythm.effective_pulse_bpm, 4),
        "pulse_relation": rhythm.pulse_relation,
        "rhythm_predictability_score": round(rhythm.rhythm_predictability_score, 4),
        "groove_stability_score": round(rhythm.groove_stability_score, 4),
        "tempogram_strength_score": round(rhythm.tempogram_strength_score, 4),
        "bass_energy_score": round(timbre.bass_energy_score, 4),
        "bass_modulation_score": round(timbre.bass_modulation_score, 4),
        "low_end_stability_score": round(timbre.low_end_stability_score, 4),
        "loudness_change_score": round(timbre.loudness_change_score, 4),
        "spectral_brightness_score": round(timbre.spectral_brightness_score, 4),
        "brightness_change_score": round(timbre.brightness_change_score, 4),
        "static_loop_penalty": round(timbre.static_loop_penalty, 4),
        "chaos_penalty": round(timbre.chaos_penalty, 4),
        "mert_embedding_id": mert.embedding_id,
        "mert_model_version": mert.model_version,
        "mert_embedding_dim": mert.embedding_dim,
        "mert_drive_score": _round_optional(mert.drive_score),
        "mert_groove_score": _round_optional(mert.groove_score),
        "mert_transition_score": _round_optional(mert.transition_score),
        "mert_stability_score": _round_optional(mert.stability_score),
        "mert_confidence": _round_optional(mert.confidence),
        "semantic_scores": dict(semantic.scores),
        "semantic_confidence": _round_optional(semantic.confidence),
        "pace_feature_vector": vector,
        "fusion_weights": dict(analysis.pace_vector.fusion_weights),
        "multi_model_analysis": analysis_to_dict(analysis),
    }


def structure_from_metadata(segment: Segment) -> StructureFields:
    return AllInOneStructureAdapter().structure_for_segment(segment)


def rhythm_from_segment(segment: Segment) -> RhythmSignalFeatures:
    bpm = max(0.0, float(segment.bpm))
    effective, relation = effective_pulse_from_bpm(bpm)
    return RhythmSignalFeatures(
        bpm=bpm,
        effective_pulse_bpm=_raw_float_meta(segment, "effective_pulse_bpm", effective),
        pulse_relation=str(segment.metadata.get("pulse_relation") or relation),
        beat_confidence=_float_meta(segment, "beat_confidence", max(0.45, segment.phrase_confidence)),
        downbeat_confidence=_float_meta(segment, "downbeat_confidence", max(0.40, segment.phrase_confidence - 0.05)),
        beat_salience_score=_float_meta(segment, "beat_salience_score", segment.onset_density_score),
        onset_density_score=clamp01(segment.onset_density_score),
        rhythm_predictability_score=_float_meta(
            segment,
            "rhythm_predictability_score",
            _float_meta(segment, "rhythmic_predictability_score", segment.phrase_confidence),
        ),
        groove_stability_score=_float_meta(
            segment,
            "groove_stability_score",
            _float_meta(segment, "groove_syncopation_fit", _float_meta(segment, "ai_groove_score", segment.phrase_confidence)),
        ),
        tempogram_strength_score=_float_meta(
            segment,
            "tempogram_strength_score",
            _float_meta(segment, "rhythmic_activity_score", segment.onset_density_score),
        ),
    )


def timbre_from_segment(segment: Segment) -> TimbreEnergyFeatures:
    loudness_density = _float_meta(
        segment,
        "loudness_density_score",
        clamp01(0.55 * segment.volume_score + 0.45 * segment.sound_density_score),
    )
    bass_drive = _float_meta(segment, "bass_drive_score", _float_meta(segment, "ai_bass_drive_score", 0.35))
    static_low = _float_meta(segment, "static_low_end_penalty", _float_meta(segment, "ai_static_low_end_penalty", 0.0))
    return TimbreEnergyFeatures(
        bass_energy_score=_float_meta(segment, "bass_energy_score", bass_drive),
        bass_modulation_score=_float_meta(segment, "bass_modulation_score", bass_drive),
        low_end_stability_score=_float_meta(segment, "low_end_stability_score", clamp01(1.0 - static_low)),
        loudness_density_score=loudness_density,
        loudness_change_score=_float_meta(segment, "loudness_change_score", _float_meta(segment, "section_contrast_score", 0.2)),
        spectral_brightness_score=_float_meta(segment, "spectral_brightness_score", segment.brightness_score),
        brightness_change_score=_float_meta(segment, "brightness_change_score", _float_meta(segment, "section_contrast_score", 0.2)),
        static_loop_penalty=_float_meta(segment, "static_loop_penalty", _float_meta(segment, "ai_static_loop_penalty", static_low * 0.7)),
        static_low_end_penalty=static_low,
        chaos_penalty=_float_meta(segment, "chaos_penalty", _float_meta(segment, "ai_chaos_penalty", 0.08)),
    )


def mert_from_metadata(segment: Segment) -> MERTScores:
    return MERTScores(
        embedding_id=segment.metadata.get("mert_embedding_id"),
        model_version=str(segment.metadata.get("mert_model_version") or "mert-v1"),
        embedding_dim=_int_optional(segment.metadata.get("mert_embedding_dim")),
        drive_score=_optional_float(segment.metadata.get("mert_drive_score")),
        groove_score=_optional_float(segment.metadata.get("mert_groove_score")),
        transition_score=_optional_float(segment.metadata.get("mert_transition_score")),
        stability_score=_optional_float(segment.metadata.get("mert_stability_score")),
        confidence=_optional_float(segment.metadata.get("mert_confidence")),
    )


def semantic_from_metadata(segment: Segment) -> SemanticScores:
    scores = segment.metadata.get("semantic_scores")
    if not isinstance(scores, dict) or not scores:
        return SemanticScores(enabled=False)
    return SemanticScores(
        enabled=True,
        scores={str(key): clamp01(value) for key, value in scores.items()},
        confidence=_optional_float(segment.metadata.get("semantic_confidence")) or 0.7,
    )


def effective_pulse_from_bpm(bpm: float) -> tuple[float, str]:
    if 78.0 <= bpm <= 94.0:
        return bpm * 2.0, "half_time"
    if bpm >= 155.0:
        return bpm, "direct"
    if 95.0 <= bpm <= 154.0:
        return bpm, "direct"
    if bpm > 0:
        return bpm * 2.0 if bpm < 95.0 else bpm, "workout_pulse"
    return 0.0, "unknown"


def _mert_complete(mert: MERTScores) -> bool:
    return all(
        value is not None
        for value in (mert.drive_score, mert.groove_score, mert.transition_score, mert.stability_score)
    )


def _float_meta(segment: Segment, key: str, default: float) -> float:
    value = segment.metadata.get(key)
    if value is None and hasattr(segment, key):
        value = getattr(segment, key)
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)


def _raw_float_meta(segment: Segment, key: str, default: float) -> float:
    value = segment.metadata.get(key)
    if value is None and hasattr(segment, key):
        value = getattr(segment, key)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return clamp01(float(value))
    except (TypeError, ValueError):
        return None


def _int_optional(value: Any) -> int | None:
    try:
        if value is None:
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _round_optional(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)
