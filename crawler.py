"""Bounded, robots-aware, public-web-only HTML crawler.

This module does not call an LLM. Network requests require a public DNS result.
"""
from collections import deque
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
import ipaddress
import socket
import httpx
from extractor import extract_page

USER_AGENT = "LassoPromptsResearchBot/0.1 (+https://attentionlasso.com)"
MAX_BYTES = 2_000_000
MAX_PAGES = 15
MAX_ATTEMPTS = 25

class CrawlError(ValueError):
    pass

def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        raise CrawlError("Enter a website URL.")
    if "://" not in value:
        value = "https://" + value
    p = urlparse(value)
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise CrawlError("Only public HTTP(S) websites are supported.")
    if p.port not in (None, 80, 443):
        raise CrawlError("Nonstandard ports are not allowed.")
    return urldefrag(value)[0]

def assert_public_url(url: str) -> None:
    p = urlparse(normalize_url(url))
    host = p.hostname
    if host in ("localhost",) or host.endswith(".localhost") or host.endswith(".local"):
        raise CrawlError("Local addresses are not allowed.")
    try:
        addresses = socket.getaddrinfo(host, p.port or (443 if p.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CrawlError("Website DNS lookup failed.") from exc
    if not addresses:
        raise CrawlError("No DNS addresses found.")
    for item in addresses:
        ip = ipaddress.ip_address(item[4][0])
        if not ip.is_global:
            raise CrawlError("Website resolves to a non-public IP address.")

def priority(url: str) -> int:
    path = urlparse(url).path.lower()
    if path in ("", "/"):
        return 0
    if any(x in path for x in ("service", "product", "solution", "industr")):
        return 1
    if any(x in path for x in ("about", "pricing", "contact", "work", "case-stud")):
        return 2
    if any(x in path for x in ("blog", "article", "news")):
        return 5
    return 3

def crawl(website: str, max_pages: int = MAX_PAGES) -> dict:
    start = normalize_url(website)
    assert_public_url(start)
    origin = urlparse(start).hostname
    queue = deque([(start, 0)])
    seen, pages, failures = set(), [], []
    attempts = 0
    max_pages = min(max(1, max_pages), MAX_PAGES)
    with httpx.Client(timeout=10, follow_redirects=False, headers={"User-Agent": USER_AGENT},
                      trust_env=False) as client:
        # A denied/unavailable robots file is handled conservatively.
        robots_url = urljoin(start, "/robots.txt")
        assert_public_url(robots_url)
        try:
            robots_resp = client.get(robots_url)
            parser = RobotFileParser()
            parser.parse(robots_resp.text.splitlines() if robots_resp.status_code == 200 else [])
            if robots_resp.status_code in (401, 403) or robots_resp.status_code >= 500:
                return {"pages": [], "failures": [{"url": start, "reason": "robots.txt unavailable or denied"}], "attempts": 0}
        except httpx.HTTPError:
            return {"pages": [], "failures": [{"url": start, "reason": "robots.txt could not be checked"}], "attempts": 0}
        while queue and len(pages) < max_pages and attempts < MAX_ATTEMPTS:
            queue = deque(sorted(queue, key=lambda entry: (priority(entry[0]), entry[1])))
            url, depth = queue.popleft()
            if url in seen:
                continue
            seen.add(url)
            if urlparse(url).hostname != origin or not parser.can_fetch(USER_AGENT, url):
                continue
            attempts += 1
            try:
                assert_public_url(url)
                # No redirects: prevents redirect-to-private-address requests.
                with client.stream("GET", url) as response:
                    if response.is_redirect:
                        failures.append({"url": url, "reason": "Redirect requires manual review"})
                        continue
                    response.raise_for_status()
                    if "text/html" not in response.headers.get("content-type", "").lower():
                        failures.append({"url": url, "reason": "Not an HTML page"})
                        continue
                    chunks, size = [], 0
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > MAX_BYTES:
                            raise CrawlError("HTML response exceeds 2 MB")
                        chunks.append(chunk)
                    html = b"".join(chunks).decode(response.encoding or "utf-8", errors="replace")
                page = extract_page(url, html)
                page["text"] = page["text"][:12000]
                pages.append(page)
                if depth < 2:
                    for link in page["links"]:
                        if urlparse(link).hostname == origin and link not in seen and len(queue) < 50:
                            queue.append((link, depth + 1))
            except (httpx.HTTPError, CrawlError, UnicodeError) as exc:
                failures.append({"url": url, "reason": str(exc)[:200]})
    return {"pages": pages, "failures": failures, "attempts": attempts}
