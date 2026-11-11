"""Development-only Streamlit entrypoint; main app.py remains unchanged."""
import json
import os
import streamlit as st
from crawler import crawl, CrawlError
from analyzer import analyze_business, prepare_evidence

st.set_page_config(page_title="Lasso Prompts · Phase 1", layout="wide")
st.title("Lasso Prompts · Business Intelligence")
st.caption("Development preview. No competitor research or prompt generation yet.")
website = st.text_input("Business website", value="https://attentionlasso.com")
if st.button("Discover website pages"):
    try:
        with st.spinner("Crawling publicly accessible pages..."):
            st.session_state.phase1_crawl = crawl(website)
            st.session_state.pop("phase1_profile", None)
    except (CrawlError, ValueError) as exc:
        st.error(str(exc))
if "phase1_crawl" in st.session_state:
    result = st.session_state.phase1_crawl
    st.write("Pages fetched:", len(result["pages"]), "· Attempts:", result["attempts"])
    for failure in result["failures"]:
        st.warning(f'{failure["url"]}: {failure["reason"]}')
    pages = result["pages"]
    if pages:
        labels = [f'{p["title"] or p["url"]} ({len(p["text"])} chars)' for p in pages]
        selected = st.multiselect("Pages to include in analysis", options=list(range(len(pages))),
                                  default=list(range(len(pages))), format_func=lambda i: labels[i])
        for i in selected:
            with st.expander(labels[i]):
                st.write(pages[i]["url"])
                st.text(pages[i]["text"][:3000])
        evidence = prepare_evidence([pages[i] for i in selected])
        st.caption(f"Prepared {len(evidence)} pages and {sum(len(p['text']) for p in evidence):,} text characters for analysis.")
        api_key = st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
        if st.button("Analyze selected pages with Claude", disabled=not bool(api_key) or not evidence):
            try:
                with st.spinner("Analyzing source evidence..."):
                    st.session_state.phase1_profile = analyze_business(
                        [pages[i] for i in selected], website, api_key)
            except Exception as exc:
                st.error(f"Analysis failed. Crawl results are preserved. {type(exc).__name__}: {str(exc)[:180]}")
    if "phase1_profile" in st.session_state:
        profile = st.session_state.phase1_profile
        st.subheader("Business profile · Review before approving")
        st.info("This is an AI-produced draft. Review all fields and source excerpts before using it.")
        edited = st.text_area("Editable profile JSON", value=profile.model_dump_json(indent=2), height=500)
        try:
            parsed = json.loads(edited)
            st.download_button("Export reviewed JSON", data=json.dumps(parsed, indent=2),
                               file_name="lasso-business-profile.json", mime="application/json")
        except json.JSONDecodeError:
            st.warning("Correct JSON formatting before exporting.")
