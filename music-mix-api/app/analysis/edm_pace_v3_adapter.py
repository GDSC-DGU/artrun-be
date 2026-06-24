from __future__ import annotations

from typing import Any

from app.analysis.edm_pace_v3_core import (
    BlockProfile,
    DriveProfile,
    PaceAssistV34Profile,
    PulseProfile,
    RiskProfile,
    SegmentPaceProfile,
    SegmentRecord,
    SegmentUse,
    TransitionProfile,
    V3Config,
)
from app.domain.models import Segment


def segment_to_v3_record(segment: Segment, config: V3Config = V3Config()) -> SegmentRecord:
    music_degree = _score(segment.metadata.get("music_speed_degree"), _score(segment.metadata.get("ai_pace_push_score"), 0.5))
    slope = _raw_float(segment.metadata.get("transition_slope"), 0.0)
    segment_use = _segment_use(segment)
    section = str(
        segment.metadata.get("ai_corrected_section_type")
        or segment.metadata.get("corrected_section_type")
        or segment.metadata.get("section_type_signal")
        or segment.section_type.value
    ).split(".")[-1].lower()

    pulse_continuity = _score(
        segment.metadata.get("pulse_continuity_score"),
        0.45 * _score(segment.metadata.get("rhythm_predictability_score"), _score(segment.metadata.get("rhythmic_predictability_score"), segment.phrase_confidence))
        + 0.35 * _score(segment.metadata.get("beat_salience_score"), segment.onset_density_score)
        + 0.20 * (1.0 - _score(segment.metadata.get("pulse_drop_score"), 0.0)),
    )
    cadence_lock = _score(
        _nested(segment, "pace_feature_vector_v2", "cadence_lock_support"),
        _score(segment.metadata.get("ai_cadence_lock_score"), segment.phrase_confidence),
    )
    beat_salience = _score(segment.metadata.get("beat_salience_score"), max(segment.onset_density_score, segment.phrase_confidence * 0.75))
    drive_preservation = _score(segment.metadata.get("drive_preservation_score"), _score(_nested(segment, "pace_feature_vector_v2", "drive_preservation_score"), 0.55))
    connector_drive = _score(segment.metadata.get("connector_drive_score"), _score(_nested(segment, "pace_feature_vector_v2", "connector_drive_score"), drive_preservation))
    intro_like = _score(segment.metadata.get("intro_like_score"), 1.0 if segment_use == SegmentUse.ENTRY_ONLY.value else 0.0)
    pulse_drop = _score(segment.metadata.get("pulse_drop_score"), 0.0)
    ai_semantic = segment.metadata.get("AI_semantic_scores")
    if not isinstance(ai_semantic, dict):
        ai_semantic = {}
    primary_asc = _raw_float(segment.metadata.get("primary_ASC_spm"), segment.bpm)
    asc_strength = _score(segment.metadata.get("ASC_strength"), max(beat_salience, segment.phrase_confidence * 0.75))
    asc_stability = _score(segment.metadata.get("ASC_stability"), max(pulse_continuity, segment.phrase_confidence * 0.78))
    pulse_clarity = _score(segment.metadata.get("pulse_clarity"), beat_salience)
    rhythm_predictability = _score(segment.metadata.get("rhythm_predictability"), _score(segment.metadata.get("rhythm_predictability_score"), pulse_continuity))
    pulse_dropout_risk = _score(segment.metadata.get("pulse_dropout_risk"), pulse_drop)
    half_time_shift_risk = _score(segment.metadata.get("half_time_shift_risk"), _score(segment.metadata.get("breakdown_like_score"), 0.0))
    fake_groove_risk = _score(segment.metadata.get("fake_groove_risk"), _score(segment.metadata.get("static_risk"), 0.0))
    pace_assist_score = _score(
        segment.metadata.get("pace_assist_score"),
        0.25 * asc_strength
        + 0.20 * asc_stability
        + 0.15 * pulse_clarity
        + 0.15 * rhythm_predictability
        + 0.15 * _score(segment.metadata.get("ai_pace_up_cue"), _score(segment.metadata.get("ai_pace_push_score"), 0.5))
        + 0.10 * (1.0 - max(pulse_dropout_risk, half_time_shift_risk, fake_groove_risk)),
    )

    return SegmentRecord(
        segment_id=segment.segment_id,
        track_id=segment.track_id,
        track_title=segment.track_id,
        start_sec=segment.start_sec,
        end_sec=segment.end_sec,
        start_bar=segment.start_bar,
        end_bar=segment.end_bar,
        segment_use=segment_use,
        section_label=section,
        pace=SegmentPaceProfile(
            music_speed_degree=music_degree,
            start_degree=_score(segment.metadata.get("start_degree"), max(0.0, music_degree - slope * 0.08)),
            mid_degree=_score(segment.metadata.get("mid_degree"), music_degree),
            end_degree=_score(segment.metadata.get("end_degree"), max(0.0, min(1.0, music_degree + slope * 0.08))),
            degree_slope=slope,
            degree_stability=_score(segment.metadata.get("degree_stability"), 1.0 - abs(slope) * 0.25),
            curve_shape=str(segment.metadata.get("curve_shape") or "flat" if abs(slope) < 0.2 else "ramp"),
        ),
        pulse=PulseProfile(
            effective_pulse_bpm=_raw_float(segment.metadata.get("effective_pulse_bpm"), segment.bpm),
            kick_presence_score=_score(segment.metadata.get("kick_presence_score"), beat_salience),
            pulse_continuity_score=pulse_continuity,
            beat_salience_score=beat_salience,
            beat_salience_continuity=_score(segment.metadata.get("beat_salience_continuity"), pulse_continuity),
            cadence_lock_support=cadence_lock,
            cadence_lock_continuity=_score(segment.metadata.get("cadence_lock_continuity"), min(cadence_lock, pulse_continuity)),
            rhythm_predictability_score=_score(segment.metadata.get("rhythm_predictability_score"), _score(segment.metadata.get("rhythmic_predictability_score"), segment.phrase_confidence)),
        ),
        drive=DriveProfile(
            entry_drive_score=_score(segment.metadata.get("entry_drive_score"), drive_preservation),
            mid_drive_score=_score(segment.metadata.get("mid_drive_score"), _score(segment.metadata.get("ai_pace_push_score"), drive_preservation)),
            exit_drive_score=_score(segment.metadata.get("exit_drive_score"), drive_preservation),
            drive_preservation_score=drive_preservation,
            flow_momentum_score=_score(segment.metadata.get("flow_momentum_score"), _score(segment.metadata.get("ai_flow_momentum_score"), _score(_nested(segment, "pace_feature_vector_v2", "flow_momentum_score"), 0.5))),
            pace_push_score=_score(segment.metadata.get("pace_push_score"), _score(segment.metadata.get("ai_pace_push_score"), _score(_nested(segment, "pace_feature_vector_v2", "pace_push_score"), 0.5))),
            bass_modulation_score=_score(segment.metadata.get("bass_modulation_score"), _score(segment.metadata.get("ai_bass_drive_score"), 0.35)),
        ),
        transition=TransitionProfile(
            transition_slope=slope,
            transition_target_degree=_score(segment.metadata.get("transition_target_degree"), max(0.0, min(1.0, music_degree + slope * 0.12))),
            transition_arrival_confidence=_score(segment.metadata.get("transition_arrival_confidence"), _score(_nested(segment, "pace_feature_vector_v2", "target_arrival_score"), segment.phrase_confidence)),
            runtime_connector_allowed=segment_use in {SegmentUse.DRIVE_CONNECTOR.value, SegmentUse.EXIT_CONNECTOR.value},
            drive_connector_score=connector_drive,
            transition_type=str(segment.metadata.get("transition_type") or "NONE"),
        ),
        risk=RiskProfile(
            intro_like_score=intro_like,
            pulse_drop_score=pulse_drop,
            dropout_risk=_score(segment.metadata.get("dropout_risk"), pulse_drop),
            breakdown_like_score=_score(segment.metadata.get("breakdown_like_score"), 1.0 if section in {"breakdown", "outro"} else 0.0),
            static_risk=_score(segment.metadata.get("static_risk"), _score(_nested(segment, "pace_feature_vector_v2", "static_risk"), _score(segment.metadata.get("ai_static_low_end_penalty"), 0.0))),
            chaos_risk=_score(segment.metadata.get("chaos_risk"), _score(_nested(segment, "pace_feature_vector_v2", "chaos_risk"), _score(segment.metadata.get("ai_chaos_penalty"), 0.0))),
            overpush_risk=_score(segment.metadata.get("overpush_risk"), _score(_nested(segment, "pace_feature_vector_v2", "overpush_risk"), 0.0)),
        ),
        pace_assist=PaceAssistV34Profile(
            primary_ASC_spm=primary_asc,
            ASC_strength=asc_strength,
            ASC_stability=asc_stability,
            pulse_clarity=pulse_clarity,
            rhythm_predictability=rhythm_predictability,
            pulse_dropout_risk=pulse_dropout_risk,
            half_time_shift_risk=half_time_shift_risk,
            fake_groove_risk=fake_groove_risk,
            pace_assist_score=pace_assist_score,
            ai_semantic_scores={str(k): _score(v, 0.0) for k, v in ai_semantic.items() if k != "provider"},
            user_response_effect=_score(segment.metadata.get("user_response_effect"), 0.50),
        ),
        block=BlockProfile(
            preferred_block_bars=config.connector_block_bars if segment_use in {SegmentUse.DRIVE_CONNECTOR.value, SegmentUse.EXIT_CONNECTOR.value} else config.default_block_bars,
            min_hold_bars=config.stable_hold_bars_min,
            min_hold_sec=max(config.min_hold_sec, segment.duration_sec if segment_use == SegmentUse.STABLE.value else 0.0),
            stable_duration_sec=segment.duration_sec,
            valid_runtime_block=segment_use != SegmentUse.REJECT.value and segment.phrase_confidence >= config.min_phrase_confidence,
            phrase_confidence=segment.phrase_confidence,
        ),
        is_contiguous_original_audio=bool(segment.metadata.get("is_contiguous_original_audio", True)),
        combined_confidence=_score(segment.metadata.get("combined_confidence"), _score(_nested(segment, "pace_feature_vector_v2", "combined_confidence"), segment.phrase_confidence)),
        manual_disabled=bool(segment.metadata.get("manual_disabled", False)),
    )


def segments_to_v3_records(segments: list[Segment], config: V3Config = V3Config()) -> list[SegmentRecord]:
    return [segment_to_v3_record(segment, config) for segment in segments]


def _segment_use(segment: Segment) -> str:
    raw = str(segment.metadata.get("segment_use") or "").upper()
    section = str(segment.metadata.get("ai_corrected_section_type") or segment.section_type.value).split(".")[-1].lower()
    if raw == "STABLE":
        return SegmentUse.STABLE.value
    if raw == "ENTRY_ONLY" or section == "intro":
        return SegmentUse.ENTRY_ONLY.value
    if raw in {"TRANSITION", "DRIVE_CONNECTOR"}:
        return SegmentUse.DRIVE_CONNECTOR.value
    if raw in {"EXIT_ONLY", "EXIT_CONNECTOR"} or section in {"breakdown", "outro"}:
        return SegmentUse.EXIT_CONNECTOR.value
    if raw == "REJECT":
        return SegmentUse.REJECT.value
    return SegmentUse.STABLE.value


def _nested(segment: Segment, parent: str, key: str) -> Any:
    value = segment.metadata.get(parent)
    return value.get(key) if isinstance(value, dict) else None


def _score(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return max(0.0, min(1.0, float(default)))


def _raw_float(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)
