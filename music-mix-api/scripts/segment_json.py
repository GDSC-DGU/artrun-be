from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.json_repository import load_segments
from app.domain.models import Segment


def segment_to_plain_dict(segment: Segment) -> dict:
    return {
        "segment_id": segment.segment_id,
        "track_id": segment.track_id,
        "audio_url": segment.audio_url,
        "start_sec": segment.start_sec,
        "end_sec": segment.end_sec,
        "section_type": segment.section_type.value,
        "energy_score": segment.energy_score,
        "energy_level": segment.energy_level,
        "bpm": segment.bpm,
        "phrase_confidence": segment.phrase_confidence,
    }
