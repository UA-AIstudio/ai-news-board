#!/usr/bin/env python3
"""Build site/index.html from data/*.json and templates/index.html.j2.

Usage:
    python scripts/build.py
    python scripts/build.py --preview --data-dir ../dev/data --out site/dev
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
SITE_DIR = ROOT / "site"

TZ = ZoneInfo("America/Phoenix")
CAMPUS_MAX = 5

COLUMNS = (
    ("models", "New models"),
    ("tools", "Tools and research"),
    ("campus", "On campus"),
)


def format_updated(raw: str) -> str:
    """'2026-10-04T08:15:00-07:00' -> 'Sunday, October 4, 8:15 am'."""
    stamp = datetime.fromisoformat(raw).astimezone(TZ)
    hour = stamp.hour % 12 or 12
    ampm = "am" if stamp.hour < 12 else "pm"
    return f"{stamp:%A}, {stamp:%B} {stamp.day}, {hour}:{stamp:%M} {ampm}"


def format_item_date(raw: str) -> str:
    """'2026-09-28' -> 'Sep 28'."""
    d = date.fromisoformat(raw)
    return f"{d:%b} {d.day}"


def domain(url: str) -> str:
    host = urlparse(url).hostname or ""
    return host[4:] if host.startswith("www.") else host


def prepare_item(item: dict) -> dict:
    return {
        "headline": item["headline"],
        "summary": item["summary"],
        "source": item["source"],
        "url": item["url"],
        "date": format_item_date(item["date"]) if item.get("date") else "",
        "domain": domain(item["url"]),
    }


def build_context(news: dict, pinned: list) -> dict:
    columns = []
    for key, title in COLUMNS:
        items = list(news["columns"][key])
        if key == "campus":
            items = (items + list(pinned))[:CAMPUS_MAX]
        columns.append({"key": key, "title": title, "items": [prepare_item(i) for i in items]})
    return {"updated": format_updated(news["updated"]), "columns": columns}


def render(news: dict, pinned: list, preview: bool = False) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    context = build_context(news, pinned)
    return env.get_template("index.html.j2").render(**context, preview=preview)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--preview",
        action="store_true",
        help='build the dev preview: adds a "Preview, not live" banner and noindex',
    )
    parser.add_argument("--data-dir", type=Path, help="folder with news.json and pinned.json (default: data/)")
    parser.add_argument("--out", type=Path, help="output folder (default: site/)")
    args = parser.parse_args(argv)
    data_dir = args.data_dir or DATA_DIR
    out = args.out or SITE_DIR

    news = json.loads((data_dir / "news.json").read_text(encoding="utf-8"))
    pinned = json.loads((data_dir / "pinned.json").read_text(encoding="utf-8"))
    html = render(news, pinned, preview=args.preview)

    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    (out / "index.html").write_text(html, encoding="utf-8")
    shutil.copy2(STATIC_DIR / "style.css", out / "style.css")
    print(f"Built {out / 'index.html'}{' (preview)' if args.preview else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
