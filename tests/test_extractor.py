from extractor import extract_page

def test_extracts_business_content_and_ignores_navigation():
    html = "<html><head><title>Example</title><meta name='description' content='A service'></head><body><nav>Navigation</nav><main><h1>Consulting</h1><p>" + ("We help companies grow. " * 12) + "</p></main></body></html>"
    result = extract_page("https://example.com/", html)
    assert result["title"] == "Example"
    assert result["description"] == "A service"
    assert "Consulting" in result["headings"]
    assert "Navigation" not in result["text"]
    assert result["sufficient"]
