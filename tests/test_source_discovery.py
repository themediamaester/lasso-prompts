from unittest.mock import patch
from schemas import BusinessProfile, Service
from research_evidence import ResearchEvidence
from source_discovery import discovery_queries, search_candidates, extract_questions, rank_evidence, discover_evidence

def profile():
    return BusinessProfile(name="Test",website="https://example.com",
        services=[Service(name="AI Search Optimization",source_url="https://example.com",evidence="AI search")])

def test_queries_bounded():
    assert len(discovery_queries(profile())) == 1

def test_rss_parsing_does_not_make_snippet_evidence():
    rss='<rss><channel><item><title>Best AI services?</title><link>https://example.org/post</link><description>Snippet only</description></item></channel></rss>'
    with patch("source_discovery.fetch",side_effect=[
        ("https://www.bing.com/robots.txt","text/plain","User-agent: *\\nAllow: /"),
        ("https://www.bing.com/search","application/rss+xml",rss)]):
        candidates=search_candidates("AI search")
    assert candidates[0]["url"]=="https://example.org/post"
    assert "quote" not in candidates[0]

def test_discovery_rejects_search_only_candidates():
    with patch("source_discovery.search_candidates",return_value=[{"url":"https://example.org/post","query":"q"}]), \\
         patch("source_discovery.extract_questions",return_value=[]):
        result=discover_evidence(profile())
    assert result["records"]==[]

def test_discovery_only_keeps_verified_quote():
    record=ResearchEvidence(source_url="https://example.org/post",quote="How can I appear in AI search results?",
                            verification="verified_live")
    with patch("source_discovery.search_candidates",return_value=[{"url":"https://example.org/post","query":"q"}]), \\
         patch("source_discovery.extract_questions",return_value=[("https://example.org/post",record.quote)]), \\
         patch("source_discovery.verify_public_quote",return_value=record):
        result=discover_evidence(profile())
    assert len(result["records"])==1
    assert result["records"][0].verification=="verified_live"

def test_ranking_not_fake_volume():
    a=ResearchEvidence(source_url="https://example.org/a",quote="How can AI search optimization help me?",verification="verified_live")
    b=ResearchEvidence(source_url="https://example.org/b",quote="Why is marketing difficult?",verification="verified_live")
    assert rank_evidence([b,a],profile())[0]==a
