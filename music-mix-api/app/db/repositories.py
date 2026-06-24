from __future__ import annotations

from dataclasses import dataclass, field
from app.domain.models import Segment, RecommendationConstraints


class SegmentRepository:
    def query_candidates(self, target_energy: float, constraints: RecommendationConstraints) -> list[Segment]:
        raise NotImplementedError

    def get_segment(self, segment_id: str) -> Segment | None:
        raise NotImplementedError


@dataclass
class InMemorySegmentRepository(SegmentRepository):
    segments: list[Segment] = field(default_factory=list)

    def query_candidates(self, target_energy: float, constraints: RecommendationConstraints) -> list[Segment]:
        low = target_energy - constraints.energy_window
        high = target_energy + constraints.energy_window
        out = [
            s
            for s in self.segments
            if low <= s.energy_score <= high
            and s.is_good_entry
            and constraints.min_segment_duration_sec <= s.duration_sec <= constraints.max_segment_duration_sec
        ]
        return sorted(out, key=lambda s: abs(s.energy_score - target_energy))[:50]

    def get_segment(self, segment_id: str) -> Segment | None:
        return next((s for s in self.segments if s.segment_id == segment_id), None)
