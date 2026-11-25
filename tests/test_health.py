from labor_law_assistant import health


def test_health_returns_ok():
    assert health() == "ok"
