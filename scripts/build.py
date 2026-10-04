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

import qrcode
from jinja2 import Environment, FileSystemLoader, StrictUndefined
from markupsafe import Markup
from qrcode.constants import ERROR_CORRECT_M

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

# Columns whose items rotate through the spotlight carousel.
SPOTLIGHT_COLUMNS = ("models", "tools")


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


# ---------------------------------------------------------------------------
# QR codes and metrics
# ---------------------------------------------------------------------------

QR_QUIET_ZONE = 4  # modules of white around the code, as the QR standard requires


def qr_matrix(text: str) -> list[list[bool]]:
    """QR code modules for text (error correction level M), without the quiet zone."""
    code = qrcode.QRCode(error_correction=ERROR_CORRECT_M, border=0)
    code.add_data(text)
    code.make(fit=True)
    return code.get_matrix()


def qr_svg(text: str, label: str) -> Markup:
    """An inline SVG QR code, navy on a white square with a quiet zone."""
    matrix = qr_matrix(text)
    quiet = QR_QUIET_ZONE
    total = len(matrix) + 2 * quiet
    path = []
    for y, row in enumerate(matrix):
        x = 0
        while x < len(row):
            if row[x]:
                start = x
                while x < len(row) and row[x]:
                    x += 1
                path.append(f"M{start + quiet} {y + quiet}h{x - start}v1h{start - x}z")
            else:
                x += 1
    return Markup(
        '<svg class="qr" viewBox="0 0 {total} {total}" role="img" aria-label="QR code: {label}" '
        'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">'
        '<rect width="{total}" height="{total}" fill="#FFFFFF"/>'
        '<path fill="#0C234B" d="{path}"/></svg>'
    ).format(total=total, label=label, path="".join(path))


def format_number(value: float | int) -> str:
    """The value as written, without float noise: 30 -> '30', 2.50 -> '2.5'."""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value) if isinstance(value, int) else repr(value)


def format_metric_value(value: float | int, unit: str | None) -> str:
    text = format_number(value)
    if not unit:
        return text
    return text + unit if unit in ("%", "x") else f"{text} {unit}"


def prepare_metrics(metrics: list[dict]) -> list[dict]:
    """Display text and bar length (0 to 1) for each metric.

    A bar is drawn only when it has a real scale: percentages fill against 100,
    and other values fill against the largest value with the same unit on the
    same item when at least two metrics share that unit. A value with nothing
    to compare against gets no bar ("fill" is None), only its text.
    """
    by_unit: dict[str, list[float]] = {}
    for m in metrics:
        by_unit.setdefault(m.get("unit", ""), []).append(m["value"])
    prepared = []
    for m in metrics:
        unit = m.get("unit", "")
        if unit == "%":
            scale = 100
        elif len(by_unit[unit]) > 1:
            scale = max(by_unit[unit])
        else:
            scale = None
        fill = None
        if scale is not None:
            ratio = m["value"] / scale if scale > 0 else 0
            fill = f"{min(max(ratio, 0), 1):.4f}"
        prepared.append({
            "label": m["label"],
            "text": format_metric_value(m["value"], unit),
            "fill": fill,
        })
    return prepared


# ---------------------------------------------------------------------------
# Page context
# ---------------------------------------------------------------------------


def prepare_item(item: dict) -> dict:
    return {
        "headline": item["headline"],
        "summary": item["summary"],
        "source": item["source"],
        "url": item["url"],
        "iso_date": item.get("date", ""),
        "date": format_item_date(item["date"]) if item.get("date") else "",
        "domain": domain(item["url"]),
        "has_hours": bool(item.get("hours")),
    }


def spotlight_items(news: dict) -> list[dict]:
    """All models and tools items, newest first (ties keep column order)."""
    titles = dict(COLUMNS)
    items = []
    for key in SPOTLIGHT_COLUMNS:
        for item in news["columns"][key]:
            entry = prepare_item(item)
            entry["kind"] = titles[key]
            entry["qr"] = qr_svg(item["url"], domain(item["url"]))
            entry["metrics"] = prepare_metrics(item.get("metrics", []))
            entry["reported_by"] = item.get("reported_by", "")
            items.append(entry)
    return sorted(items, key=lambda i: i["iso_date"], reverse=True)


def studio_hours(pinned: list) -> dict | None:
    """Regular hours and closure dates for the pinned item that has hours."""
    for item in pinned:
        if item.get("hours"):
            return {"hours": item["hours"], "closures": item.get("closures", [])}
    return None


def build_context(news: dict, pinned: list) -> dict:
    columns = []
    for key, title in COLUMNS:
        items = list(news["columns"][key])
        if key == "campus":
            items = (items + list(pinned))[:CAMPUS_MAX]
        columns.append({"key": key, "title": title, "items": [prepare_item(i) for i in items]})
    ticker = [item["headline"] for column in columns for item in column["items"]]
    return {
        "updated": format_updated(news["updated"]),
        "columns": columns,
        "spotlight": spotlight_items(news),
        "ticker": ticker,
        "hours": studio_hours(pinned),
    }


def load_script() -> Markup:
    script = (STATIC_DIR / "board.js").read_text(encoding="utf-8")
    if "</script" in script.lower():
        raise ValueError("static/board.js must not contain '</script'")
    return Markup(script)


def render(news: dict, pinned: list, preview: bool = False) -> str:
    env = Environment(
        loader=FileSystemLoader(TEMPLATE_DIR),
        autoescape=True,
        undefined=StrictUndefined,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    context = build_context(news, pinned)
    return env.get_template("index.html.j2").render(**context, preview=preview, board_js=load_script())


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
