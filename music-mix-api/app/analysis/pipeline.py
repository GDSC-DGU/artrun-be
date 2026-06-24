from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

from app.analysis.audio_io import prepare_audio
from app.analysis.ai_music_segment_analyzer import AI_SEGMENT_ANALYSIS_KEYS, annotate_segments_with_ai_running_feel
from app.analysis.energy import EnergyFeatures, compute_energy_score, energy_level
from app.analysis.labeler import SectionStats, relabel_for_running
from app.analysis.multi_model_pace_feature_core import MULTI_MODEL_METADATA_KEYS
from app.analysis.multi_model_pace_features import annotate_segments_with_multi_model_pace_features
from app.analysis.pace_assist_analyzer_v3_4 import (
    PACE_ASSIST_V3_4_FEATURE_KEYS,
    annotate_segments_with_pace_assist_v3_4,
)
from app.analysis.pace_assist_features import PACE_ASSIST_FEATURE_KEYS, annotate_segments_with_pace_assist_features
from app.analysis.rhythm_validator import build_phrase_grid
from app.analysis.segment_clip_exporter import export_segment_clips
from app.analysis.speed_degree_pace_features_v2 import SPEED_DEGREE_V2_METADATA_KEYS, annotate_segments_with_speed_degree_v2
from app.domain.models import RhythmResult, SectionType, Segment


ANALYSIS_VERSION = "mobile-running-music-analysis-v0.3.4"


@dataclass(frozen=True)
class BarFeatures:
    bar_index: int
    start_sec: float
    end_sec: float
    volume_score: float
    brightness_score: float
    onset_density_score: float
    sound_density_score: float
    dynamic_change_score: float


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _round_list(values: list[float], digits: int = 4) -> list[float]:
    return [round(float(v), digits) for v in values]


def _safe_percentile_scale(values, low_pct: float = 10.0, high_pct: float = 90.0):
    import numpy as np

    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return arr
    low = float(np.percentile(arr, low_pct))
    high = float(np.percentile(arr, high_pct))
    if high <= low:
        return np.zeros_like(arr)
    return np.clip((arr - low) / (high - low), 0.0, 1.0)


def _bpm_score(bpm: float) -> float:
    # Keep BPM as a light contributor only. This prevents fast-but-light music
    # from being treated as high energy on tempo alone.
    return _clamp((bpm - 80.0) / 90.0)


def _load_audio(audio_path: str | Path):
    try:
        import librosa
    except Exception as exc:  # pragma: no cover - exercised by environment setup
        raise RuntimeError("librosa is required for local audio analysis") from exc

    return librosa.load(str(audio_path), sr=44100, mono=True)


def _estimate_rhythm(y, sr: int, duration_sec: float) -> RhythmResult:
    import librosa
    import numpy as np

    hop_length = 512
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr, hop_length=hop_length, onset_envelope=onset_env, trim=False)
    bpm = float(np.asarray(tempo).reshape(-1)[0])
    beat_times = librosa.frames_to_time(beat_frames, sr=sr, hop_length=hop_length).tolist()

    if not beat_times or bpm <= 0:
        bpm = 120.0
        beat_interval = 60.0 / bpm
        beat_times = np.arange(0.0, duration_sec, beat_interval).tolist()

    bar_times = beat_times[::4]
    if not bar_times or bar_times[0] > 1.5:
        beat_interval = 60.0 / bpm
        bar_interval = beat_interval * 4.0
        bar_times = np.arange(0.0, duration_sec, bar_interval).tolist()
        beat_times = np.arange(0.0, duration_sec, beat_interval).tolist()

    phrase_8, phrase_16 = build_phrase_grid(bar_times)
    confidence = 0.75 if len(bar_times) >= 8 else 0.45
    return RhythmResult(
        bpm=bpm,
        beats=_round_list(beat_times),
        downbeats=_round_list(bar_times),
        bar_times=_round_list(bar_times),
        phrase_8bar_times=_round_list(phrase_8),
        phrase_16bar_times=_round_list(phrase_16),
        confidence=confidence,
    )


def _extract_frame_features(y, sr: int):
    import librosa
    import numpy as np

    hop_length = 512
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=hop_length)[0]
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, n_fft=2048, hop_length=hop_length)[0]
    bandwidth = librosa.feature.spectral_bandwidth(y=y, sr=sr, n_fft=2048, hop_length=hop_length)[0]
    flatness = librosa.feature.spectral_flatness(y=y, n_fft=2048, hop_length=hop_length)[0]
    stft_mag = abs(librosa.stft(y, n_fft=2048, hop_length=hop_length))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low_mask = (freqs >= 35.0) & (freqs <= 180.0)
    total_energy = stft_mag.sum(axis=0) + 1e-9
    low_ratio = stft_mag[low_mask].sum(axis=0) / total_energy
    onset_env = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop_length)
    frame_count = min(len(rms), len(centroid), len(bandwidth), len(flatness), len(low_ratio), len(onset_env))
    frame_times = librosa.frames_to_time(np.arange(frame_count), sr=sr, hop_length=hop_length)
    return {
        "frame_times": frame_times,
        "rms": rms[:frame_count],
        "centroid": centroid[:frame_count],
        "bandwidth": bandwidth[:frame_count],
        "flatness": flatness[:frame_count],
        "low_ratio": low_ratio[:frame_count],
        "onset_env": onset_env[:frame_count],
    }


def _mean_in_range(values, times, start: float, end: float) -> float:
    import numpy as np

    idx = np.where((times >= start) & (times < end))[0]
    if len(idx) == 0:
        return 0.0
    return float(np.mean(values[idx]))


def _aggregate_bars(frame_features: dict[str, Any], bar_times: list[float], duration_sec: float) -> list[BarFeatures]:
    import numpy as np

    if not bar_times:
        return []

    times = frame_features["frame_times"]
    ends = bar_times[1:] + [duration_sec]
    raw_rows = []
    for i, (start, end) in enumerate(zip(bar_times, ends), start=1):
        if end <= start:
            continue
        rms = _mean_in_range(frame_features["rms"], times, start, end)
        centroid = _mean_in_range(frame_features["centroid"], times, start, end)
        bandwidth = _mean_in_range(frame_features["bandwidth"], times, start, end)
        flatness = _mean_in_range(frame_features["flatness"], times, start, end)
        low_ratio = _mean_in_range(frame_features["low_ratio"], times, start, end)
        onset = _mean_in_range(frame_features["onset_env"], times, start, end)
        raw_rows.append((i, start, end, rms, centroid, bandwidth, flatness, low_ratio, onset))

    if not raw_rows:
        return []

    rms_values = np.array([r[3] for r in raw_rows], dtype=float)
    centroid_values = np.array([r[4] for r in raw_rows], dtype=float)
    bandwidth_values = np.array([r[5] for r in raw_rows], dtype=float)
    flatness_values = np.array([r[6] for r in raw_rows], dtype=float)
    low_ratio_values = np.array([r[7] for r in raw_rows], dtype=float)
    onset_values = np.array([r[8] for r in raw_rows], dtype=float)

    rms_rel = _safe_percentile_scale(rms_values)
    onset_rel = _safe_percentile_scale(onset_values)
    centroid_rel = _safe_percentile_scale(centroid_values)
    low_abs_values = np.clip(low_ratio_values / 0.22, 0.0, 1.0)
    density_raw = 0.40 * bandwidth_values / 6000.0 + 0.20 * flatness_values * 5.0 + 0.40 * low_abs_values
    density_rel = _safe_percentile_scale(density_raw)

    bars: list[BarFeatures] = []
    previous_rms = float(rms_values[0])
    for idx, row in enumerate(raw_rows):
        bar_index, start, end, rms, centroid, bandwidth, flatness, low_ratio, onset = row
        volume_abs = _clamp((rms - 0.015) / 0.18)
        onset_abs = _clamp(onset / 2.5)
        brightness_abs = _clamp(centroid / 5200.0)
        bass_abs = _clamp(low_ratio / 0.22)
        density_abs = _clamp(0.40 * bandwidth / 6000.0 + 0.20 * flatness * 5.0 + 0.40 * bass_abs)
        dynamic = _clamp(abs(rms - previous_rms) / 0.08)
        previous_rms = float(rms)
        bars.append(
            BarFeatures(
                bar_index=int(bar_index),
                start_sec=round(float(start), 4),
                end_sec=round(float(end), 4),
                volume_score=round(0.55 * float(rms_rel[idx]) + 0.45 * volume_abs, 4),
                brightness_score=round(0.45 * float(centroid_rel[idx]) + 0.55 * brightness_abs, 4),
                onset_density_score=round(0.60 * float(onset_rel[idx]) + 0.40 * onset_abs, 4),
                sound_density_score=round(0.45 * float(density_rel[idx]) + 0.55 * density_abs, 4),
                dynamic_change_score=round(dynamic, 4),
            )
        )
    return bars


def _segment_ranges(bar_count: int) -> list[tuple[int, int]]:
    if bar_count <= 0:
        return []
    ranges: list[tuple[int, int]] = []
    start = 1
    chunk = 16
    while start <= bar_count:
        end = min(bar_count, start + chunk - 1)
        if end - start + 1 < 8 and ranges:
            prev_start, _ = ranges[-1]
            ranges[-1] = (prev_start, end)
        else:
            ranges.append((start, end))
        start = end + 1
    return ranges


def _average(items: list[float]) -> float:
    return sum(items) / len(items) if items else 0.0


def _build_segments(track_id: str, audio_path: str, rhythm: RhythmResult, bars: list[BarFeatures], profile: str) -> list[Segment]:
    if not bars:
        return []

    bpm_component = _bpm_score(rhythm.bpm)
    provisional_scores = []
    for bar in bars:
        features = EnergyFeatures(
            volume_score=bar.volume_score,
            onset_density_score=bar.onset_density_score,
            brightness_score=bar.brightness_score,
            sound_density_score=bar.sound_density_score,
            bpm_score=bpm_component,
            dynamic_change_score=bar.dynamic_change_score,
        )
        provisional_scores.append(compute_energy_score(features, profile=profile)[0])

    segments: list[Segment] = []
    ranges = _segment_ranges(len(bars))
    track_end = bars[-1].end_sec
    for i, (start_bar, end_bar) in enumerate(ranges, start=1):
        segment_bars = bars[start_bar - 1 : end_bar]
        segment_scores = provisional_scores[start_bar - 1 : end_bar]
        start_sec = segment_bars[0].start_sec
        end_sec = segment_bars[-1].end_sec
        if end_sec <= start_sec:
            continue

        features = EnergyFeatures(
            volume_score=_average([b.volume_score for b in segment_bars]),
            onset_density_score=_average([b.onset_density_score for b in segment_bars]),
            brightness_score=_average([b.brightness_score for b in segment_bars]),
            sound_density_score=_average([b.sound_density_score for b in segment_bars]),
            bpm_score=bpm_component,
            dynamic_change_score=_average([b.dynamic_change_score for b in segment_bars]),
        )
        energy_score, level = compute_energy_score(features, profile=profile)
        position_ratio = _clamp((start_sec + end_sec) / 2.0 / max(track_end, 1.0))
        stats = SectionStats(
            mean_energy=energy_score,
            start_energy=segment_scores[0] if segment_scores else energy_score,
            end_energy=segment_scores[-1] if segment_scores else energy_score,
            mean_onset_density=features.onset_density_score,
            position_ratio=position_ratio,
            model_label=None,
        )
        section_type = relabel_for_running(stats)
        phrase_confidence = min(1.0, rhythm.confidence + (0.15 if (start_bar - 1) % 8 == 0 else 0.0))
        entry_quality = min(1.0, phrase_confidence + (0.05 if (start_bar - 1) % 16 == 0 else 0.0))
        exit_quality = min(1.0, phrase_confidence + (0.05 if end_bar % 8 == 0 else 0.0))
        loudness_density_score = _clamp(0.55 * features.volume_score + 0.45 * features.sound_density_score)
        segments.append(
            Segment(
                segment_id=f"{track_id}_seg_{i:03d}",
                track_id=track_id,
                audio_url=audio_path,
                start_sec=round(start_sec, 3),
                end_sec=round(end_sec, 3),
                start_bar=start_bar,
                end_bar=end_bar,
                section_type=section_type,
                energy_score=round(energy_score, 4),
                energy_level=level,
                bpm=round(rhythm.bpm, 3),
                phrase_confidence=round(phrase_confidence, 4),
                is_good_entry=(start_bar - 1) % 8 == 0,
                is_good_exit=True,
                model_section_label=None,
                final_section_label=section_type.value,
                volume_score=round(features.volume_score, 4),
                brightness_score=round(features.brightness_score, 4),
                onset_density_score=round(features.onset_density_score, 4),
                sound_density_score=round(features.sound_density_score, 4),
                metadata={
                    "analysis_version": ANALYSIS_VERSION,
                    "entry_quality": round(entry_quality, 4),
                    "exit_quality": round(exit_quality, 4),
                    "loudness_density_score": round(loudness_density_score, 4),
                    "section_type_signal": section_type.value,
                    "phrase_bar_multiple": 16 if (end_bar - start_bar + 1) >= 16 else 8,
                },
            )
        )
    return segments


def segment_to_dict(segment: Segment) -> dict[str, Any]:
    data = asdict(segment)
    data["section_type"] = segment.section_type.value
    for key in PACE_ASSIST_FEATURE_KEYS:
        if key in segment.metadata:
            data[key] = segment.metadata[key]
    for key in AI_SEGMENT_ANALYSIS_KEYS:
        if key in segment.metadata:
            data[key] = segment.metadata[key]
    for key in MULTI_MODEL_METADATA_KEYS:
        if key in segment.metadata:
            data[key] = segment.metadata[key]
    for key in SPEED_DEGREE_V2_METADATA_KEYS:
        if key in segment.metadata:
            data[key] = segment.metadata[key]
    for key in PACE_ASSIST_V3_4_FEATURE_KEYS:
        if key in segment.metadata:
            data[key] = segment.metadata[key]
    for key in ("entry_quality", "exit_quality", "loudness_density_score", "segment_clip_path", "phrase_bar_multiple"):
        if key in segment.metadata:
            data[key] = segment.metadata[key]
    if "pace_assist_debug" in segment.metadata:
        data["pace_assist_debug"] = segment.metadata["pace_assist_debug"]
    if "section_type_original" in segment.metadata:
        data["section_type_original"] = segment.metadata["section_type_original"]
    return data


def analysis_to_jsonable(result: dict[str, Any]) -> dict[str, Any]:
    out = dict(result)
    out["rhythm"] = asdict(result["rhythm"])
    out["segments"] = [segment_to_dict(s) for s in result["segments"]]
    out["bar_features"] = [asdict(b) for b in result.get("bar_features", [])]
    return out


def analyze_track(track_id: str, audio_path: str | Path, profile: str = "basic") -> dict[str, Any]:
    prepared = prepare_audio(audio_path)
    y, sr = _load_audio(prepared.mono_wav)

    try:
        import librosa
    except Exception as exc:  # pragma: no cover
        raise RuntimeError("librosa is required for local audio analysis") from exc

    duration_sec = float(librosa.get_duration(y=y, sr=sr))
    rhythm = _estimate_rhythm(y, sr, duration_sec)
    frame_features = _extract_frame_features(y, sr)
    bars = _aggregate_bars(frame_features, rhythm.bar_times, duration_sec)
    segments = _build_segments(track_id, str(Path(audio_path)), rhythm, bars, profile)
    segments = annotate_segments_with_pace_assist_features(
        segments=segments,
        audio_path=prepared.mono_wav,
        beat_times=rhythm.beats,
        bpm=rhythm.bpm,
    )
    clip_paths = export_segment_clips(
        audio_path=prepared.stereo_wav,
        segments=segments,
        output_dir=Path("outputs") / "clips" / track_id,
    )
    if clip_paths:
        segments = [
            replace(segment, metadata={**segment.metadata, "segment_clip_path": clip_paths[segment.segment_id]})
            for segment in segments
        ]
    segments = annotate_segments_with_ai_running_feel(segments)
    segments = annotate_segments_with_multi_model_pace_features(segments)
    segments = annotate_segments_with_speed_degree_v2(segments)
    segments = annotate_segments_with_pace_assist_v3_4(
        segments=segments,
        audio_path=prepared.mono_wav,
    )

    avg_energy = _average([s.energy_score for s in segments])
    return {
        "analysis_version": ANALYSIS_VERSION,
        "track_id": track_id,
        "audio_path": str(Path(audio_path)),
        "prepared_audio_path": str(prepared.mono_wav),
        "profile": profile,
        "duration_sec": round(duration_sec, 3),
        "bpm": round(rhythm.bpm, 3),
        "rhythm": rhythm,
        "beat_times": rhythm.beats,
        "bar_times": rhythm.bar_times,
        "phrase_8bar_times": rhythm.phrase_8bar_times,
        "phrase_16bar_times": rhythm.phrase_16bar_times,
        "avg_energy_score": round(avg_energy, 4),
        "segments": segments,
        "bar_features": bars,
    }
