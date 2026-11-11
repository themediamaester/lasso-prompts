import pytest
from crawler import normalize_url, assert_public_url, CrawlError, priority

def test_normalization():
    assert normalize_url("example.com") == "https://example.com"

@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://user:pass@example.com", "http://example.com:8080"])
def test_rejects_unsafe_urls(url):
    with pytest.raises(CrawlError):
        normalize_url(url)

def test_rejects_loopback_without_network():
    with pytest.raises(CrawlError):
        assert_public_url("http://127.0.0.1")

def test_service_pages_first():
    assert priority("https://example.com/services") < priority("https://example.com/blog/story")
