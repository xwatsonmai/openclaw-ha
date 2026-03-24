#!/usr/bin/env python3
import json
import os
import sys
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRIEF_PATH = os.path.join(ROOT, "data", "answer_brief.json")
SUMMARY_PATH = os.path.join(ROOT, "data", "summary.json")
CARD_PATH = os.path.join(ROOT, "data", "answer_card.md")


def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_iso(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def age_seconds(ts):
    return int((datetime.now(timezone.utc) - parse_iso(ts)).total_seconds())


def mode_brief():
    data = load_json(BRIEF_PATH)
    result = {
        "generated_at": data.get("generated_at"),
        "age_seconds": age_seconds(data.get("generated_at")),
        "headline": data.get("headline"),
        "lines": data.get("lines", [])
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def mode_summary():
    data = load_json(SUMMARY_PATH)
    result = {
        "generated_at": data.get("generated_at"),
        "age_seconds": age_seconds(data.get("generated_at")),
        "counts": data.get("counts", {}),
        "focus": data.get("focus", {}),
        "focus_alerts": data.get("focus_alerts", []),
        "answer_views": data.get("answer_views", {})
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


def mode_card():
    with open(CARD_PATH, "r", encoding="utf-8") as f:
        print(f.read())


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "brief"
    if mode == "brief":
        mode_brief()
    elif mode == "summary":
        mode_summary()
    elif mode == "card":
        mode_card()
    else:
        print("usage: read_cache.py [brief|summary|card]", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
