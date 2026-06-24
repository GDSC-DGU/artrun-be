from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.analysis.multi_model_pace_feature_core import MERTScores, SegmentUse, StructureFields, clamp01
from app.domain.models import Segment


@dataclass(frozen=True)
class MERTEmbeddingAdapter:
    """MERT adapter boundary.

    The MVP does not load a heavy MERT model in the backend process. If a
    segment clip exists, this adapter projects existing signal/AI features into
    MERT-like scores so the DB/debug contract is exercised. If no clip is
    available, it returns missing scores and the core falls back to signal-only.
    """

    model_version: str = "mert-v1-deterministic-projection"

    def scores_for_segment(self, segment: Segment, structure: StructureFields) -> MERTScores:
        clip_path = segment.metadata.get("segment_clip_path")
        if not clip_path or not Path(str(clip_path)).exists():
            return MERTScores(model_version=self.model_version)

        drive = _first_float(segment, ["ai_pace_push_score", "pace_push_score", "onset_density_score"], 0.5)
        groove = _first_float(segment, ["ai_groove_score", "groove_syncopation_fit", "phrase_confidence"], 0.5)
        transition = _transition_score(segment, structure)
        stability = clamp01(
            0.45 * _first_float(segment, ["rhythmic_predictability_score"], segment.phrase_confidence)
            + 0.35 * groove
            + 0.20 * (1.0 - _first_float(segment, ["ai_chaos_penalty"], 0.1))
        )
        confidence = clamp01(
            0.45 * segment.phrase_confidence
            + 0.25 * _first_float(segment, ["beat_salience_score"], 0.5)
            + 0.30 * (1.0 - _first_float(segment, ["ai_chaos_penalty"], 0.1))
        )

        return MERTScores(
            embedding_id=f"{segment.segment_id}_mert",
            model_version=self.model_version,
            embedding_dim=4,
            drive_score=round(drive, 4),
            groove_score=round(groove, 4),
            transition_score=round(transition, 4),
            stability_score=round(stability, 4),
            confidence=round(confidence, 4),
        )


def _transition_score(segment: Segment, structure: StructureFields) -> float:
    base = _first_float(segment, ["ai_build_tension_score", "section_contrast_score", "drop_likelihood_score"], 0.45)
    if structure.segment_use == SegmentUse.TRANSITION.value:
        base = max(base, 0.72)
    if structure.flow_direction == "down":
        base = max(base, 0.62)
    return clamp01(base)


def _first_float(segment: Segment, keys: list[str], default: float) -> float:
    for key in keys:
        value: Any = segment.metadata.get(key)
        if value is None and hasattr(segment, key):
            value = getattr(segment, key)
        try:
            if value is not None:
                return clamp01(float(value))
        except (TypeError, ValueError):
            continue
    return clamp01(default)
