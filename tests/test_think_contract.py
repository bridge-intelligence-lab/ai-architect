import json
from pathlib import Path


def test_messages_schema_exists():
    path = Path("contracts/messages.json")
    assert path.exists(), "contracts/messages.json should exist"
    data = json.loads(path.read_text())
    assert "defs" in data
    assert "ThinkRequest" in data["defs"]
    assert "ToolResult" in data["defs"]


def test_think_request_minimal_fields():
    from jsonschema import validate
    import json

    schema = json.loads(Path("contracts/messages.json").read_text())
    think_req = {
        "request_type": "ThinkRequest",
        "session_id": "s1",
        "user_id": "u1",
        "prompt": "What next?"
    }
    validate(instance=think_req, schema=schema)


def test_tool_result_minimal_fields():
    from jsonschema import validate
    import json

    schema = json.loads(Path("contracts/messages.json").read_text())
    tool_res = {
        "request_type": "ToolResult",
        "session_id": "s1",
        "user_id": "u1",
        "correlation_id": "123e4567-e89b-12d3-a456-426614174000",
        "result": {"ok": True}
    }
    validate(instance=tool_res, schema=schema)
