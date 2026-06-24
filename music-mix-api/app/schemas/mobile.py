from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class RunningSampleIn(BaseModel):
    timestamp_sec: float
    speed_kmh: float = Field(gt=0)
    cadence_spm: float | None = None


class RunningContextIn(BaseModel):
    current_pace_sec_per_km: float = Field(gt=0)
    target_pace_sec_per_km: float = Field(gt=0)
    current_cadence_spm: float | None = None
    target_cadence_spm: float | None = None
    speed_20s_ago_kmh: float | None = None
    running_samples: list[RunningSampleIn] = []
    previous_target_music_speed_degree: float | None = None
    active_speed_zone: str | None = None
    candidate_speed_zone: str | None = None
    candidate_since_sec: float | None = None
    last_zone_change_sec: float | None = None
    near_phrase_boundary: bool = True
    running_mode: str = "steady_run"
    fatigue_level: float | None = Field(default=None, ge=0, le=1)


class PlaybackContextIn(BaseModel):
    current_track_id: str | None = None
    current_segment_id: str | None = None
    current_position_sec: float = 0.0
    current_segment_played_sec: float = 0.0
    seconds_since_last_switch: float = 0.0
    previous_target_energy: float = 0.55
    recent_track_ids: list[str] = []
    recent_segment_ids: list[str] = []
    force_adjust: bool = False
    current_music_ASC_spm: float | None = None


class ClientContextIn(BaseModel):
    platform: str = "unknown"
    app_version: str = "0.0.0"
    network_type: str = "unknown"
    battery_saver_enabled: bool = False


class ConstraintsIn(BaseModel):
    min_segment_duration_sec: float = 30.0
    max_segment_duration_sec: float = 90.0
    allow_same_track: bool = False
    prefer_preloaded_audio: bool = True
    energy_window: float = 0.15


class NextSegmentRequest(BaseModel):
    session_id: str
    user_id: str | None = None
    running_context: RunningContextIn
    playback_context: PlaybackContextIn
    client_context: ClientContextIn = ClientContextIn()
    constraints: ConstraintsIn = ConstraintsIn()


class MixPlanRequest(BaseModel):
    current_segment_id: str
    next_segment_id: str
    current_position_sec: float | None = None
