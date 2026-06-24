from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.analysis.multi_model_pace_feature_core import SegmentUse, StructureFields, TransitionType, clamp01
from app.domain.models import Segment


@dataclass(frozen=True)
class AllInOneStructureAdapter:
    """Lightweight structure adapter.

    Production can replace this with All-In-One beat/downbeat/section output.
    For the MVP it maps existing phrase-aligned segment metadata to the v1
    structure schema without changing the original audio boundaries.
    """

    def structure_for_segment(self, segment: Segment) -> StructureFields:
        section = _section(segment)
        entry_quality = _float(segment.metadata.get("entry_quality"), segment.phrase_confidence)
        exit_quality = _float(segment.metadata.get("exit_quality"), segment.phrase_confidence)
        phrase_confidence = clamp01(segment.phrase_confidence)
        duration_bars = max(1, int(segment.end_bar - segment.start_bar + 1))
        contiguous = bool(segment.metadata.get("is_contiguous_original_audio", True))

        segment_use, transition_type, flow_direction, target_after = classify_segment_use(
            section=section,
            entry_quality=entry_quality,
            exit_quality=exit_quality,
            phrase_confidence=phrase_confidence,
            contiguous=contiguous,
        )

        return StructureFields(
            segment_id=segment.segment_id,
            track_id=segment.track_id,
            start_sec=segment.start_sec,
            end_sec=segment.end_sec,
            start_bar=segment.start_bar,
            end_bar=segment.end_bar,
            duration_bars=duration_bars,
            segment_use=segment_use,
            transition_type=transition_type,
            flow_direction=flow_direction,
            target_after_transition=target_after,
            entry_quality=round(entry_quality, 4),
            exit_quality=round(exit_quality, 4),
            phrase_confidence=round(phrase_confidence, 4),
            is_contiguous_original_audio=contiguous,
        )


def classify_segment_use(
    *,
    section: str,
    entry_quality: float,
    exit_quality: float,
    phrase_confidence: float,
    contiguous: bool,
) -> tuple[str, str, str, str | None]:
    if not contiguous:
        return SegmentUse.REJECT.value, TransitionType.MIXED_UNKNOWN.value, "flat", None
    if phrase_confidence < 0.45 or entry_quality < 0.35 or exit_quality < 0.35:
        return SegmentUse.REJECT.value, TransitionType.MIXED_UNKNOWN.value, "flat", None
    if section == "build_up":
        return SegmentUse.TRANSITION.value, TransitionType.BUILD_TO_DROP.value, "up", "drop"
    if section == "intro":
        return SegmentUse.ENTRY_ONLY.value, TransitionType.INTRO_TO_GROOVE.value, "up", "groove"
    if section in {"breakdown", "outro"}:
        return SegmentUse.EXIT_ONLY.value, TransitionType.DROP_TO_BREAKDOWN.value, "down", "recovery"
    return SegmentUse.STABLE.value, TransitionType.NONE.value, "flat", None


def _section(segment: Segment) -> str:
    raw: Any = (
        segment.metadata.get("ai_corrected_section_type")
        or segment.metadata.get("corrected_section_type")
        or segment.metadata.get("section_type_signal")
        or segment.section_type.value
    )
    return str(raw).split(".")[-1].lower()


def _float(value: Any, default: float) -> float:
    try:
        return clamp01(float(value))
    except (TypeError, ValueError):
        return clamp01(default)
