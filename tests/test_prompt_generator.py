import pytest
from unittest.mock import patch
from schemas import BusinessProfile, Service
from prompt_generator import BuyerPrompt, PromptSet, validate_prompt_set, generate_prompts

def profile():
    return BusinessProfile(name="Attention Lasso", website="https://attentionlasso.com",
        services=[Service(name="AI Search Optimization", source_url="https://attentionlasso.com/services",
                          evidence="AI search optimization")])

def prompt(question="Which agencies can improve visibility in AI search?"):
    return BuyerPrompt(prompt=question, intent="provider", stage="consideration",
                       service="AI Search Optimization", persona="Marketing manager",
                       rationale="Buyer seeks a provider")

def test_valid_prompt():
    assert validate_prompt_set(PromptSet(prompts=[prompt()]), profile(), 20).prompts[0].intent == "provider"

def test_reject_unverified_service():
    p = prompt()
    p.service = "Predictive eye-tracking"
    with pytest.raises(ValueError, match="unverified service"):
        validate_prompt_set(PromptSet(prompts=[p]), profile(), 20)

def test_reject_duplicates():
    with pytest.raises(ValueError, match="Duplicate"):
        validate_prompt_set(PromptSet(prompts=[prompt(), prompt()]), profile(), 20)

def test_reject_over_requested_count():
    with pytest.raises(ValueError, match="more prompts"):
        validate_prompt_set(PromptSet(prompts=[prompt()]), profile(), 0)

def test_generation_uses_auto_tool_and_profile():
    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                assert kwargs["tool_choice"]["type"] == "auto"
                assert "AI Search Optimization" in kwargs["messages"][0]["content"]
                data = {"prompts": [prompt().model_dump()]}
                block = type("Block", (), {"type":"tool_use","name":"submit_prompts","input":data})()
                return type("Response", (), {"stop_reason":"tool_use","content":[block]})()
    with patch("anthropic.Anthropic", return_value=FakeClient()):
        assert len(generate_prompts(profile(), "test-key", count=5).prompts) == 1

def test_no_tool_response_is_actionable():
    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return type("Response", (), {"stop_reason":"end_turn","content":[]})()
    with patch("anthropic.Anthropic", return_value=FakeClient()):
        with pytest.raises(ValueError, match="structured prompt set"):
            generate_prompts(profile(), "test-key", count=5)
