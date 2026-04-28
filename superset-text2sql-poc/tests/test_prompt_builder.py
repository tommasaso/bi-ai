from app.prompt_builder import build_system_prompt


def test_prompt_includes_schema():
    prompt = build_system_prompt()
    assert "stop_events" in prompt
    assert "lines" in prompt
    assert "vehicle_events" in prompt


def test_prompt_includes_metrics():
    prompt = build_system_prompt()
    assert "average_delay" in prompt
    assert "punctuality_rate" in prompt
    assert "daily_passenger_count" in prompt


def test_prompt_includes_security_constraints():
    prompt = build_system_prompt()
    assert "INSERT" in prompt
    assert "DELETE" in prompt
    assert "DROP" in prompt


def test_prompt_includes_json_output_instruction():
    prompt = build_system_prompt()
    assert "JSON" in prompt
    assert "status" in prompt
    assert "sql" in prompt
    assert "explanation" in prompt
