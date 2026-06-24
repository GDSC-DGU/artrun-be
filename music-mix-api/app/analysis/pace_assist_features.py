from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.domain.models import SectionType, Segment

EPS = 1e-9

PACE_ASSIST_FEATURE_KEYS = [
    "beat_salience_score",
    "rhythmic_activity_score",
    "rhythmic_predictability_score",
    "syncopation_score",
    "groove_syncopation_fit",
    "bass_drive_score",
    "section_contrast_score",
    "static_low_end_penalty",
    "pace_push_score",
    "drop_likelihood_score",
    "corrected_section_type",
    "pace_role_hint",
]


@dataclass(frozen=True)
class PaceAssistConfig:
    sr: int = 44100
    hop_length: int = 512
    n_fft: int = 2048
    beat_window_sec: float = 0.070
    onset_peak_threshold_std: float = 0.35
    rhythmic_activity_full_scale_hz: float = 4.0
    low_band_hz: tuple[float, float] = (20.0, 160.0)
    ideal_syncopation: float = 0.45
    syncopation_half_width: float = 0.45
    drop_min_beat_salience: float = 0.50
    drop_min_rhythmic_activity: float = 0.42
    drop_min_bass_drive: float = 0.40
    drop_min_section_contrast: float = 0.45
    drop_max_static_penalty: float = 0.38


@dataclass(frozen=True)
class SegmentTiming:
    segment_id: str
    track_id: str
    start_sec: float
    end_sec: float
    section_type: str = "groove"
    bpm: float | None = None


@dataclass(frozen=True)
class PaceAssistFeatures:
    segment_id: str
    track_id: str
    beat_salience_score: float
    rhythmic_activity_score: float
    rhythmic_predictability_score: float
    syncopation_score: float
    groove_syncopation_fit: float
    bass_drive_score: float
    section_contrast_score: float
    static_low_end_penalty: float
    pace_push_score: float
    drop_likelihood_score: float
    corrected_section_type: str
    pace_role_hint: str
    debug: dict[str, float]


def annotate_segment_dicts_with_pace_assist_features(
    *,
    segments: Sequence[Mapping[str, Any]],
    audio_path: str | Path,
    beat_times: Sequence[float] | None = None,
    bpm: float | None = None,
    config: PaceAssistConfig = PaceAssistConfig(),
) -> list[dict[str, Any]]:
    import librosa

    y, sr = librosa.load(str(audio_path), sr=config.sr, mono=True)
    primitives = compute_audio_primitives(y=y, sr=sr, beat_times=beat_times, bpm=bpm, config=config)
    timings = [segment_from_dict(segment) for segment in segments]
    features = compute_segment_features(timings, primitives, config)

    out: list[dict[str, Any]] = []
    for raw, feature in zip(segments, features):
        merged = dict(raw)
        merged["section_type_original"] = raw.get("section_type", "groove")
        merged.update(asdict(feature))
        out.append(merged)
    return out


def annotate_segments_with_pace_assist_features(
    *,
    segments: Sequence[Segment],
    audio_path: str | Path,
    beat_times: Sequence[float] | None = None,
    bpm: float | None = None,
    config: PaceAssistConfig = PaceAssistConfig(),
) -> list[Segment]:
    raw_segments = [segment_to_raw_dict(segment) for segment in segments]
    annotated = annotate_segment_dicts_with_pace_assist_features(
        segments=raw_segments,
        audio_path=audio_path,
        beat_times=beat_times,
        bpm=bpm,
        config=config,
    )

    out: list[Segment] = []
    for segment, row in zip(segments, annotated):
        feature_payload = {key: row[key] for key in PACE_ASSIST_FEATURE_KEYS if key in row}
        feature_payload["pace_assist_debug"] = row.get("debug", {})
        corrected = feature_payload.get("corrected_section_type", segment.section_type.value)
        section_type = section_type_from_value(str(corrected))
        out.append(
            replace(
                segment,
                section_type=section_type,
                final_section_label=section_type.value,
                metadata={
                    **segment.metadata,
                    "section_type_original": row.get("section_type_original", segment.section_type.value),
                    **feature_payload,
                },
            )
        )
    return out


def segment_to_raw_dict(segment: Segment) -> dict[str, Any]:
    return {
        "segment_id": segment.segment_id,
        "track_id": segment.track_id,
        "start_sec": segment.start_sec,
        "end_sec": segment.end_sec,
        "section_type": segment.section_type.value,
        "bpm": segment.bpm,
        "energy_score": segment.energy_score,
        "phrase_confidence": segment.phrase_confidence,
        "volume_score": segment.volume_score,
        "brightness_score": segment.brightness_score,
        "onset_density_score": segment.onset_density_score,
        "sound_density_score": segment.sound_density_score,
        "metadata": segment.metadata,
    }


def section_type_from_value(value: str) -> SectionType:
    try:
        return SectionType(value)
    except ValueError:
        return SectionType.GROOVE


def compute_audio_primitives(*, y, sr: int, beat_times, bpm, config: PaceAssistConfig) -> dict[str, Any]:
    import librosa
    import numpy as np

    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=config.hop_length)
    onset_env = minmax(onset_env)
    frame_times = librosa.frames_to_time(np.arange(len(onset_env)), sr=sr, hop_length=config.hop_length)

    if beat_times is None:
        tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, onset_envelope=onset_env, hop_length=config.hop_length)
        beat_times_arr = librosa.frames_to_time(beat_frames, sr=sr, hop_length=config.hop_length)
        bpm_val = float(np.asarray(tempo).reshape(-1)[0])
    else:
        beat_times_arr = np.asarray(beat_times, dtype=float)
        bpm_val = float(bpm) if bpm else estimate_bpm(beat_times_arr)

    onset_peak_times = pick_onset_peaks(onset_env, frame_times, config.onset_peak_threshold_std)
    low_env, total_env = low_and_total_energy(y, sr, len(onset_env), config)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=config.n_fft, hop_length=config.hop_length)[0]
    centroid = minmax(resize_to(centroid, len(onset_env)))

    return {
        "bpm": bpm_val,
        "frame_times": frame_times,
        "onset_env": onset_env,
        "onset_peak_times": onset_peak_times,
        "beat_times": beat_times_arr,
        "low_env": low_env,
        "total_env": total_env,
        "centroid_env": centroid,
    }


def compute_segment_features(segments: Sequence[SegmentTiming], primitives: Mapping[str, Any], config: PaceAssistConfig) -> list[PaceAssistFeatures]:
    import numpy as np

    frame_times = np.asarray(primitives["frame_times"], dtype=float)
    onset_env = np.asarray(primitives["onset_env"], dtype=float)
    onset_peaks = np.asarray(primitives["onset_peak_times"], dtype=float)
    beat_times = np.asarray(primitives["beat_times"], dtype=float)
    low_env = np.asarray(primitives["low_env"], dtype=float)
    total_env = np.asarray(primitives["total_env"], dtype=float)
    centroid_env = np.asarray(primitives["centroid_env"], dtype=float)

    rows = []
    for segment in segments:
        mask = (frame_times >= segment.start_sec) & (frame_times < segment.end_sec)
        if not np.any(mask):
            mask = nearest_mask(frame_times, segment.start_sec, segment.end_sec)

        segment_beats = beat_times[(beat_times >= segment.start_sec) & (beat_times < segment.end_sec)]
        segment_onsets = onset_peaks[(onset_peaks >= segment.start_sec) & (onset_peaks < segment.end_sec)]
        duration = max(EPS, segment.end_sec - segment.start_sec)

        beat_salience, beat_ratio = beat_salience_score(onset_env, frame_times, segment_beats, segment.start_sec, segment.end_sec, config)
        rhythmic_activity, onset_density_hz = rhythmic_activity_score(segment_onsets, duration, config)
        predictability = rhythmic_predictability_score(segment_beats)
        syncopation = syncopation_score(segment_onsets, segment_beats)
        groove_fit = inverted_u(syncopation, config.ideal_syncopation, config.syncopation_half_width)
        bass_drive, bass_debug = bass_drive_score(low_env[mask], total_env[mask], frame_times[mask], segment_beats, config)
        static_penalty = static_low_end_penalty(
            low_end_ratio=bass_debug["low_end_ratio"],
            rhythmic_activity=rhythmic_activity,
            bass_modulation=bass_debug["bass_modulation_score"],
            beat_salience=beat_salience,
        )

        rows.append(
            {
                "segment": segment,
                "beat_salience": beat_salience,
                "rhythmic_activity": rhythmic_activity,
                "predictability": predictability,
                "syncopation": syncopation,
                "groove_fit": groove_fit,
                "bass_drive": bass_drive,
                "static_penalty": static_penalty,
                "stats": {
                    "onset_mean": mean(onset_env[mask]),
                    "low_mean": mean(low_env[mask]),
                    "total_mean": mean(total_env[mask]),
                    "centroid_mean": mean(centroid_env[mask]),
                    "beat_onset_ratio": beat_ratio,
                    "onset_density_hz": onset_density_hz,
                    **bass_debug,
                },
            }
        )

    result: list[PaceAssistFeatures] = []
    previous_stats = None
    for row in rows:
        segment = row["segment"]
        contrast = section_contrast_score(row["stats"], previous_stats)
        drop_like = drop_likelihood_score(
            row["beat_salience"],
            row["rhythmic_activity"],
            row["bass_drive"],
            contrast,
            row["static_penalty"],
            config,
        )
        pace_push = intrinsic_pace_push_score(
            row["beat_salience"],
            row["rhythmic_activity"],
            row["predictability"],
            row["groove_fit"],
            row["bass_drive"],
            contrast,
            row["static_penalty"],
        )
        corrected = corrected_section_type(
            segment.section_type,
            position_ratio(segment, segments),
            drop_like,
            pace_push,
            row["static_penalty"],
            row["rhythmic_activity"],
            row["bass_drive"],
        )
        role = pace_role_hint(segment.bpm, corrected, pace_push, row["bass_drive"], row["rhythmic_activity"], row["static_penalty"])
        debug = {**row["stats"], "section_contrast_score": contrast}
        result.append(
            PaceAssistFeatures(
                segment_id=segment.segment_id,
                track_id=segment.track_id,
                beat_salience_score=round4(row["beat_salience"]),
                rhythmic_activity_score=round4(row["rhythmic_activity"]),
                rhythmic_predictability_score=round4(row["predictability"]),
                syncopation_score=round4(row["syncopation"]),
                groove_syncopation_fit=round4(row["groove_fit"]),
                bass_drive_score=round4(row["bass_drive"]),
                section_contrast_score=round4(contrast),
                static_low_end_penalty=round4(row["static_penalty"]),
                pace_push_score=round4(pace_push),
                drop_likelihood_score=round4(drop_like),
                corrected_section_type=corrected,
                pace_role_hint=role,
                debug={key: round(float(value), 4) for key, value in debug.items()},
            )
        )
        previous_stats = row["stats"]
    return result


def beat_salience_score(onset_env, frame_times, beat_times, start, end, config: PaceAssistConfig) -> tuple[float, float]:
    import numpy as np

    mask = (frame_times >= start) & (frame_times < end)
    total = float(np.sum(onset_env[mask])) + EPS
    if len(beat_times) == 0 or total <= EPS:
        return 0.0, 0.0
    beat_mass = 0.0
    for beat_time in beat_times:
        win = (np.abs(frame_times - beat_time) <= config.beat_window_sec) & mask
        beat_mass += float(np.sum(onset_env[win]))
    ratio = beat_mass / total
    return clamp01(scale01(ratio, 0.20, 0.72)), ratio


def rhythmic_activity_score(onset_peak_times, duration_sec: float, config: PaceAssistConfig) -> tuple[float, float]:
    density_hz = float(len(onset_peak_times)) / max(duration_sec, EPS)
    return clamp01(density_hz / config.rhythmic_activity_full_scale_hz), density_hz


def rhythmic_predictability_score(beat_times) -> float:
    import numpy as np

    if len(beat_times) < 4:
        return 0.5
    ibi = np.diff(beat_times)
    cv = float(np.std(ibi) / (np.mean(ibi) + EPS))
    return clamp01(1.0 - 3.0 * cv)


def syncopation_score(onset_peak_times, beat_times) -> float:
    import numpy as np

    if len(onset_peak_times) == 0 or len(beat_times) < 2:
        return 0.0
    strong = 0
    weak = 0
    for onset_time in onset_peak_times:
        idx = int(np.searchsorted(beat_times, onset_time) - 1)
        if idx < 0 or idx >= len(beat_times) - 1:
            continue
        phase = (onset_time - beat_times[idx]) / max(EPS, beat_times[idx + 1] - beat_times[idx])
        if phase <= 0.18 or phase >= 0.82:
            strong += 1
        else:
            weak += 1
    total = strong + weak
    return 0.0 if total == 0 else clamp01(weak / total)


def bass_drive_score(low_env, total_env, frame_times, beat_times, config: PaceAssistConfig) -> tuple[float, dict[str, float]]:
    import numpy as np

    if len(low_env) == 0:
        return 0.0, {"low_end_ratio": 0.0, "bass_modulation_score": 0.0, "bass_onbeat_ratio": 0.0}

    low_end_ratio = clamp01(float(np.mean(low_env) / (np.mean(total_env) + EPS)))
    bass_modulation = clamp01(float(np.std(low_env) / (np.mean(low_env) + EPS)) / 0.85)

    if len(beat_times) == 0:
        bass_onbeat_ratio = 0.0
    else:
        beat_mass = 0.0
        for beat_time in beat_times:
            beat_mass += float(np.sum(low_env[np.abs(frame_times - beat_time) <= config.beat_window_sec]))
        bass_onbeat_ratio = beat_mass / (float(np.sum(low_env)) + EPS)

    score = (
        0.30 * scale01(low_end_ratio, 0.25, 0.75)
        + 0.35 * bass_modulation
        + 0.35 * scale01(bass_onbeat_ratio, 0.15, 0.65)
    )
    return clamp01(score), {
        "low_end_ratio": low_end_ratio,
        "bass_modulation_score": bass_modulation,
        "bass_onbeat_ratio": bass_onbeat_ratio,
    }


def static_low_end_penalty(*, low_end_ratio: float, rhythmic_activity: float, bass_modulation: float, beat_salience: float) -> float:
    low_dominance = scale01(low_end_ratio, 0.38, 0.78)
    penalty = (
        0.35 * low_dominance
        + 0.25 * (1.0 - clamp01(rhythmic_activity))
        + 0.25 * (1.0 - clamp01(bass_modulation))
        + 0.15 * (1.0 - clamp01(beat_salience))
    )
    return clamp01(penalty * low_dominance)


def section_contrast_score(current: Mapping[str, float], previous: Mapping[str, float] | None) -> float:
    import numpy as np

    if previous is None:
        return 0.35
    keys = ["onset_mean", "low_mean", "total_mean", "centroid_mean"]
    values = [abs(current[key] - previous[key]) / (abs(current[key]) + abs(previous[key]) + EPS) for key in keys]
    return clamp01(float(np.mean(values)) * 2.2)


def drop_likelihood_score(
    beat_salience: float,
    rhythmic_activity: float,
    bass_drive: float,
    section_contrast: float,
    static_penalty: float,
    config: PaceAssistConfig,
) -> float:
    raw = (
        0.25 * beat_salience
        + 0.22 * rhythmic_activity
        + 0.25 * bass_drive
        + 0.20 * section_contrast
        + 0.08 * (1.0 - static_penalty)
    )
    gate = 1.0
    if beat_salience < config.drop_min_beat_salience:
        gate *= 0.72
    if rhythmic_activity < config.drop_min_rhythmic_activity:
        gate *= 0.72
    if bass_drive < config.drop_min_bass_drive:
        gate *= 0.75
    if section_contrast < config.drop_min_section_contrast:
        gate *= 0.80
    if static_penalty > config.drop_max_static_penalty:
        gate *= 0.45
    return clamp01(raw * gate)


def intrinsic_pace_push_score(
    beat_salience: float,
    rhythmic_activity: float,
    predictability: float,
    groove_fit: float,
    bass_drive: float,
    section_contrast: float,
    static_penalty: float,
) -> float:
    return clamp01(
        0.22 * beat_salience
        + 0.20 * rhythmic_activity
        + 0.14 * predictability
        + 0.16 * groove_fit
        + 0.18 * bass_drive
        + 0.10 * section_contrast
        - 0.22 * static_penalty
    )


def corrected_section_type(
    original: str,
    position: float,
    drop_like: float,
    pace_push: float,
    static_penalty: float,
    rhythmic_activity: float,
    bass_drive: float,
) -> str:
    section = (original or "groove").lower()
    if position < 0.10 and pace_push < 0.65:
        return "intro"
    if position > 0.88 and pace_push < 0.65:
        return "outro"
    if section == "drop" or drop_like >= 0.62:
        if drop_like >= 0.62 and static_penalty < 0.38:
            return "drop"
        if static_penalty >= 0.45 or rhythmic_activity < 0.32:
            return "breakdown"
        return "groove"
    if section == "build_up":
        return "build_up" if pace_push >= 0.55 and rhythmic_activity >= 0.38 else "groove"
    if static_penalty > 0.55 and bass_drive < 0.45:
        return "breakdown"
    return section if section in {"intro", "groove", "build_up", "drop", "breakdown", "outro"} else "groove"


def pace_role_hint(
    bpm: float | None,
    corrected_section: str,
    pace_push: float,
    bass_drive: float,
    rhythmic_activity: float,
    static_penalty: float,
) -> str:
    bpm_value = float(bpm or 0.0)
    if static_penalty > 0.55 and pace_push < 0.55:
        return "low_drive_or_static_low_end"
    if corrected_section in {"intro", "outro", "breakdown"} and pace_push < 0.45:
        return "recovery"
    if 165 <= bpm_value <= 176 and pace_push >= 0.58:
        return "sprint_push"
    if 132 <= bpm_value <= 152 and pace_push >= 0.55:
        return "pace_up"
    if 85 <= bpm_value <= 102 and bass_drive >= 0.58:
        return "slow_heavy_power"
    if 140 <= bpm_value <= 152 and bass_drive < 0.45 and rhythmic_activity < 0.65:
        return "fast_light_control"
    if 118 <= bpm_value <= 130 and 0.35 <= pace_push <= 0.70:
        return "steady"
    return "general_candidate"


def segment_from_dict(raw: Mapping[str, Any]) -> SegmentTiming:
    return SegmentTiming(
        segment_id=str(raw.get("segment_id") or raw.get("id")),
        track_id=str(raw.get("track_id")),
        start_sec=float(raw.get("start_sec", 0.0)),
        end_sec=float(raw.get("end_sec", 0.0)),
        section_type=str(raw.get("section_type", "groove")),
        bpm=maybe_float(raw.get("bpm")),
    )


def low_and_total_energy(y, sr: int, target_len: int, config: PaceAssistConfig):
    import librosa
    import numpy as np

    stft = librosa.stft(y, n_fft=config.n_fft, hop_length=config.hop_length)
    power = np.abs(stft) ** 2
    freqs = librosa.fft_frequencies(sr=sr, n_fft=config.n_fft)
    low_mask = (freqs >= config.low_band_hz[0]) & (freqs < config.low_band_hz[1])
    low = np.sqrt(np.mean(power[low_mask, :], axis=0) + EPS) if np.any(low_mask) else np.zeros(power.shape[1])
    total = np.sqrt(np.mean(power, axis=0) + EPS)
    return minmax(resize_to(low, target_len)), minmax(resize_to(total, target_len))


def pick_onset_peaks(onset_env, frame_times, threshold_std: float):
    import numpy as np

    if len(onset_env) < 3:
        return np.array([], dtype=float)
    threshold = float(np.mean(onset_env) + threshold_std * np.std(onset_env))
    mid = onset_env[1:-1]
    mask = (mid > onset_env[:-2]) & (mid >= onset_env[2:]) & (mid >= threshold)
    return frame_times[np.flatnonzero(mask) + 1]


def estimate_bpm(beat_times) -> float:
    import numpy as np

    beats = np.asarray(beat_times, dtype=float)
    return 0.0 if len(beats) < 2 else float(60.0 / (np.median(np.diff(beats)) + EPS))


def position_ratio(segment: SegmentTiming, all_segments: Sequence[SegmentTiming]) -> float:
    if not all_segments:
        return 0.5
    track_end = max(item.end_sec for item in all_segments)
    return 0.5 if track_end <= 0 else clamp01(((segment.start_sec + segment.end_sec) / 2.0) / track_end)


def nearest_mask(frame_times, start: float, end: float):
    import numpy as np

    idx = int(np.argmin(np.abs(frame_times - ((start + end) / 2.0))))
    mask = np.zeros_like(frame_times, dtype=bool)
    mask[idx] = True
    return mask


def resize_to(values, target_len: int):
    import numpy as np

    values = np.asarray(values, dtype=float).reshape(-1)
    if len(values) == target_len:
        return values
    if len(values) == 0:
        return np.zeros(target_len, dtype=float)
    return np.interp(np.linspace(0, 1, target_len), np.linspace(0, 1, len(values)), values)


def minmax(values):
    import numpy as np

    values = np.asarray(values, dtype=float)
    if len(values) == 0:
        return values
    low = float(np.percentile(values, 5))
    high = float(np.percentile(values, 95))
    if high - low <= EPS:
        return np.zeros_like(values)
    return np.clip((values - low) / (high - low), 0.0, 1.0)


def scale01(value: float, low: float, high: float) -> float:
    return 0.0 if high <= low else clamp01((float(value) - low) / (high - low))


def inverted_u(value: float, center: float, half_width: float) -> float:
    return clamp01(1.0 - abs(float(value) - center) / max(EPS, half_width))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def mean(values) -> float:
    return 0.0 if len(values) == 0 else float(values.mean())


def maybe_float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def round4(value: float) -> float:
    return round(clamp01(float(value)), 4)
