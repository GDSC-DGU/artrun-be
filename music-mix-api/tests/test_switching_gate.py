from app.recommendation.switching_gate import should_request_new_segment


def test_gate_blocks_short_play_time():
    assert not should_request_new_segment(10, 100, 0.5, 0.9)


def test_gate_blocks_short_switch_interval():
    assert not should_request_new_segment(40, 20, 0.5, 0.9)


def test_gate_blocks_small_energy_delta():
    assert not should_request_new_segment(40, 60, 0.50, 0.60)


def test_gate_allows_valid_switch():
    assert should_request_new_segment(40, 60, 0.50, 0.80)
