from app.domain.models import Segment, SectionType, PlaybackContext
from app.recommendation.scoring import compute_cadence_match, score_segment


def test_cadence_match_supports_half_bpm_relation():
    assert compute_cadence_match(86, 172) == 1.0


def test_drop_high_energy_scores_well():
    seg = Segment(
        segment_id="s1",
        track_id="t1",
        audio_url="url",
        start_sec=60,
        end_sec=120,
        start_bar=33,
        end_bar=64,
        section_type=SectionType.DROP,
        energy_score=0.90,
        energy_level=5,
        bpm=86,
        phrase_confidence=0.9,
    )
    breakdown = score_segment(seg, 0.88, 172, PlaybackContext())
    assert breakdown.energy_match > 0.95
    assert breakdown.cadence_match == 1.0
    assert breakdown.final_score > 0.80
