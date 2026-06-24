from __future__ import annotations

import os
from dataclasses import dataclass

from app.analysis.multi_model_pace_feature_core import SemanticScores, StructureFields, clamp01
from app.domain.models import Segment


SEMANTIC_PROMPTS = (
    "steady_running_groove",
    "pace_up_driving_section",
    "sprint_push_drop",
    "recovery_control_section",
    "build_up_to_drop_transition",
    "chaotic_unstable_section",
    "static_low_drive_loop",
)


@dataclass(frozen=True)
class MuQMulanSemanticAdapter:
    """Optional MuQ-MuLan semantic adapter boundary.

    Set ENABLE_MUQ_MULAN=true to enable deterministic semantic projection in
    this MVP. A real adapter can replace `scores_for_segment` with text/music
    embedding similarity while preserving the schema.
    """

    enabled: bool | None = None

    def scores_for_segment(self, segment: Segment, structure: StructureFields) -> SemanticScores:
        enabled = self.enabled
        if enabled is None:
            enabled = os.getenv("ENABLE_MUQ_MULAN", "").lower() in {"1", "true", "yes", "on"}
        if not enabled:
            return SemanticScores(enabled=False)

        role = str(segment.metadata.get("ai_segment_role", ""))
        section = str(segment.metadata.get("ai_corrected_section_type") or segment.section_type.value)
        push = _float(segment.metadata.get("ai_pace_push_score"), 0.5)
        flow = _float(segment.metadata.get("ai_flow_momentum_score"), push)
        groove = _float(segment.metadata.get("ai_groove_score"), 0.5)
        static = _float(segment.metadata.get("ai_static_low_end_penalty"), 0.1)
        chaos = _float(segment.metadata.get("ai_chaos_penalty"), 0.1)
        transition = 0.8 if structure.segment_use == "TRANSITION" else _float(segment.metadata.get("section_contrast_score"), 0.35)

        scores = {
            "steady_running_groove": clamp01(0.55 * groove + 0.35 * flow + 0.10 * (1.0 - static)),
            "pace_up_driving_section": clamp01(0.55 * push + 0.30 * flow + 0.15 * groove),
            "sprint_push_drop": clamp01(0.62 * push + 0.20 * (1.0 if section == "drop" else 0.0) + 0.18 * flow),
            "recovery_control_section": clamp01(0.55 * (1.0 - push) + 0.25 * static + 0.20 * (1.0 if "recovery" in role else 0.0)),
            "build_up_to_drop_transition": clamp01(transition),
            "chaotic_unstable_section": clamp01(chaos),
            "static_low_drive_loop": clamp01(static),
        }
        return SemanticScores(enabled=True, scores=scores, confidence=round(0.72 * (1.0 - chaos) + 0.18, 4))


def _float(value: object, default: float) -> float:
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)
