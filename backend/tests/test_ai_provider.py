import json

from app.agents.prompts import load_prompt
from app.ai.factory import get_provider


def test_mock_generate_is_keyed_by_agent():
    p = get_provider()  # AI_PROVIDER=mock in conftest
    out = p.generate(system="AGENT: intake_extract\n...", user="κείμενο")
    data = json.loads(out)
    assert "parties" in data


def test_mock_embed_deterministic():
    p = get_provider()
    a, b = p.embed(["αγωγή"]), p.embed(["αγωγή"])
    assert a == b and len(a[0]) == 1024


def test_load_prompt_versioned():
    text, version = load_prompt("intake_extract")
    assert version == 1 and "AGENT: intake_extract" in text
