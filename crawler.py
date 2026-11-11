"""Bounded public website crawler. No AI calls or paid services."""
from collections import deque
import ipaddress
import re
import socket
from urllib.parse import urlparse, urljoin, urldefrag
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree
import urllib3
from extractor import extract_page

USER_AGENT = "LassoPromptsResearchBot/0.2 (+https://attentionlasso.com)"
MAX_PAGES = 15
MAX_ATTEMPTS = 25
MAX_BYTES = 2_000_000
MAX_CANDIDATES = 50
MAX_REDIRECTS = 3

class CrawlError(ValueError):
    pass

def normalize_url(value):
    value = value.strip()
    if not value:
        raise CrawlError("Enter a website URL")
    if "://" not in value:
        value = "https://" + value
    p = urlparse(value)
    try:
        port = p.port
    except ValueError as exc:
        raise CrawlError("Invalid port") from exc
    if p.scheme not in ("http", "https") or not p.hostname or p.username or p.password:
        raise CrawlError("Only public HTTP(S) URLs are allowed")
    if port not in (None, 80, 443):
        raise CrawlError("Nonstandard ports are not allowed")
    return urldefrag(value)[0]

def resolve_public_ip(host):
    if host == "localhost" or host.endswith((".localhost", ".local")):
        raise CrawlError("Local hosts are not allowed")
    try:
        addresses = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise CrawlError("DNS resolution failed") from exc
    ips = [ipaddress.ip_address(entry[4][0]) for entry in addresses]
    if not ips or not all(ip.is_global for ip in ips):
        raise CrawlError("Non-public DNS address rejected")
    return str(ips[0])

def assert_public_url(url):
    p = urlparse(normalize_url(url))
    resolve_public_ip(p.hostname)

def priority(url):
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

def fetch(url, redirects=MAX_REDIRECTS, allowed_host=None):
    """Pin the TCP connection to a validated public IP while verifying TLS for the hostname."""
    current = normalize_url(url)
    for _ in range(redirects + 1):
        p = urlparse(current)
        if allowed_host and p.hostname != allowed_host:
            raise CrawlError("Redirect outside the approved domain")
        ip = resolve_public_ip(p.hostname)
        port = p.port or (443 if p.scheme == "https" else 80)
        host_header = p.hostname + ((":" + str(port)) if p.port else "")
        pool_cls = urllib3.HTTPSConnectionPool if p.scheme == "https" else urllib3.HTTPConnectionPool
        opts = {"timeout": urllib3.Timeout(connect=5, read=10), "retries": False, "maxsize": 1}
        if p.scheme == "https":
            opts.update(server_hostname=p.hostname, assert_hostname=p.hostname, cert_reqs="CERT_REQUIRED")
        pool = pool_cls(ip, port=port, **opts)
        try:
            path = p.path or "/"
            if p.query:
                path += "?" + p.query
            response = pool.request("GET", path, headers={"Host": host_header, "User-Agent": USER_AGENT,
                "Accept": "text/html, application/xml, text/xml, */*"}, redirect=False,
                preload_content=False)
            try:
                if response.status in (301, 302, 303, 307, 308):
                    location = response.headers.get("Location")
                    if not location:
                        raise CrawlError("Redirect missing location")
                    current = normalize_url(urljoin(current, location))
                    continue
                if response.status >= 400:
                    raise CrawlError("HTTP " + str(response.status))
                length = response.headers.get("Content-Length")
                if length and int(length) > MAX_BYTES:
                    raise CrawlError("Response too large")
                chunks, size = [], 0
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > MAX_BYTES:
                        raise CrawlError("Response too large")
                    chunks.append(chunk)
                content = b"".join(chunks)
                return current, response.headers.get("Content-Type", ""), content.decode("utf-8", errors="replace")
            finally:
                response.release_conn()
        except (urllib3.exceptions.HTTPError, OSError) as exc:
            raise CrawlError("Network request failed: " + str(exc)[:120]) from exc
        finally:
            pool.close()
    raise CrawlError("Too many redirects")

def sitemap_links(xml_text):
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    return [el.text.strip() for el in root.iter()
            if el.tag.split("}")[-1] == "loc" and el.text and el.text.strip()]

def crawl(website, max_pages=MAX_PAGES):
    start = normalize_url(website)
    assert_public_url(start)
    origin = urlparse(start).hostname
    pages, failures, seen = [], [], set()
    attempts = 0
    max_pages = min(max(1, int(max_pages)), MAX_PAGES)
    robots_url = urljoin(start, "/robots.txt")
    try:
        _, _, robots_text = fetch(robots_url, allowed_host=origin)
    except CrawlError as exc:
        # A missing robots.txt means no stated rules; denial/network failure fails closed.
        if str(exc) == "HTTP 404":
            robots_text = ""
        else:
            return {"pages": [], "failures": [{"url": robots_url, "reason": str(exc)}],
                    "attempts": 0, "status": "robots_unavailable"}
    parser = RobotFileParser()
    parser.parse(robots_text.splitlines())
    sitemap_urls = re.findall(r"(?im)^\s*Sitemap:\s*(\S+)", robots_text)
    sitemap_urls.append(urljoin(start, "/sitemap.xml"))
    candidates = [start]
    checked_sitemaps = set()
    for sitemap in sitemap_urls[:3]:
        if sitemap in checked_sitemaps:
            continue
        checked_sitemaps.add(sitemap)
        if urlparse(sitemap).hostname != origin or not parser.can_fetch(USER_AGENT, sitemap):
            continue
        try:
            _, content_type, xml = fetch(sitemap, allowed_host=origin)
            if "xml" not in content_type and not xml.lstrip().startswith("<?xml"):
                continue
            for link in sitemap_links(xml)[:MAX_CANDIDATES]:
                if urlparse(link).hostname != origin:
                    continue
                if link.lower().split("?")[0].endswith(".xml") and link not in checked_sitemaps and len(checked_sitemaps) < 8:
                    checked_sitemaps.add(link)
                    try:
                        _, _, nested_xml = fetch(link, allowed_host=origin)
                        for page_link in sitemap_links(nested_xml)[:MAX_CANDIDATES]:
                            if urlparse(page_link).hostname == origin and page_link not in candidates:
                                candidates.append(page_link)
                    except CrawlError:
                        pass
                elif link not in candidates:
                    candidates.append(link)
        except CrawlError:
            pass
    # Reserve the first crawl slots for high-value business pages, not articles.
    selected = sorted(candidates, key=priority)[:MAX_CANDIDATES]
    queue = deque((url, 0) for url in selected)
    while queue and len(pages) < max_pages and attempts < MAX_ATTEMPTS:
        queue = deque(sorted(queue, key=lambda item: (priority(item[0]), item[1])))
        url, depth = queue.popleft()
        if url in seen:
            continue
        seen.add(url)
        if urlparse(url).hostname != origin or not parser.can_fetch(USER_AGENT, url):
            continue
        attempts += 1
        try:
            final_url, content_type, html = fetch(url, allowed_host=origin)
            if urlparse(final_url).hostname != origin:
                raise CrawlError("Redirected outside original domain")
            if "text/html" not in content_type.lower():
                raise CrawlError("Not HTML content")
            page = extract_page(final_url, html)
            page["text"] = page["text"][:12000]
            pages.append(page)
            if depth < 2:
                for link in page["links"]:
                    if urlparse(link).hostname == origin and link not in seen and len(queue) < MAX_CANDIDATES:
                        queue.append((link, depth + 1))
        except CrawlError as exc:
            failures.append({"url": url, "reason": str(exc)})
    return {"pages": pages, "failures": failures, "attempts": attempts,
            "status": "complete" if pages else "no_pages"}
