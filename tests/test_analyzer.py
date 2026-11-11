import json
import pytest
from analyzer import prepare_evidence, parse_profile

PAGE = {"url":"https://example.com/services", "title":"SEO Services",
        "description":"Search visibility", "headings":["SEO Services"],
        "text":"We provide technical SEO services to small businesses. " * 5,
        "sufficient":True}

def test_prepared_evidence_is_bounded():
    result = prepare_evidence([PAGE], max_chars=500)
    assert len(result) == 1
    assert len(result[0]["text"]) <= 300

def test_rejects_fabricated_evidence():
    obj = {"name":"Example","website":"https://example.com","analyzed_urls":[PAGE["url"]],
           "services":[{"name":"SEO","source_url":PAGE["url"],"evidence":"We offer eye tracking software","confidence":"high"}]}
    with pytest.raises(ValueError, match="evidence"):
        parse_profile(json.dumps(obj), [PAGE])

def test_accepts_supported_evidence():
    obj = {"name":"Example","website":"https://example.com","analyzed_urls":[PAGE["url"]],
           "services":[{"name":"SEO","source_url":PAGE["url"],"evidence":"technical SEO services","confidence":"high"}]}
    result = parse_profile(json.dumps(obj), [PAGE])
    assert result.services[0].name == "SEO"

def test_rejects_unseen_source():
    obj = {"name":"Example","website":"https://example.com",
           "services":[{"name":"SEO","source_url":"https://other.com","evidence":"SEO","confidence":"high"}]}
    with pytest.raises(ValueError, match="not analyzed"):
        parse_profile(json.dumps(obj), [PAGE])
