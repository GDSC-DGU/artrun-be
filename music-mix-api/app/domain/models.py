from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class RunningMode(str, Enum):
    WARM_UP = "warm_up"
    STEADY_RUN = "steady_run"
    PACE_UP = "pace_up"
    SPRINT = "sprint"
    INTERVAL_HIGH = "interval_high"
    COOL_DOWN = "cool_down"


class SectionType(str, Enum):
    INTRO = "intro"
    GROOVE = "groove"
    BUILD_UP = "build_up"
    DROP = "drop"
    BREAKDOWN = "breakdown"
    OUTRO = "outro"
    UNKNOWN = "unknown"


class TransitionMethod(str, Enum):
    DIRECT_FADE = "direct_fade"
    BASIC_CROSSFADE = "basic_crossfade"
    PHRASE_ALIGNED_CROSSFADE = "phrase_aligned_equal_power_crossfade"
    EQ_CROSSFADE = "eq_crossfade"
    BUILD_UP_TO_DROP_SWITCH = "build_up_to_drop_switch"


@dataclass(frozen=True)
class RhythmResult:
    bpm: float
    beats: list[float]
    downbeats: list[float]
    bar_times: list[float]
    phrase_8bar_times: list[float]
    phrase_16bar_times: list[float]
    confidence: float
    meter: str = "4/4"


@dataclass(frozen=True)
class RawSection:
    start_sec: float
    end_sec: float
    model_label: str | None = None
    confidence: float = 0.5


@dataclass(frozen=True)
class Segment:
    segment_id: str
    track_id: str
    audio_url: str
    start_sec: float
    end_sec: float
    start_bar: int
    end_bar: int
    section_type: SectionType
    energy_score: float
    energy_level: int
    bpm: float
    phrase_confidence: float
    is_good_entry: bool = True
    is_good_exit: bool = True
    model_section_label: str | None = None
    final_section_label: str | None = None
    volume_score: float = 0.0
    brightness_score: float = 0.0
    onset_density_score: float = 0.0
    sound_density_score: float = 0.0
    drum_density_score: float | None = None
    bass_strength_score: float | None = None
    mobile_preload_priority: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def duration_sec(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)


@dataclass(frozen=True)
class RunningContext:
    current_pace_sec_per_km: float
    target_pace_sec_per_km: float
    running_mode: RunningMode | str
    current_cadence_spm: float | None = None
    target_cadence_spm: float | None = None
    speed_20s_ago_kmh: float | None = None
    running_samples: list[dict[str, Any]] = field(default_factory=list)
    previous_target_music_speed_degree: float | None = None
    active_speed_zone: str | None = None
    candidate_speed_zone: str | None = None
    candidate_since_sec: float | None = None
    last_zone_change_sec: float | None = None
    near_phrase_boundary: bool = True
    fatigue_level: float | None = None


@dataclass(frozen=True)
class PlaybackContext:
    current_track_id: str | None = None
    current_segment_id: str | None = None
    current_position_sec: float = 0.0
    current_segment_played_sec: float = 0.0
    seconds_since_last_switch: float = 0.0
    previous_target_energy: float = 0.55
    recent_track_ids: list[str] = field(default_factory=list)
    recent_segment_ids: list[str] = field(default_factory=list)
    force_adjust: bool = False
    current_music_ASC_spm: float | None = None


@dataclass(frozen=True)
class ClientContext:
    platform: str = "unknown"
    app_version: str = "0.0.0"
    network_type: str = "unknown"
    battery_saver_enabled: bool = False


@dataclass(frozen=True)
class RecommendationConstraints:
    min_segment_duration_sec: float = 30.0
    max_segment_duration_sec: float = 90.0
    allow_same_track: bool = False
    prefer_preloaded_audio: bool = True
    energy_window: float = 0.15


@dataclass(frozen=True)
class TargetEnergyDecision:
    current_speed_mps: float
    target_speed_mps: float
    speed_gap_ratio: float
    target_energy_score: float
    target_energy_level: int
    main_reason: str


@dataclass(frozen=True)
class PlaybackPlan:
    start_at_sec: float
    recommended_play_until_sec: float
    fade_out_current_sec: float = 2.0
    fade_in_next_sec: float = 2.0
    preload_required: bool = True
    transition_method: TransitionMethod = TransitionMethod.DIRECT_FADE


@dataclass(frozen=True)
class SegmentRecommendation:
    should_switch: bool
    decision: TargetEnergyDecision
    selected_segment: Segment | None = None
    playback_plan: PlaybackPlan | None = None
    reason: dict[str, Any] = field(default_factory=dict)
    retry_after_sec: int | None = None
