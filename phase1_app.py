"""Development-only Streamlit entrypoint. Production app.py remains unchanged."""
import json
import os
import streamlit as st
from pydantic import ValidationError
from crawler import crawl, CrawlError
from analyzer import analyze_business, prepare_evidence, validate_profile_evidence
from schemas import BusinessProfile
from prompt_generator import generate_prompts, PromptSet, validate_prompt_set, generate_researched_prompts, validate_sourced_prompts, SourcedPromptSet
from research_evidence import verify_public_quote, ResearchEvidence
import csv
import io

st.set_page_config(page_title="Lasso Prompts · Phase 1", layout="wide")
st.title("Lasso Prompts · Buyer-intent prompts")
st.caption("Development preview · build buyer-prompts-v1 · research → review → prompts.")

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
                st.error(f"Analysis failed; crawl preserved. {type(exc).__name__}: {str(exc)[:300]}")
                st.caption("Build: structured-profile-v2. If this label is missing, your app is running older code.")
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

st.divider()
st.header("AI prompt brainstorming (unverified)")
st.write("Use the business profile you just created, or upload an exported JSON profile. No recrawl required.")
uploaded = st.file_uploader("Import reviewed business profile (JSON)", type=["json"])
prompt_profile = None
if uploaded is not None:
    try:
        prompt_profile = BusinessProfile.model_validate_json(uploaded.getvalue())
    except (ValidationError, ValueError) as exc:
        st.error("Uploaded file is not a valid business profile: " + str(exc)[:250])
elif "phase1_profile" in st.session_state:
    try:
        prompt_profile = BusinessProfile.model_validate_json(st.session_state.phase1_edit)
        validate_profile_evidence(prompt_profile, st.session_state.phase1_evidence)
    except (ValidationError, ValueError):
        st.warning("Correct the business profile above or upload an exported JSON file.")
if prompt_profile is not None:
    st.success(f"{prompt_profile.name} · {len(prompt_profile.services)} verified service entries loaded")
    with st.expander("Services included in the prompt research"):
        st.write([s.name for s in prompt_profile.services])
    persona = st.text_input("Target buyer (optional)", placeholder="e.g. Marketing manager at a growing B2B company")
    market = st.text_input("Target market (optional)", placeholder="e.g. Kenya")
    count = st.slider("Number of prompts", min_value=5, max_value=40, value=20, step=5)
    st.info("These are research hypotheses, not measured search queries or AI visibility results. "
            "Generation makes one new Anthropic API request and uses existing credits.")
    prompt_consent = st.checkbox("I approve one paid Anthropic request to generate buyer-intent prompts.")
    try:
        prompt_key = st.secrets.get("ANTHROPIC_API_KEY", os.getenv("ANTHROPIC_API_KEY", ""))
    except Exception:
        prompt_key = os.getenv("ANTHROPIC_API_KEY", "")
    if st.button("Generate buyer-intent prompts", disabled=not (prompt_consent and prompt_key)):
        try:
            with st.spinner("Generating prompts grounded in your business profile..."):
                generated = generate_prompts(prompt_profile, prompt_key, count=count, persona=persona, market=market)
            st.session_state.prompt_set = generated
            st.session_state.prompt_profile_name = prompt_profile.name
        except Exception as exc:
            st.error(f"Prompt generation failed: {type(exc).__name__}: {str(exc)[:350]}")
    if "prompt_set" in st.session_state and st.session_state.get("prompt_profile_name") == prompt_profile.name:
        st.subheader("Review, edit and export")
        st.caption("Edit questions and labels below. The list is not a live AI visibility measurement.")
        edited = st.data_editor(
            [p.model_dump() for p in st.session_state.prompt_set.prompts],
            num_rows="dynamic", hide_index=True, use_container_width=True,
            column_config={
                "intent": st.column_config.SelectboxColumn("Intent", options=["problem","solution","provider","comparison","decision"]),
                "stage": st.column_config.SelectboxColumn("Stage", options=["awareness","consideration","decision"]),
                "service": st.column_config.SelectboxColumn("Service", options=[s.name for s in prompt_profile.services]),
            },
            key="prompt_editor")
        try:
            reviewed_set = PromptSet.model_validate({"prompts": edited})
            validate_prompt_set(reviewed_set, prompt_profile, max(40, len(reviewed_set.prompts)))
            data = [p.model_dump() for p in reviewed_set.prompts]
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=["prompt","intent","stage","service","persona","rationale"])
            writer.writeheader()
            writer.writerows(data)
            left, right = st.columns(2)
            left.download_button("Download CSV", output.getvalue(), "lasso-buyer-prompts.csv", "text/csv")
            right.download_button("Download JSON", reviewed_set.model_dump_json(indent=2),
                                  "lasso-buyer-prompts.json", "application/json")
        except (ValidationError, ValueError) as exc:
            st.warning("Fix invalid or duplicate prompt rows before exporting: " + str(exc)[:350])

st.divider()
st.header("Research-backed buyer prompts")
st.write("Supply a public page and an exact quote. Lasso verifies the quote exists before generating source-linked questions. This does not establish search volume or prove the author is a buyer.")
if "research_quotes" not in st.session_state:
    st.session_state.research_quotes = []
with st.form("research_source_form"):
    source_url = st.text_input("Public source URL", placeholder="https://example.org/discussion")
    source_quote = st.text_area("Exact question or relevant excerpt from that page", height=110)
    source_type = st.selectbox("Source type", ["public discussion", "review", "FAQ", "article", "webpage", "other"])
    submitted = st.form_submit_button("Verify and add source")
if submitted:
    try:
        with st.spinner("Checking source access and exact quotation..."):
            record = verify_public_quote(source_url, source_quote)
            record.source_type = source_type
            if not any(str(e.source_url) == str(record.source_url) and e.quote == record.quote
                       for e in st.session_state.research_quotes):
                st.session_state.research_quotes.append(record)
                st.success("Source quotation verified and added")
            else:
                st.info("This source quotation is already in the research set")
    except (ValueError, Exception) as exc:
        st.error(f"Could not verify source: {str(exc)[:280]}")
if st.session_state.research_quotes:
    st.subheader(f"Verified source quotations ({len(st.session_state.research_quotes)})")
    for i, record in enumerate(st.session_state.research_quotes):
        with st.expander(f"{i+1}. {record.source_type}: {str(record.source_url)}"):
            st.write(record.quote)
            st.caption(f"Verification: {record.verification} · {record.retrieved_at}")
            if st.button("Remove source", key=f"remove_source_{i}"):
                st.session_state.research_quotes.pop(i)
                st.rerun()
    st.download_button("Export research evidence (JSON)",
                       json.dumps([e.model_dump(mode="json") for e in st.session_state.research_quotes],indent=2),
                       "lasso-research-evidence.json", "application/json")
if prompt_profile is not None and st.session_state.research_quotes:
    researched_count = st.slider("Maximum researched prompts", 1, 20, 10)
    st.caption("A verified quotation is evidence that wording appeared on a page, not proof of customer demand.")
    research_consent = st.checkbox("I approve one Anthropic request for source-linked prompt generation.")
    if st.button("Generate sourced prompts", disabled=not (research_consent and prompt_key)):
        try:
            with st.spinner("Generating traceable questions..."):
                st.session_state.sourced_set = generate_researched_prompts(
                    prompt_profile, st.session_state.research_quotes, prompt_key, count=researched_count)
                st.session_state.sourced_profile_name = prompt_profile.name
        except Exception as exc:
            st.error(f"Research generation failed: {type(exc).__name__}: {str(exc)[:300]}")
    if "sourced_set" in st.session_state and st.session_state.get("sourced_profile_name") == prompt_profile.name:
        st.subheader("Source-linked prompt library")
        for i, item in enumerate(st.session_state.sourced_set.prompts):
            with st.expander(f"{i+1}. {item.prompt}", expanded=i==0):
                st.write(f"**Source:** {item.source_url}")
                st.write(f"**Original wording:** {item.source_quote}")
                st.write(f"**Classification:** {item.provenance} · {item.intent} · {item.stage}")
                st.write(f"**Derivation:** {item.transformation}")
        st.download_button("Export sourced prompts (JSON)",
                           st.session_state.sourced_set.model_dump_json(indent=2),
                           "lasso-sourced-prompts.json", "application/json")
        output = io.StringIO()
        rows = [p.model_dump() for p in st.session_state.sourced_set.prompts]
        writer = csv.DictWriter(output, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
        st.download_button("Export sourced prompts (CSV)", output.getvalue(),
                           "lasso-sourced-prompts.csv", "text/csv")
