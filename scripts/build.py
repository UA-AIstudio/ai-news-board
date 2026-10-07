#!/usr/bin/env python3
"""Build site/index.html from data/*.json and templates/index.html.j2.

Usage:
    python scripts/build.py
    python scripts/build.py --preview --data-dir ../dev/data --out site/dev
"""

from __future__ import annotations

import argparse
import io
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
from PIL import Image
from qrcode.constants import ERROR_CORRECT_M

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
TEMPLATE_DIR = ROOT / "templates"
STATIC_DIR = ROOT / "static"
SITE_DIR = ROOT / "site"

TZ = ZoneInfo("America/Phoenix")

COLUMNS = (
    ("models", "New models"),
    ("tools", "Tools and research"),
    ("campus", "On campus"),
)

# Each column card shows this many items at a time and rotates through the rest.
PAGE_SIZE = 2

# Shown in a column that has no items (only "campus" may be empty).
EMPTY_COLUMN = "No new campus AI news this week"

# The right-hand Studio panel. Public information about the Studio itself.
STUDIO = {
    "url": "https://lib.arizona.edu/study/ai-studio",
    "room": "Room 212, Weaver Science-Engineering Library",
    "email": "lbry-aistudio@arizona.edu",
    "offers": (
        "Use local LLMs",
        "Talk to an AI specialist",
        "Attend workshops and events",
        "Plan an AI challenge",
    ),
}

# The poster artwork for the Studio panel. People add and replace images under
# static/img/; the build converts the poster to WebP for the page.
POSTER_SOURCE = STATIC_DIR / "img" / "studio-poster.png"
POSTER_PATH = "img/studio-poster.webp"
POSTER_MAX_BYTES = 400_000
# The part of the poster the panel shows, as fractions of its width and height
# (left, top, right, bottom): the students and the robot. This trims the
# poster's own title, tiles and contact strip, which the panel already shows
# as text. Check it whenever the poster is replaced.
POSTER_FOCUS = (0.465, 0.03, 0.885, 0.71)

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

# Columns whose items rotate through the spotlight carousel.
SPOTLIGHT_COLUMNS = ("models", "tools")


def format_updated(raw: str) -> str:
    """'2026-10-04T08:15:00-07:00' -> 'Sunday, October 4, 8:15 am'."""
    checked = format_checked(raw)
    return f"{checked['date']}, {checked['time']}"


def format_checked(raw: str) -> dict:
    """'2026-10-04T08:15:00-07:00' -> {'time': '8:15 am', 'date': 'Sunday, October 4'}."""
    stamp = datetime.fromisoformat(raw).astimezone(TZ)
    hour = stamp.hour % 12 or 12
    ampm = "am" if stamp.hour < 12 else "pm"
    return {"time": f"{hour}:{stamp:%M} {ampm}", "date": f"{stamp:%A}, {stamp:%B} {stamp.day}"}


def format_clock(hhmm: str) -> str:
    """'18:00' -> '6pm', '11:30' -> '11:30am', '12:00' -> '12pm'."""
    h, m = (int(x) for x in hhmm.split(":"))
    suffix = "am" if h < 12 else "pm"
    return f"{h % 12 or 12}{f':{m:02d}' if m else ''}{suffix}"


def format_hours(hours: dict) -> str:
    """Weekly hours as one line: 'Mon to Thu 11am to 6pm, Fri 11am to 5pm'.

    Consecutive days with the same hours are grouped; closed days are left out.
    """
    groups: list[list] = []  # [first day, last day, [open, close]]
    previous = None
    for key in DAY_KEYS:
        span = hours.get(key)
        if span and span == previous:
            groups[-1][1] = key
        elif span:
            groups.append([key, key, span])
        previous = span
    parts = []
    for first, last, (opens, closes) in groups:
        days = first.title() if first == last else f"{first.title()} to {last.title()}"
        parts.append(f"{days} {format_clock(opens)} to {format_clock(closes)}")
    return ", ".join(parts)


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


def poster_info(source: Path = POSTER_SOURCE) -> dict | None:
    """Size of the cropped poster, for the img tag, or None if there is no poster."""
    if not source.is_file():
        return None
    with Image.open(source) as image:
        left, top, right, bottom = poster_box(image.size)
    return {"src": POSTER_PATH, "width": right - left, "height": bottom - top}


def poster_box(size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    left, top, right, bottom = POSTER_FOCUS
    return (round(left * width), round(top * height), round(right * width), round(bottom * height))


def write_poster(source: Path, dest: Path, max_bytes: int = POSTER_MAX_BYTES) -> int:
    """Crop the poster to POSTER_FOCUS and save it as WebP under max_bytes.

    Lowers the quality first, then the size, until it fits. Returns the bytes written.
    """
    with Image.open(source) as image:
        image = image.convert("RGB").crop(poster_box(image.size))
    while True:
        for quality in (82, 74, 66, 58, 50):
            buffer = io.BytesIO()
            image.save(buffer, "WEBP", quality=quality, method=6)
            if buffer.tell() <= max_bytes:
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(buffer.getvalue())
                return buffer.tell()
        if image.width < 200:
            raise ValueError(f"{source} cannot be made smaller than {max_bytes} bytes as WebP")
        image = image.resize((image.width * 3 // 4, image.height * 3 // 4), Image.LANCZOS)


def studio_hours(pinned: list) -> dict | None:
    """Regular hours and closure dates for the pinned item that has hours."""
    for item in pinned:
        if item.get("hours"):
            return {"hours": item["hours"], "closures": item.get("closures", [])}
    return None


def paginate(items: list, size: int = PAGE_SIZE) -> list[list]:
    """Split items into pages of `size`, in order. No items means no pages."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def build_context(news: dict, pinned: list) -> dict:
    """Page data. The columns hold news only; pinned items (Studio hours, the
    AI desk) go to the Studio panel and are not repeated in the ticker."""
    columns = [
        {
            "key": key,
            "title": title,
            "items": [prepare_item(i) for i in news["columns"][key]],
            "empty": EMPTY_COLUMN,
        }
        for key, title in COLUMNS
    ]
    for column in columns:
        column["pages"] = paginate(column["items"])
    ticker = [item["headline"] for column in columns for item in column["items"]]
    hours = studio_hours(pinned)
    return {
        "checked": format_checked(news["updated"]),
        "columns": columns,
        "spotlight": spotlight_items(news),
        "ticker": ticker,
        "hours": hours,
        "hours_text": format_hours(hours["hours"]) if hours else "",
        "notes": [prepare_item(p) for p in pinned if not p.get("hours")],
        "studio": {**STUDIO, "qr": qr_svg(STUDIO["url"], domain(STUDIO["url"]))},
        "poster": poster_info(),
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
    if POSTER_SOURCE.is_file():
        write_poster(POSTER_SOURCE, out / POSTER_PATH)
    print(f"Built {out / 'index.html'}{' (preview)' if args.preview else ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
