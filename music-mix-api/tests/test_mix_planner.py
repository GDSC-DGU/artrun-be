from app.domain.models import Segment, SectionType, TransitionMethod
from app.mix.planner import auto_mix_plan, build_direct_fade_plan, build_transition_mix_plan


def segment():
    return Segment("s", "t", "url", 58, 118, 33, 64, SectionType.DROP, 0.9, 5, 128, 0.9)


def test_direct_fade_plan_has_two_actions():
    plan = build_direct_fade_plan(100, segment())
    assert plan.method == TransitionMethod.DIRECT_FADE
    assert len(plan.timeline) == 2


def test_auto_uses_phrase_crossfade_when_bpm_close_and_phrase_confident():
    plan = auto_mix_plan(100, segment(), bpm_diff=3)
    assert plan.method == TransitionMethod.PHRASE_ALIGNED_CROSSFADE


def test_auto_uses_direct_fade_when_bpm_far():
    plan = auto_mix_plan(100, segment(), bpm_diff=12)
    assert plan.method == TransitionMethod.DIRECT_FADE


def test_transition_plan_uses_eight_bar_equal_power_crossfade():
    current = Segment("c", "track2", "url", 15, 75, 9, 40, SectionType.GROOVE, 0.55, 3, 124, 0.8)
    nxt = Segment("n", "track1", "url", 60, 90, 33, 48, SectionType.DROP, 0.90, 5, 128, 0.8)
    plan = build_transition_mix_plan(current, nxt)
    assert plan.method == TransitionMethod.PHRASE_ALIGNED_CROSSFADE
    assert plan.duration_bars == 8
    assert plan.timeline[0].action == "equal_power_fade_out"
