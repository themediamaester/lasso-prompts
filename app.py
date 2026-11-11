
import streamlit as st
import anthropic

st.set_page_config(
    page_title="Lasso Prompts",
    page_icon="🎯",
    layout="centered"
)

# ---------- Password Protection ----------
PASSWORD = st.secrets.get("APP_PASSWORD", "changeme")

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("Lasso Prompts")
    st.write("Password required to access the tool.")
    password = st.text_input("Enter password", type="password")
    if st.button("Unlock"):
        if password == PASSWORD:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password")
    st.stop()

# ---------- Main App ----------
st.title("Lasso Prompts")
st.caption("Turn real customer language into buyer-intent prompts")

brand = st.text_input("Brand name", value="Attention Lasso")
website = st.text_input("Website URL", value="https://attentionlasso.com")
market = st.selectbox(
    "Primary market",
    ["Global / United States", "Kenya / East Africa", "Middle East / Dubai", "Other"]
)

st.divider()
st.subheader("Step 1 — Find real customer language")

if st.button("Suggest best data sources"):
    with st.spinner("Finding high-signal sources..."):
        client = anthropic.Anthropic(
            api_key=st.secrets["ANTHROPIC_API_KEY"]
        )

        source_prompt = f"""
You are helping a marketer collect real buyer language for the brand "{brand}" ({website}).
Market focus: {market}.

Suggest the highest-signal places to find authentic customer language. Be specific and practical.

Return the answer in this exact structure:

### Recommended Search Queries
- List 6–8 precise search queries the user can paste into Google or Reddit search

### Best Reddit Communities
- List 4–6 relevant subreddits (with short reason)

### Review & Feedback Sites
- List the most relevant review platforms for this type of business

### Other High-Value Sources
- Any other good places (forums, Facebook groups, Quora, specific websites, etc.)

### How to Collect Fast
- Give 3–4 short practical tips for collecting useful language quickly
"""

        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1500,
            messages=[{"role": "user", "content": source_prompt}]
        )

        st.markdown(message.content[0].text)

st.divider()
st.subheader("Step 2 — Paste the evidence")

evidence = st.text_area(
    "Paste customer language here (chatbot logs, Reddit comments, reviews, sales notes, support tickets, etc.)",
    height=250,
    placeholder="The more real customer language you paste, the better the prompts will be..."
)

st.divider()

if st.button("Generate Prompt Library", type="primary"):
    if not brand.strip() or not website.strip():
        st.warning("Brand name and website are required.")
    else:
        with st.spinner("Extracting natural buyer language and building prompts..."):
            client = anthropic.Anthropic(
                api_key=st.secrets["ANTHROPIC_API_KEY"]
            )

            generation_prompt = f"""
You are Lasso Prompts — an expert at turning real customer language into high-quality buyer-intent prompts for AI visibility tracking and content.

Highest priority: authenticity and natural language. Prefer the exact words and phrasing customers actually use. Keep language as close to verbatim as possible. Do not polish it into marketing-speak.

Brand: {brand}
Website: {website}
Market: {market}

Evidence provided by the user:
{evidence if evidence.strip() else "No additional evidence was provided. Work carefully from the brand and website context only."}

Produce the following sections:

### 1. Voice of Customer Summary
- Top pains / problems (include short real phrases when available)
- Desired outcomes
- Exact customer phrases worth reusing (prioritize verbatim language)

### 2. Competitor Shortlist
List 4–7 relevant competitors. For each, give a short reason. If none were provided in the evidence, discover likely ones from the category and context.

### 3. Buyer Intent Prompt Library
Create 25–40 natural full-sentence prompts that a real buyer would type into ChatGPT, Claude, Perplexity or Gemini.

Group them under these headings:
- Discovery / Category
- Problem / Symptom
- Comparison / Alternatives
- Evaluation / Best for...
- Local / Use-case / Constraints
- Brand & Trust (only include if supported by the evidence)

Rules:
- Sound like a real person speaking, not a marketer
- Prefer patterns and wording found in the evidence
- Keep prompts specific and natural
- Avoid forcing the brand name into prompts unless it appears naturally in customer language

### 4. Recommended Core Panel
Select the strongest 15–20 prompts that should be tracked or used first. List them clearly.

Be rigorous. Quality and authenticity over volume.
"""

            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4000,
                messages=[{"role": "user", "content": generation_prompt}]
            )

            result = message.content[0].text
            st.markdown(result)

            st.download_button(
                label="Download as Markdown",
                data=result,
                file_name=f"{brand.lower().replace(' ', '-')}-lasso-prompts.md",
                mime="text/markdown"
            )

st.divider()
st.caption("Lasso Prompts · Built by Attention Lasso")
