"""Bounded, no-key discovery via Bing RSS. Search snippets are NOT treated as evidence."""
import re
from urllib.parse import urlencode, urlparse, urljoin
from urllib.robotparser import RobotFileParser
from xml.etree import ElementTree as ET
from bs4 import BeautifulSoup
from crawler import fetch, CrawlError, USER_AGENT, normalize_url
from research_evidence import ResearchEvidence, verify_public_quote
from schemas import BusinessProfile

SEARCH_HOST = "www.bing.com"
MAX_QUERIES = 3
MAX_RESULTS_PER_QUERY = 5
MAX_PAGES = 10
QUESTION = re.compile(r"[^.!?\\n]{18,220}\\?", re.U)

def discovery_queries(profile: BusinessProfile, market=""):
    """Use verified service names, not model-created queries or invented buyers."""
    services = [s.name.strip() for s in profile.services if s.name.strip()]
    suffix = (" " + market.strip()[:60]) if market.strip() else ""
    return [f'"{service}" questions discussion{suffix}' for service in services[:MAX_QUERIES]]

def search_candidates(query):
    """Retrieve RSS search results; candidates are not source evidence."""
    robots_url = "https://" + SEARCH_HOST + "/robots.txt"
    try:
        _, _, robots = fetch(robots_url, allowed_host=SEARCH_HOST)
    except CrawlError as exc:
        if str(exc) == "HTTP 404":
            robots = ""
        else:
            raise ValueError("Search provider robots policy unavailable") from exc
    parser = RobotFileParser()
    parser.parse(robots.splitlines())
    url = "https://" + SEARCH_HOST + "/search?" + urlencode({"q":query,"format":"rss"})
    if not parser.can_fetch(USER_AGENT,url):
        raise ValueError("Search provider disallows automated RSS access")
    _, content_type, body = fetch(url, allowed_host=SEARCH_HOST)
    if "xml" not in content_type.lower() and not body.lstrip().startswith(("<?xml","<rss")):
        raise ValueError("Search provider did not return RSS")
    try:
        root = ET.fromstring(body)
    except ET.ParseError as exc:
        raise ValueError("Search provider returned invalid RSS") from exc
    candidates = []
    for item in root.findall(".//item")[:MAX_RESULTS_PER_QUERY]:
        link = (item.findtext("link") or "").strip()
        p = urlparse(link)
        if p.scheme == "https" and p.hostname and p.hostname != SEARCH_HOST and not p.username:
            candidates.append({"url":link,"title":item.findtext("title") or "", "query":query})
    return candidates

def extract_questions(url):
    """Read the source itself. Snippets, search titles and model output never count."""
    url = normalize_url(url)
    host = urlparse(url).hostname
    robots_url = urljoin(url,"/robots.txt")
    try:
        _, _, rules = fetch(robots_url, allowed_host=host)
    except CrawlError as exc:
        if str(exc) == "HTTP 404":
            rules = ""
        else:
            return []
    parser = RobotFileParser()
    parser.parse(rules.splitlines())
    if not parser.can_fetch(USER_AGENT,url):
        return []
    try:
        final_url, content_type, html = fetch(url, allowed_host=host)
    except CrawlError:
        return []
    if "text/html" not in content_type.lower():
        return []
    soup = BeautifulSoup(html,"html.parser")
    for tag in soup(["script","style","nav","footer","aside","noscript"]):
        tag.decompose()
    # Keep quotes as contiguous text fragments to support exact on-page verification.
    fragments = [node.get_text(" ",strip=True) for node in soup.select("h1,h2,h3,p,li")]
    result=[]
    for fragment in fragments[:300]:
        for match in QUESTION.finditer(fragment):
            quote = re.sub(r"\\s+"," ",match.group(0)).strip()
            if len(quote) >= 20 and quote not in result:
                result.append(quote)
    return [(final_url,q) for q in result[:5]]

def rank_evidence(records, profile):
    """Transparent heuristic, not demand volume: service overlap + question specificity."""
    keywords = set()
    for service in profile.services:
        keywords.update(w.lower() for w in re.findall(r"[a-zA-Z]{4,}",service.name))
    def score(record):
        words = set(re.findall(r"[a-zA-Z]{4,}",record.quote.lower()))
        overlap = min(3,len(words & keywords))
        question = int(record.quote.rstrip().endswith("?"))
        specific = int(7 <= len(record.quote.split()) <= 30)
        return overlap * 2 + question + specific
    return sorted(records,key=lambda x:(-score(x),str(x.source_url),x.quote))

def discover_evidence(profile: BusinessProfile, market=""):
    """Bounded discovery, fail closed, with explicit failure reports."""
    queries = discovery_queries(profile,market)
    candidates, failures = [], []
    for query in queries:
        try:
            candidates.extend(search_candidates(query))
        except (ValueError,CrawlError) as exc:
            failures.append({"query":query,"reason":str(exc)[:180]})
    seen_urls, records, seen_quotes = set(), [], set()
    for candidate in candidates:
        url = candidate["url"]
        if url in seen_urls or len(seen_urls) >= MAX_PAGES:
            continue
        seen_urls.add(url)
        try:
            questions = extract_questions(url)
            for final_url, quote in questions:
                key = (final_url,quote.casefold())
                if key in seen_quotes:
                    continue
                # Exact quote was extracted from the live page. Mark as verified only
                # after rechecking via the canonical verifier, including robots.
                try:
                    record = verify_public_quote(final_url,quote)
                except (ValueError,CrawlError):
                    continue
                record.source_type = "discovered webpage"
                record.context = "Found via search: " + candidate["query"][:180]
                seen_quotes.add(key)
                records.append(record)
        except (ValueError,CrawlError) as exc:
            failures.append({"url":url,"reason":str(exc)[:180]})
    return {"records":rank_evidence(records,profile),"queries":queries,
            "candidates_checked":len(seen_urls),"failures":failures,
            "note":"Scores reflect wording and service relevance, not search volume or buyer identity."}
