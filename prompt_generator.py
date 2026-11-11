"""Buyer-intent prompt generation from a reviewed business profile.

Prompt suggestions are hypotheses, not measured search volume or AI visibility.
"""
import json
import re
from typing import Literal
from pydantic import BaseModel, Field, model_validator
from schemas import BusinessProfile

INTENTS = ("problem", "solution", "provider", "comparison", "decision")
STAGES = ("awareness", "consideration", "decision")

class BuyerPrompt(BaseModel):
    prompt: str = Field(min_length=12, max_length=350)
    intent: Literal["problem", "solution", "provider", "comparison", "decision"]
    stage: Literal["awareness", "consideration", "decision"]
    service: str
    persona: str = Field(min_length=2, max_length=180)
    rationale: str = Field(min_length=5, max_length=400)

class PromptSet(BaseModel):
    prompts: list[BuyerPrompt] = Field(min_length=1, max_length=60)

SYSTEM = """Generate plausible, natural-language questions a real buyer might ask an AI assistant.
You are NOT measuring actual query frequency, AI recommendations, or share of voice.
Use ONLY the supplied reviewed business profile and the user's target buyer context.
Questions must be customer-centered, specific, varied, and useful for testing AI visibility.
Avoid inserting the business name in generic discovery questions.
Avoid fabricated competitors, performance claims, geography, prices or capabilities.
Include a mix of problem, solution, provider, comparison, decision intents and buyer journey stages.
Every prompt must map to one of the supplied services. Use the submit_prompts tool.
Keep each question standalone and understandable without additional context."""

def validate_prompt_set(result: PromptSet, profile: BusinessProfile, count: int):
    allowed = {s.name for s in profile.services}
    if len(result.prompts) > count:
        raise ValueError("Generated more prompts than requested")
    seen = set()
    for item in result.prompts:
        if item.service not in allowed:
            raise ValueError(f"Prompt references an unverified service: {item.service}")
        key = re.sub(r"\\W+", "", item.prompt.casefold())
        if key in seen:
            raise ValueError("Duplicate prompt in generated set")
        seen.add(key)
    return result

def generate_prompts(profile: BusinessProfile, api_key: str, *, count=20,
                     persona="", market="", model="claude-sonnet-5-5"):
    if not api_key:
        raise ValueError("Anthropic API key is required")
    if not profile.services:
        raise ValueError("The reviewed profile has no services")
    if not 5 <= count <= 40:
        raise ValueError("Choose 5 to 40 prompts")
    from anthropic import Anthropic
    client = Anthropic(api_key=api_key)
    tool = {"name": "submit_prompts", "description": "Submit the buyer-intent questions",
            "input_schema": PromptSet.model_json_schema()}
    payload = {
        "business": profile.model_dump(exclude={"proof_points", "differentiators", "unknowns", "analyzed_urls"}),
        "requested_count": count,
        "target_persona": persona[:180] or "Infer a plausible buyer from the profile",
        "target_market": market[:180] or "Only markets supported by the profile",
    }
    response = client.messages.create(
        model=model, max_tokens=8192, system=SYSTEM,
        tools=[tool], tool_choice={"type": "auto", "disable_parallel_tool_use": True},
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}])
    if response.stop_reason == "max_tokens":
        raise ValueError("Response was truncated. Try a smaller prompt count.")
    calls = [b for b in response.content
             if b.type == "tool_use" and b.name == "submit_prompts"]
    if len(calls) != 1:
        raise ValueError("Claude did not return a structured prompt set. Retry with fewer prompts.")
    return validate_prompt_set(PromptSet.model_validate(calls[0].input), profile, count)
