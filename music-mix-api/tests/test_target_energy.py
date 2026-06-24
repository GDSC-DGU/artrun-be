from app.recommendation.target_energy import compute_target_energy, compute_speed_gap_ratio


def test_speed_gap_positive_when_runner_is_slower():
    gap = compute_speed_gap_ratio(360, 300)
    assert round(gap, 3) == 0.167


def test_target_energy_increases_when_runner_is_slower():
    decision = compute_target_energy(360, 300, "pace_up")
    assert decision.target_energy_score > 0.8
    assert decision.target_energy_level == 5
    assert decision.main_reason == "runner_is_slower_than_target"


def test_target_energy_decreases_when_runner_is_faster():
    decision = compute_target_energy(280, 300, "steady_run")
    assert decision.target_energy_score < 0.55
    assert decision.main_reason == "runner_is_faster_than_target"
