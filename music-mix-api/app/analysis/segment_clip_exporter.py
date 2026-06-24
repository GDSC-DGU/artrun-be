from __future__ import annotations

from pathlib import Path

from app.domain.models import Segment


def export_segment_clips(
    *,
    audio_path: str | Path,
    segments: list[Segment],
    output_dir: str | Path,
    sr: int = 44100,
) -> dict[str, str]:
    """Export phrase-aligned segment clips for offline AI analysis.

    The signal analyzer owns clip boundaries; AI only judges the exported clips.
    Failures are non-fatal so local analysis can still produce segment JSON on
    machines with limited codec support.
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    clip_paths: dict[str, str] = {}

    try:
        import librosa
        import soundfile as sf
    except Exception:
        return clip_paths

    for segment in segments:
        duration = max(0.0, segment.end_sec - segment.start_sec)
        if duration <= 0:
            continue
        clip_path = out_dir / f"{segment.segment_id}.wav"
        try:
            y, loaded_sr = librosa.load(
                str(audio_path),
                sr=sr,
                mono=False,
                offset=max(0.0, segment.start_sec),
                duration=duration,
            )
            if getattr(y, "ndim", 1) == 2:
                y = y.T
            sf.write(str(clip_path), y, loaded_sr)
            clip_paths[segment.segment_id] = str(clip_path)
        except Exception:
            continue

    return clip_paths
