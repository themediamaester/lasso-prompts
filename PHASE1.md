# Lasso Prompts 2.0 — Phase 1 development

Development branch only. The production Streamlit app on main is unchanged.

## First milestone: deterministic crawler and extractor
- Public HTTP(S) URL normalization and DNS validation
- robots.txt check, no automatic redirects
- Bounded HTML fetching (15 pages, 25 attempts, 2 MB/page)
- Basic page prioritization and extraction
- Unit tests for extraction and URL safety

## Not yet implemented
Sitemap discovery, redirect-safe fetching, DNS pinning to prevent DNS rebinding, structured data extraction, editable business profiles, Anthropic analysis, persistence and export. **Do not expose this crawler to untrusted public users until DNS pinning and remaining security tests are complete.**

## Local test
Install requirements-dev.txt, then run `python -m pytest tests -q`.

No Anthropic calls are made by this milestone.
