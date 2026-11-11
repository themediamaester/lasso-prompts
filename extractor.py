"""Deterministic HTML extraction for business research."""
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re

SKIP_TAGS = ("script", "style", "noscript", "svg", "footer", "nav", "aside", "form")

def extract_page(url: str, html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    description = ""
    meta = soup.find("meta", attrs={"name": re.compile("^description$", re.I)})
    if meta:
        description = meta.get("content", "")
    headings = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
    links = []
    for a in soup.find_all("a", href=True):
        target = urljoin(url, a["href"]).split("#", 1)[0]
        if urlparse(target).scheme in ("http", "https"):
            links.append(target)
    canonical = soup.find("link", rel="canonical")
    canonical_url = urljoin(url, canonical["href"]) if canonical and canonical.get("href") else url
    for tag in soup.find_all(SKIP_TAGS):
        tag.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True)).strip()
    return {"url": url, "canonical_url": canonical_url, "title": title,
            "description": description, "headings": headings,
            "text": text, "links": list(dict.fromkeys(links)),
            "sufficient": len(text) >= 150}
