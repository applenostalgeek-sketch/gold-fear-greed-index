"""inject_scores.py - Pre-render current scores into index.html for SEO.

Runs after all score scripts and generate_summary.py in the workflow.
Replaces placeholder values in index.html so Google can index real scores
without executing JavaScript.
"""
import json
import re
import html
from pathlib import Path
from datetime import datetime, timezone


def load_json(path):
    with open(path) as f:
        return json.load(f)


def replace_element_content(content, element_id, new_content):
    """Replace text content of element with given id."""
    escaped = html.escape(str(new_content))
    # Match opening tag with this id (any attribute order), capture content, stop at next tag
    pattern = rf'(id="{re.escape(element_id)}"[^>]*>)([\s\S]*?)(<)'
    # Use \g<N> syntax to avoid ambiguity when escaped starts with a digit
    replacement = rf'\g<1>{escaped}\g<3>'
    new_content_str, count = re.subn(pattern, replacement, content, count=1)
    if count == 0:
        print(f"  WARNING: element id='{element_id}' not found")
    return new_content_str


def get_label_upper(score):
    s = round(score)
    if s <= 25: return "EXTREME FEAR"
    if s <= 45: return "FEAR"
    if s <= 55: return "NEUTRAL"
    if s <= 75: return "GREED"
    return "EXTREME GREED"


def main():
    index_path = Path("index.html")
    content = index_path.read_text(encoding="utf-8")

    # Load asset scores
    assets = {}
    for asset in ["gold", "bonds", "stocks", "crypto"]:
        data = load_json(f"data/{asset}-fear-greed.json")
        assets[asset] = {"score": round(data["score"]), "label": data["label"]}

    # Load sentiment from market-summary.json
    summary = load_json("data/market-summary.json")
    sentiment = summary["scores"]["sentiment"]
    sentiment_score = round(sentiment["score"])
    sentiment_label = get_label_upper(sentiment_score)
    ai_summary = summary.get("summary", "")

    # Date (UTC, no time — close enough for daily updates)
    date_str = "Updated: " + datetime.now(timezone.utc).strftime("%B %d, %Y")

    # Inject sentiment hero circle
    content = replace_element_content(content, "score", sentiment_score)
    content = replace_element_content(content, "label", sentiment_label)

    # Inject asset mini-circle scores (labels are hidden by JS, skip them)
    for asset in ["gold", "bonds", "stocks", "crypto"]:
        content = replace_element_content(content, f"{asset}Value", assets[asset]["score"])

    # Inject date
    content = replace_element_content(content, "updated", date_str)

    # Inject AI summary into insight div (Google indexes it; JS overwrites for users)
    if len(ai_summary) > 20:
        content = replace_element_content(content, "insight", ai_summary)

    index_path.write_text(content, encoding="utf-8")

    print("Injected scores into index.html")
    print(f"  Sentiment: {sentiment_score} ({sentiment_label})")
    for asset in ["gold", "bonds", "stocks", "crypto"]:
        print(f"  {asset.capitalize()}: {assets[asset]['score']} ({assets[asset]['label']})")
    if len(ai_summary) > 20:
        print(f"  AI summary: {ai_summary[:80]}...")


if __name__ == "__main__":
    main()
