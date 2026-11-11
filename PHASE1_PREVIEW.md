# Lasso Prompts Phase 1 development preview

This branch is **not production-ready**. It does not modify the existing `app.py` on `main`.

## Run locally

```bash
git checkout feature/phase1-crawler
python -m venv .venv
# Activate your environment, then:
pip install -r requirements-dev.txt
streamlit run phase1_app.py
```

Set `ANTHROPIC_API_KEY` in local Streamlit secrets or your environment. Never commit secrets. You can inspect the crawl and extracted text without an API key.

## Create a separate Streamlit Community Cloud test app

1. In Streamlit Community Cloud, select **New app** and choose repository `themediamaester/lasso-prompts`.
2. Select branch `feature/phase1-crawler`, entrypoint `phase1_app.py`.
3. Add the existing `ANTHROPIC_API_KEY` to the **new test app's** Secrets settings (do not paste it into GitHub).
4. Deploy the **separate** app. Do not change the existing production app.
5. Enter `https://attentionlasso.com`, click **Discover website pages**, and inspect the pages and excerpts.
6. Select the service, About, pricing, and product pages. Confirm API use, then click **Analyze selected pages** once.
7. Review each service and its supporting quotation. Export the reviewed JSON.

**Dependencies:** This development branch includes the crawler dependencies in `requirements.txt`; production `main` is unchanged.

## Pass criteria

- The website is identified as an attention-engineering / marketing services business, **not** eye-tracking software.
- The five primary service pillars are represented from the actual fetched pages.
- Every service has a cited fetched URL and an excerpt present on that page.
- Unknown information is not invented.
- A user can inspect and correct the draft before export.
- The production app stays unchanged.

## Known limitations

The analyzer uses one Anthropic API request and does not automatically retry. It cannot guarantee that every inferred statement is correct. Evidence validation confirms that quotations exist, not that the interpretation is logically sound. There is no persistence across session resets. No competitor research or prompt generation is included.
