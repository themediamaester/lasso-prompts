from unittest.mock import patch
import pytest
from schemas import BusinessProfile, Service
from research_evidence import ResearchEvidence, verify_public_quote
from prompt_generator import SourcedPrompt, SourcedPromptSet, validate_sourced_prompts

URL = "https://example.org/discussion"
QUOTE = "How do I get my business mentioned by AI assistants?"

def evidence():
    return ResearchEvidence(source_url=URL, quote=QUOTE, verification="verified_live")

def profile():
    return BusinessProfile(name="Example", website="https://example.com",
        services=[Service(name="AI Search Optimization",source_url="https://example.com",evidence="AI search")])

def sourced(**changes):
    base = dict(prompt=QUOTE, intent="problem", stage="awareness",
        service="AI Search Optimization", persona="Business owner",
        rationale="Asks about AI visibility", source_url=URL, source_quote=QUOTE,
        provenance="observed_question", transformation="Reproduced the question verbatim")
    base.update(changes)
    return SourcedPrompt(**base)

def test_verified_public_quote_checks_robots_and_page():
    with patch("research_evidence.fetch", side_effect=[
        ("https://example.org/robots.txt","text/plain","User-agent: *\\nAllow: /"),
        (URL,"text/html",f"<html><body><main>{QUOTE} " + "Additional context. "*20 + "</main></body></html>")
    ]):
        result = verify_public_quote(URL, QUOTE)
    assert result.verification == "verified_live"

def test_quote_must_be_on_page():
    with patch("research_evidence.fetch", side_effect=[
        ("https://example.org/robots.txt","text/plain","User-agent: *\\nAllow: /"),
        (URL,"text/html","<html><body><main>Some unrelated information.</main></body></html>")
    ]):
        with pytest.raises(ValueError, match="not found"):
            verify_public_quote(URL, QUOTE)

def test_unverified_source_is_rejected():
    record = evidence()
    record.verification = "unverified"
    with pytest.raises(ValueError, match="not been verified"):
        validate_sourced_prompts(SourcedPromptSet(prompts=[sourced()]),profile(),[record],10)

def test_fabricated_quote_is_rejected():
    with pytest.raises(ValueError, match="not been verified"):
        validate_sourced_prompts(SourcedPromptSet(prompts=[sourced(source_quote="Made up quote")]),profile(),[evidence()],10)

def test_observed_must_match_verbatim():
    with pytest.raises(ValueError, match="reproduce"):
        validate_sourced_prompts(SourcedPromptSet(prompts=[sourced(prompt="Who sells AI visibility services?")]),profile(),[evidence()],10)

def test_derived_question_can_rephrase():
    item=sourced(prompt="Which agencies can help my business appear in AI answers?",
        provenance="evidence_derived", transformation="Converted an owner question to provider search")
    assert validate_sourced_prompts(SourcedPromptSet(prompts=[item]),profile(),[evidence()],10)
