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
                assert kwargs["model"] == "claude-sonnet-5-5"
                assert "search engine optimization" in kwargs["messages"][0]["content"]
                return type("Response", (), {"content": [type("Text", (), {"type": "text", "text": json.dumps(response)})()]})()
    with patch("anthropic.Anthropic", return_value=FakeClient()):
        profile = analyze_business(pages, "https://example.com", "fake-test-key")
    assert {s.name for s in profile.services} == {"Search Engine Optimization", "Marketing Automation"}
