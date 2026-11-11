from crawler import sitemap_links, priority, normalize_url, CrawlError
import pytest

def test_sitemap_urls():
    xml = '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://example.com/services</loc></url></urlset>'
    assert sitemap_links(xml) == ["https://example.com/services"]

def test_sitemap_bad_xml():
    assert sitemap_links("<broken") == []

def test_prioritization():
    assert priority("https://example.com/services/seo") < priority("https://example.com/blog/post")

@pytest.mark.parametrize("value", ["http://localhost", "ftp://example.com", "https://example.com:9000"])
def test_invalid_inputs(value):
    if "localhost" in value:
        from crawler import assert_public_url
        with pytest.raises(CrawlError):
            assert_public_url(value)
    else:
        with pytest.raises(CrawlError):
            normalize_url(value)
