"""Development-only Streamlit entrypoint. Production app.py remains unchanged."""
import json
import os
import streamlit as st
from pydantic import ValidationError
from crawler import crawl, CrawlError
from analyzer import analyze_business, prepare_evidence, validate_profile_evidence
from schemas import BusinessProfile

st.set_page_config(page_title="Lasso Prompts · Phase 1", layout="wide")
st.title("Lasso Prompts · Business Intelligence")
st.caption("Development preview: website evidence first. No competitors or buyer prompts yet.")

website = st.text_input("Business website", value="https://attentionlasso.com")
if st.button("Discover website pages"):
    try:
        with st.spinner("Crawling public website pages..."):
            st.session_state.phase1_crawl = crawl(website)
            st.session_state.phase1_site = website
            st.session_state.pop("phase1_profile", None)
            st.session_state.pop("phase1_edit", None)
    except (CrawlError, ValueError) as exc:
        st.error(str(exc))

if "phase1_crawl" in st.session_state:
    result = st.session_state.phase1_crawl
    st.write(f'{len(result["pages"])} pages fetched · {result["attempts"]} page requests')
    for failure in result["failures"]:
        st.warning(f'{failure["url"]}: {failure["reason"]}')
    pages = result["pages"]
    if pages:
        labels = [f'{p["title"] or p["url"]} ({len(p["text"])} characters)' for p in pages]
        selected = st.multiselect(
            "Select evidence pages", options=list(range(len(pages))),
            default=list(range(len(pages))), format_func=lambda i: labels[i])
        for i in selected:
            with st.expander(labels[i]):
                st.write(pages[i]["url"])
                st.text(pages[i]["text"][:3000])
        evidence = prepare_evidence([pages[i] for i in selected])
        characters = sum(len(p["text"]) for p in evidence)
        st.caption(f"{len(evidence)} selected pages · {characters:,} characters of evidence")
        st.info("Crawling is free. Clicking Analyze makes an Anthropic API request using existing credits. "
                "The exact charge depends on model usage. No background AI requests are made.")
        consent = st.checkbox("I approve one Anthropic analysis request using my existing API credits.")
        api_key = st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
        if not api_key:
            st.warning("Configure ANTHROPIC_API_KEY to enable analysis.")
        if st.button("Analyze selected pages", disabled=not (consent and api_key and evidence)):
            try:
                with st.spinner("Analyzing the retrieved evidence..."):
                    profile = analyze_business([pages[i] for i in selected],
                                               st.session_state.phase1_site, api_key)
                    st.session_state.phase1_evidence = prepare_evidence([pages[i] for i in selected])
                    st.session_state.phase1_profile = profile
                    st.session_state.phase1_edit = profile.model_dump_json(indent=2)
            except Exception as exc:
                st.error(f"Analysis failed; the crawl is preserved. {type(exc).__name__}. "
                         "Review the developer logs for details.")
    if "phase1_profile" in st.session_state:
        st.subheader("Review and correct business profile")
        st.info("Source evidence is checked in the generated draft. Human edits must be reviewed before export.")
        st.text_area("Editable JSON", height=480, key="phase1_edit")
        try:
            reviewed = BusinessProfile.model_validate_json(st.session_state.phase1_edit)
            validate_profile_evidence(reviewed, st.session_state.phase1_evidence)
            st.success("Profile structure and source quotations are valid. Review interpretations before using it.")
            st.download_button("Export reviewed business profile",
                               data=reviewed.model_dump_json(indent=2),
                               file_name="lasso-business-profile.json", mime="application/json")
        except (ValidationError, ValueError) as exc:
            st.error("Profile structure or cited evidence is invalid: " + str(exc)[:220])
