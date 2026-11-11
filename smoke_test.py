"""Public-site smoke test. No AI requests."""
import json
from crawler import crawl

result = crawl("https://attentionlasso.com", max_pages=15)
summary = {
    "status": result["status"],
    "attempts": result["attempts"],
    "pages": [
        {"url": p["url"], "title": p["title"], "characters": len(p["text"]),
         "sufficient": p["sufficient"], "headings": p["headings"][:8]}
        for p in result["pages"]
    ],
    "failures": result["failures"],
}
with open("attention-lasso-crawl-report.json", "w", encoding="utf-8") as out:
    json.dump(summary, out, indent=2)
print(json.dumps(summary, indent=2))
