"""Verifiable buyer-language evidence, independent of AI-generated rationales."""
import re
from datetime import datetime, timezone
from urllib.parse import urlparse, urljoin
from urllib.robotparser import RobotFileParser
from pydantic import BaseModel, Field, HttpUrl
from crawler import fetch, normalize_url, CrawlError, USER_AGENT
from extractor import extract_page

class ResearchEvidence(BaseModel):
    source_url: HttpUrl
    quote: str = Field(min_length=12, max_length=900)
    source_type: str = Field(default="webpage", max_length=80)
    context: str = Field(default="", max_length=300)
    retrieved_at: str = ""
    verification: str = "unverified"

def normalize_quote(text):
    return re.sub(r"\\s+", " ", text).strip().casefold()

def verify_public_quote(url: str, quote: str) -> ResearchEvidence:
    """Fetch one user-selected public HTML URL, respect robots, verify literal quote."""
    url = normalize_url(url)
    origin = urlparse(url)
    robots = urljoin(url, "/robots.txt")
    try:
        _, _, rules = fetch(robots, allowed_host=origin.hostname)
    except CrawlError as exc:
        if str(exc) == "HTTP 404":
            rules = ""
        else:
            raise ValueError("Cannot verify robots rules: " + str(exc)) from exc
    parser = RobotFileParser()
    parser.parse(rules.splitlines())
    if not parser.can_fetch(USER_AGENT, url):
        raise ValueError("Source disallows automated access")
    final_url, content_type, html = fetch(url, allowed_host=origin.hostname)
    if "text/html" not in content_type.lower():
        raise ValueError("Source is not an HTML page")
    page = extract_page(final_url, html)
    haystack = " ".join([page["title"], page["description"], *page["headings"], page["text"]])
    if normalize_quote(quote) not in normalize_quote(haystack):
        raise ValueError("The exact quotation was not found on the retrieved page")
    return ResearchEvidence(source_url=final_url, quote=quote,
        retrieved_at=datetime.now(timezone.utc).isoformat(), verification="verified_live")

def evidence_payload(records):
    """Pass only verifiable records to AI; never relabel user claims as observed."""
    return [{"source_url":str(r.source_url), "quote":r.quote, "source_type":r.source_type,
             "context":r.context, "verification":r.verification} for r in records]
