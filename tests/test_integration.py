"""End-to-end offline integration test; Anthropic is not called."""
import json
from unittest.mock import patch
from analyzer import analyze_business

def test_business_analysis_with_mocked_anthropic():
    pages = [{
        "url": "https://example.com/services",
        "title": "Example Marketing Services",
        "description": "SEO and automation",
        "headings": ["Search Engine Optimization", "Marketing Automation"],
        "text": "We provide search engine optimization and marketing automation for businesses. " * 6,
        "sufficient": True,
    }]
    response = {
        "name": "Example", "website": "https://example.com",
        "description": "Marketing services", "business_type": "Marketing services",
        "services": [
            {"name": "Search Engine Optimization", "description": "SEO",
             "source_url": pages[0]["url"], "evidence": "search engine optimization",
             "confidence": "high"},
            {"name": "Marketing Automation", "description": "Automation",
             "source_url": pages[0]["url"], "evidence": "marketing automation",
             "confidence": "high"}
        ],
        "analyzed_urls": [pages[0]["url"]]
    }
    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                assert kwargs["model"] == "claude-sonnet-5-5"\n                assert kwargs["tool_choice"]["name"] == "submit_business_profile"
                assert "search engine optimization" in kwargs["messages"][0]["content"]
                return type("Response", (), {"stop_reason": "tool_use", "content": [type("Tool", (), {"type": "tool_use", "name": "submit_business_profile", "input": response})()]})()
    with patch("anthropic.Anthropic", return_value=FakeClient()):
        profile = analyze_business(pages, "https://example.com", "fake-test-key")
    assert {s.name for s in profile.services} == {"Search Engine Optimization", "Marketing Automation"}

def test_truncated_tool_response_reports_actionable_error():
    pages = [{"url":"https://example.com","title":"Example","description":"",
              "headings":[],"text":"We provide SEO services. " * 10,"sufficient":True}]
    class FakeClient:
        class messages:
            @staticmethod
            def create(**kwargs):
                return type("Response", (), {"stop_reason": "max_tokens", "content": []})()
    with patch("anthropic.Anthropic", return_value=FakeClient()):
        import pytest
        with pytest.raises(ValueError, match="output limit"):
            analyze_business(pages, "https://example.com", "fake-test-key")
