# tests/test_llm_client.py
from app.ai.llm_client import LLMClient

def test_llm_noop_echo():
    c = LLMClient(provider="noop")
    r = c.call_llm("hello world")
    assert r["provider"] == "noop"
    assert "NOOP ECHO" in r["text"]