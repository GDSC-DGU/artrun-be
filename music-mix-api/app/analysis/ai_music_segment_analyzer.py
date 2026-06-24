from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from typing import Any, Mapping, Protocol

from app.domain.models import SectionType, Segment

VALID_INTENTIONS = {"recovery_or_control", "steady", "pace_up", "sprint_push"}
VALID_ROLES = {
    "recovery",
    "steady",
    "pace_up",
    "sprint_push",
    "steady_to_pace_up_bridge",
    "slow_heavy_power",
    "fast_light_control",
    "low_drive_or_static",
    "chaotic_not_runnable",
}
VALID_SECTION_TYPES = {"intro", "groove", "build_up", "drop", "breakdown", "outro", "bridge", "low_drive"}
AI_SEGMENT_ANALYSIS_KEYS = [
    "ai_perceived_speed_score",
    "ai_flow_momentum_score",
    "ai_pace_push_score",
    "ai_cadence_lock_score",
    "ai_groove_score",
    "ai_bass_drive_score",
    "ai_build_tension_score",
    "ai_static_loop_penalty",
    "ai_static_low_end_penalty",
    "ai_chaos_penalty",
    "ai_corrected_section_type",
    "ai_segment_role",
    "recommended_for",
    "avoid_for",
    "ai_runnable_confidence",
    "ai_notes",
    "ai_model",
    "section_type_signal",
    "section_type_ai",
]


@dataclass(frozen=True)
class SegmentClipContext:
    segment_id: str
    track_id: str
    clip_path: str
    start_sec: float
    end_sec: float
    start_bar: int | None = None
    end_bar: int | None = None
    bpm: float | None = None
    section_type: str | None = None
    loudness_density_score: float | None = None
    onset_density_score: float | None = None
    entry_quality: float | None = None
    exit_quality: float | None = None
    extra_signal_features: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AISegmentAnalysis:
    segment_id: str
    ai_perceived_speed_score: float
    ai_flow_momentum_score: float
    ai_pace_push_score: float
    ai_cadence_lock_score: float
    ai_groove_score: float
    ai_bass_drive_score: float
    ai_build_tension_score: float
    ai_static_loop_penalty: float
    ai_static_low_end_penalty: float
    ai_chaos_penalty: float
    ai_corrected_section_type: str
    ai_segment_role: str
    recommended_for: list[str]
    avoid_for: list[str]
    ai_runnable_confidence: float
    ai_notes: str = ""
    ai_model: str | None = None


class AISegmentAnalyzerClient(Protocol):
    def analyze_segment(self, context: SegmentClipContext, prompt: str) -> Mapping[str, Any]:
        ...


def clamp01(value: float | None) -> float:
    if value is None:
        return 0.0
    return max(0.0, min(1.0, float(value)))


def maybe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def score(raw: Mapping[str, Any], key: str, default: float = 0.0) -> float:
    return clamp01(maybe_float(raw.get(key), default))


def normalize_intention_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        item_str = str(item)
        if item_str in VALID_INTENTIONS and item_str not in out:
            out.append(item_str)
    return out


def role_defaults(role: str) -> tuple[list[str], list[str]]:
    return {
        "recovery": (["recovery_or_control"], ["pace_up", "sprint_push"]),
        "steady": (["steady"], []),
        "pace_up": (["pace_up"], ["recovery_or_control"]),
        "sprint_push": (["sprint_push"], ["recovery_or_control", "steady"]),
        "steady_to_pace_up_bridge": (["steady", "pace_up"], ["sprint_push"]),
        "slow_heavy_power": (["pace_up"], ["sprint_push"]),
        "fast_light_control": (["steady", "pace_up"], ["sprint_push"]),
        "low_drive_or_static": (["recovery_or_control"], ["pace_up", "sprint_push"]),
        "chaotic_not_runnable": ([], ["steady", "pace_up", "sprint_push"]),
    }.get(role, ([], []))


def build_ai_segment_prompt(context: SegmentClipContext) -> str:
    return f"""
You are analyzing an EDM music segment for a mobile running pace-assist app.

Judge running feel, not general music quality.
Loudness is not running push. Low-end amount is not bass drive. Drop label is not automatically sprint.

Return only valid JSON with scores from 0.0 to 1.0.

Segment context:
- segment_id: {context.segment_id}
- track_id: {context.track_id}
- bpm: {context.bpm}
- signal_section_type: {context.section_type}
- start_bar: {context.start_bar}
- end_bar: {context.end_bar}
- loudness_density_score: {context.loudness_density_score}
- onset_density_score: {context.onset_density_score}
- entry_quality: {context.entry_quality}
- exit_quality: {context.exit_quality}
""".strip()


def normalize_ai_segment_analysis(raw: Mapping[str, Any], *, fallback_segment_id: str) -> AISegmentAnalysis:
    role = str(raw.get("ai_segment_role") or infer_role_from_scores(raw))
    if role not in VALID_ROLES:
        role = infer_role_from_scores(raw)
    section = str(raw.get("ai_corrected_section_type") or "groove")
    if section not in VALID_SECTION_TYPES:
        section = "groove"

    recommended_for = normalize_intention_list(raw.get("recommended_for"))
    avoid_for = normalize_intention_list(raw.get("avoid_for"))
    default_rec, default_avoid = role_defaults(role)
    recommended_for = recommended_for or default_rec
    avoid_for = avoid_for or default_avoid

    return AISegmentAnalysis(
        segment_id=str(raw.get("segment_id") or fallback_segment_id),
        ai_perceived_speed_score=score(raw, "ai_perceived_speed_score"),
        ai_flow_momentum_score=score(raw, "ai_flow_momentum_score"),
        ai_pace_push_score=score(raw, "ai_pace_push_score"),
        ai_cadence_lock_score=score(raw, "ai_cadence_lock_score"),
        ai_groove_score=score(raw, "ai_groove_score"),
        ai_bass_drive_score=score(raw, "ai_bass_drive_score"),
        ai_build_tension_score=score(raw, "ai_build_tension_score"),
        ai_static_loop_penalty=score(raw, "ai_static_loop_penalty"),
        ai_static_low_end_penalty=score(raw, "ai_static_low_end_penalty"),
        ai_chaos_penalty=score(raw, "ai_chaos_penalty"),
        ai_corrected_section_type=section,
        ai_segment_role=role,
        recommended_for=recommended_for,
        avoid_for=avoid_for,
        ai_runnable_confidence=score(raw, "ai_runnable_confidence", 0.5),
        ai_notes=str(raw.get("ai_notes") or ""),
        ai_model=str(raw.get("ai_model")) if raw.get("ai_model") else None,
    )


def infer_role_from_scores(raw: Mapping[str, Any]) -> str:
    pace = score(raw, "ai_pace_push_score")
    flow = score(raw, "ai_flow_momentum_score")
    static = max(score(raw, "ai_static_loop_penalty"), score(raw, "ai_static_low_end_penalty"))
    chaos = score(raw, "ai_chaos_penalty")
    cadence = score(raw, "ai_cadence_lock_score")

    if chaos >= 0.65:
        return "chaotic_not_runnable"
    if static >= 0.58 and pace < 0.52:
        return "low_drive_or_static"
    if pace >= 0.78 and cadence >= 0.70:
        return "sprint_push"
    if pace >= 0.64 and flow >= 0.55:
        return "pace_up"
    if flow >= 0.58 and pace >= 0.48:
        return "steady_to_pace_up_bridge"
    if pace < 0.35:
        return "recovery"
    return "steady"


def context_from_segment(segment: Segment) -> SegmentClipContext:
    return SegmentClipContext(
        segment_id=segment.segment_id,
        track_id=segment.track_id,
        clip_path=str(segment.metadata.get("segment_clip_path", "")),
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        start_bar=segment.start_bar,
        end_bar=segment.end_bar,
        bpm=segment.bpm,
        section_type=segment.section_type.value,
        loudness_density_score=maybe_float(segment.metadata.get("loudness_density_score"), segment.energy_score),
        onset_density_score=segment.onset_density_score,
        entry_quality=maybe_float(segment.metadata.get("entry_quality"), segment.phrase_confidence),
        exit_quality=maybe_float(segment.metadata.get("exit_quality"), segment.phrase_confidence),
        extra_signal_features=dict(segment.metadata),
    )


def heuristic_ai_analysis_for_segment(segment: Segment) -> AISegmentAnalysis:
    meta = segment.metadata
    beat = maybe_float(meta.get("beat_salience_score"), segment.phrase_confidence)
    activity = maybe_float(meta.get("rhythmic_activity_score"), segment.onset_density_score)
    predictability = maybe_float(meta.get("rhythmic_predictability_score"), segment.phrase_confidence)
    groove = maybe_float(meta.get("groove_syncopation_fit"), maybe_float(meta.get("syncopation_score"), 0.5))
    bass = maybe_float(meta.get("bass_drive_score"), 0.35)
    static_low_raw = maybe_float(meta.get("static_low_end_penalty"), 0.0)
    drop_likelihood = maybe_float(meta.get("drop_likelihood_score"), 0.0)
    pace_push = maybe_float(meta.get("pace_push_score"), 0.45)
    loudness = maybe_float(meta.get("loudness_density_score"), segment.energy_score)
    section = str(meta.get("corrected_section_type") or segment.section_type.value)

    bpm = segment.bpm
    half_time_cadence_fit = 0.0
    if bpm > 0:
        half_time_cadence_fit = clamp01(1.0 - abs((bpm * 2.0) - 172.0) / 28.0)
    workout_pulse_fit = 1.0 if 120.0 <= bpm <= 152.0 else clamp01(1.0 - min(abs(bpm - 120.0), abs(bpm - 152.0)) / 30.0)

    perceived_speed = clamp01(0.45 * workout_pulse_fit + 0.35 * activity + 0.20 * beat)
    cadence_lock = clamp01(max(half_time_cadence_fit, 0.45 * predictability + 0.35 * beat + 0.20 * workout_pulse_fit))
    static_low = clamp01(static_low_raw * (1.0 - 0.35 * groove - 0.20 * beat))
    flow = clamp01(0.35 * pace_push + 0.25 * groove + 0.20 * predictability + 0.20 * activity - 0.18 * static_low)
    ai_pace_push = clamp01(0.42 * pace_push + 0.24 * cadence_lock + 0.22 * flow + 0.12 * bass - 0.28 * static_low)
    ai_groove = clamp01(0.45 * groove + 0.25 * predictability + 0.20 * activity + 0.10 * beat)
    ai_bass = clamp01(0.75 * bass + 0.25 * max(0.0, bass - static_low))
    build_tension = clamp01(0.55 * drop_likelihood + 0.25 * flow + 0.20 * activity)
    static_loop = clamp01(0.65 * static_low + 0.20 * (1.0 - flow) + 0.15 * (1.0 - beat))
    chaos = clamp01(0.45 * (1.0 - predictability) + 0.30 * max(0.0, activity - groove) + 0.25 * max(0.0, loudness - beat))

    raw = {
        "segment_id": segment.segment_id,
        "ai_perceived_speed_score": perceived_speed,
        "ai_flow_momentum_score": flow,
        "ai_pace_push_score": ai_pace_push,
        "ai_cadence_lock_score": cadence_lock,
        "ai_groove_score": ai_groove,
        "ai_bass_drive_score": ai_bass,
        "ai_build_tension_score": build_tension,
        "ai_static_loop_penalty": static_loop,
        "ai_static_low_end_penalty": static_low,
        "ai_chaos_penalty": chaos,
        "ai_corrected_section_type": section,
        "ai_runnable_confidence": clamp01(0.55 + 0.25 * predictability + 0.20 * segment.phrase_confidence - 0.20 * chaos),
        "ai_model": "heuristic-running-feel-v0",
    }
    role = infer_role_from_scores(raw)

    # Half-time cadence-lock segments are direct sprint candidates even if raw
    # BPM looks slow; fast 140s tracks are bridge/control candidates, not sprint
    # replacements.
    if half_time_cadence_fit >= 0.78 and ai_pace_push >= 0.42 and static_low < 0.55:
        role = "sprint_push"
    elif section in {"intro", "outro"} and role in {"steady_to_pace_up_bridge", "pace_up", "sprint_push"}:
        role = "steady"
    elif 140.0 <= bpm <= 152.0 and role in {"sprint_push", "pace_up"}:
        role = "steady_to_pace_up_bridge" if ai_pace_push < 0.72 else "pace_up"
    elif static_low >= 0.50 and beat < 0.25:
        role = "low_drive_or_static"

    recommended_for, avoid_for = role_defaults(role)
    notes = (
        f"role={role}; pulse={bpm:.1f}; push={ai_pace_push:.2f}; "
        f"flow={flow:.2f}; static_low={static_low:.2f}"
    )
    raw.update(
        {
            "ai_segment_role": role,
            "recommended_for": recommended_for,
            "avoid_for": avoid_for,
            "ai_notes": notes,
        }
    )
    return normalize_ai_segment_analysis(raw, fallback_segment_id=segment.segment_id)


def merge_ai_analysis_into_segment(segment: Segment, ai: AISegmentAnalysis) -> Segment:
    payload = asdict(ai)
    payload["section_type_signal"] = segment.section_type.value
    payload["section_type_ai"] = ai.ai_corrected_section_type
    if "loudness_density_score" not in segment.metadata:
        payload["loudness_density_score"] = segment.energy_score
    metadata = {**segment.metadata, **payload}
    try:
        section = SectionType(ai.ai_corrected_section_type)
    except ValueError:
        section = segment.section_type
    return replace(
        segment,
        section_type=section,
        final_section_label=ai.ai_corrected_section_type,
        metadata=metadata,
    )


def annotate_segments_with_ai_running_feel(
    segments: list[Segment],
    client: AISegmentAnalyzerClient | None = None,
) -> list[Segment]:
    annotated: list[Segment] = []
    for segment in segments:
        if client is None:
            ai = heuristic_ai_analysis_for_segment(segment)
        else:
            context = context_from_segment(segment)
            raw = client.analyze_segment(context, build_ai_segment_prompt(context))
            ai = normalize_ai_segment_analysis(raw, fallback_segment_id=segment.segment_id)
        annotated.append(merge_ai_analysis_into_segment(segment, ai))
    return annotated


def ai_role_match_score(segment: Segment | Mapping[str, Any], running_intention: str) -> float:
    if isinstance(segment, Mapping):
        recommended_for = set(segment.get("recommended_for") or [])
        avoid_for = set(segment.get("avoid_for") or [])
        role = str(segment.get("ai_segment_role") or "")
    else:
        recommended_for = set(segment.metadata.get("recommended_for") or [])
        avoid_for = set(segment.metadata.get("avoid_for") or [])
        role = str(segment.metadata.get("ai_segment_role") or "")

    if running_intention in avoid_for:
        return 0.0
    if running_intention in recommended_for:
        return 1.0
    if running_intention == "pace_up" and role in {"steady_to_pace_up_bridge", "fast_light_control"}:
        return 0.78
    if running_intention == "steady" and role in {"steady_to_pace_up_bridge", "fast_light_control"}:
        return 0.82
    if running_intention == "recovery_or_control" and role in {"recovery", "low_drive_or_static"}:
        return 0.75
    return 0.45
