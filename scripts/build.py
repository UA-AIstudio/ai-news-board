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
from markupsafe import Markup

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
# QR codes
#
# A small QR Code Model 2 encoder (byte mode, error correction level M,
# versions 1 to 10), so the page can show a scannable code for each spotlight
# item without adding a dependency. It follows ISO/IEC 18004 and the structure
# of Project Nayuki's public reference implementation.
# ---------------------------------------------------------------------------

QR_MAX_VERSION = 10
# Error correction level M, indexed by version (index 0 unused).
QR_ECC_PER_BLOCK = (0, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26)
QR_NUM_BLOCKS = (0, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5)
QR_FORMAT_ECL_M = 0  # format bits for level M


def _qr_raw_modules(ver: int) -> int:
    result = (16 * ver + 128) * ver + 64
    if ver >= 2:
        num_align = ver // 7 + 2
        result -= (25 * num_align - 10) * num_align - 55
        if ver >= 7:
            result -= 36
    return result


def _qr_data_capacity(ver: int) -> int:
    return _qr_raw_modules(ver) // 8 - QR_ECC_PER_BLOCK[ver] * QR_NUM_BLOCKS[ver]


def _gf_multiply(x: int, y: int) -> int:
    z = 0
    for i in reversed(range(8)):
        z = (z << 1) ^ ((z >> 7) * 0x11D)
        z ^= ((y >> i) & 1) * x
    return z


def _rs_divisor(degree: int) -> list[int]:
    result = [0] * (degree - 1) + [1]
    root = 1
    for _ in range(degree):
        for j in range(degree):
            result[j] = _gf_multiply(result[j], root)
            if j + 1 < degree:
                result[j] ^= result[j + 1]
        root = _gf_multiply(root, 0x02)
    return result


def _rs_remainder(data: list[int], divisor: list[int]) -> list[int]:
    result = [0] * len(divisor)
    for b in data:
        factor = b ^ result.pop(0)
        result.append(0)
        for i, coef in enumerate(divisor):
            result[i] ^= _gf_multiply(coef, factor)
    return result


def _qr_alignment_positions(ver: int) -> list[int]:
    if ver == 1:
        return []
    num_align = ver // 7 + 2
    step = (ver * 4 + num_align * 2 + 1) // (num_align * 2 - 2) * 2
    size = ver * 4 + 17
    positions = [6]
    pos = size - 7
    while len(positions) < num_align:
        positions.insert(1, pos)
        pos -= step
    return positions


def _qr_mask_bit(mask: int, x: int, y: int) -> bool:
    if mask == 0:
        return (x + y) % 2 == 0
    if mask == 1:
        return y % 2 == 0
    if mask == 2:
        return x % 3 == 0
    if mask == 3:
        return (x + y) % 3 == 0
    if mask == 4:
        return (x // 3 + y // 2) % 2 == 0
    if mask == 5:
        return x * y % 2 + x * y % 3 == 0
    if mask == 6:
        return (x * y % 2 + x * y % 3) % 2 == 0
    return ((x + y) % 2 + x * y % 3) % 2 == 0


class _QrGrid:
    def __init__(self, ver: int):
        self.ver = ver
        self.size = ver * 4 + 17
        self.dark = [[False] * self.size for _ in range(self.size)]
        self.function = [[False] * self.size for _ in range(self.size)]

    def set_function(self, x: int, y: int, dark: bool) -> None:
        self.dark[y][x] = dark
        self.function[y][x] = True

    def draw_function_patterns(self) -> None:
        size = self.size
        for i in range(size):
            self.set_function(6, i, i % 2 == 0)
            self.set_function(i, 6, i % 2 == 0)
        for cx, cy in ((3, 3), (size - 4, 3), (3, size - 4)):
            for dy in range(-4, 5):
                for dx in range(-4, 5):
                    x, y = cx + dx, cy + dy
                    if 0 <= x < size and 0 <= y < size:
                        dist = max(abs(dx), abs(dy))
                        self.set_function(x, y, dist not in (2, 4))
        align = _qr_alignment_positions(self.ver)
        last = len(align) - 1
        for i, ax in enumerate(align):
            for j, ay in enumerate(align):
                if (i, j) in ((0, 0), (0, last), (last, 0)):
                    continue
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        self.set_function(ax + dx, ay + dy, max(abs(dx), abs(dy)) != 1)
        self.draw_format_bits(0)  # reserve the area; redrawn after masking
        self.draw_version()

    def draw_format_bits(self, mask: int) -> None:
        data = QR_FORMAT_ECL_M << 3 | mask
        rem = data
        for _ in range(10):
            rem = (rem << 1) ^ ((rem >> 9) * 0x537)
        bits = (data << 10 | rem) ^ 0x5412
        bit = lambda i: (bits >> i) & 1 != 0  # noqa: E731
        size = self.size
        for i in range(6):
            self.set_function(8, i, bit(i))
        self.set_function(8, 7, bit(6))
        self.set_function(8, 8, bit(7))
        self.set_function(7, 8, bit(8))
        for i in range(9, 15):
            self.set_function(14 - i, 8, bit(i))
        for i in range(8):
            self.set_function(size - 1 - i, 8, bit(i))
        for i in range(8, 15):
            self.set_function(8, size - 15 + i, bit(i))
        self.set_function(8, size - 8, True)

    def draw_version(self) -> None:
        if self.ver < 7:
            return
        rem = self.ver
        for _ in range(12):
            rem = (rem << 1) ^ ((rem >> 11) * 0x1F25)
        bits = self.ver << 12 | rem
        for i in range(18):
            dark = (bits >> i) & 1 != 0
            a, b = self.size - 11 + i % 3, i // 3
            self.set_function(a, b, dark)
            self.set_function(b, a, dark)

    def draw_codewords(self, data: list[int]) -> None:
        size = self.size
        i = 0
        right = size - 1
        while right >= 1:
            if right == 6:
                right = 5
            for vert in range(size):
                for j in range(2):
                    x = right - j
                    upward = (right + 1) & 2 == 0
                    y = size - 1 - vert if upward else vert
                    if not self.function[y][x] and i < len(data) * 8:
                        self.dark[y][x] = (data[i >> 3] >> (7 - (i & 7))) & 1 != 0
                        i += 1
            right -= 2

    def apply_mask(self, mask: int) -> None:
        for y in range(self.size):
            for x in range(self.size):
                if not self.function[y][x] and _qr_mask_bit(mask, x, y):
                    self.dark[y][x] = not self.dark[y][x]

    def penalty(self) -> int:
        size, dark = self.size, self.dark
        score = 0
        lines = [row[:] for row in dark] + [[dark[y][x] for y in range(size)] for x in range(size)]
        finder = [True, False, True, True, True, False, True]
        for line in lines:
            run, prev = 0, None
            for cell in line:
                if cell == prev:
                    run += 1
                else:
                    if run >= 5:
                        score += 3 + run - 5
                    run, prev = 1, cell
            if run >= 5:
                score += 3 + run - 5
            padded = [False] * 4 + line + [False] * 4
            for k in range(len(padded) - 6):
                if padded[k:k + 7] == finder:
                    before = padded[max(0, k - 4):k]
                    after = padded[k + 7:k + 11]
                    if (len(before) == 4 and not any(before)) or (len(after) == 4 and not any(after)):
                        score += 40
        for y in range(size - 1):
            for x in range(size - 1):
                c = dark[y][x]
                if c == dark[y][x + 1] == dark[y + 1][x] == dark[y + 1][x + 1]:
                    score += 3
        total = size * size
        count = sum(sum(row) for row in dark)
        k = (abs(count * 20 - total * 10) + total - 1) // total - 1
        score += k * 10
        return score


def qr_matrix(text: str, mask: int | None = None) -> list[list[bool]]:
    """Encode text as a QR code (byte mode, level M). Returns rows of booleans
    (True is dark), without the quiet zone. Raises ValueError if it is too long."""
    payload = text.encode("utf-8")
    for ver in range(1, QR_MAX_VERSION + 1):
        count_bits = 8 if ver <= 9 else 16
        if 4 + count_bits + 8 * len(payload) <= _qr_data_capacity(ver) * 8:
            break
    else:
        raise ValueError(f"text too long for a version {QR_MAX_VERSION} QR code: {len(payload)} bytes")

    bits: list[int] = []

    def append(value: int, length: int) -> None:
        bits.extend((value >> i) & 1 for i in reversed(range(length)))

    capacity_bits = _qr_data_capacity(ver) * 8
    append(0b0100, 4)
    append(len(payload), count_bits)
    for b in payload:
        append(b, 8)
    append(0, min(4, capacity_bits - len(bits)))
    append(0, -len(bits) % 8)
    pad = 0xEC
    while len(bits) < capacity_bits:
        append(pad, 8)
        pad ^= 0xEC ^ 0x11
    data = [int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8)]

    num_blocks, ecc_len = QR_NUM_BLOCKS[ver], QR_ECC_PER_BLOCK[ver]
    raw_codewords = _qr_raw_modules(ver) // 8
    num_short = num_blocks - raw_codewords % num_blocks
    short_len = raw_codewords // num_blocks
    divisor = _rs_divisor(ecc_len)
    blocks, k = [], 0
    for i in range(num_blocks):
        length = short_len - ecc_len + (0 if i < num_short else 1)
        block = data[k:k + length]
        k += length
        ecc = _rs_remainder(block, divisor)
        if i < num_short:
            block = block + [0]
        blocks.append(block + ecc)
    codewords = []
    for i in range(len(blocks[0])):
        for j, block in enumerate(blocks):
            if i != short_len - ecc_len or j >= num_short:
                codewords.append(block[i])

    def build(m: int) -> _QrGrid:
        grid = _QrGrid(ver)
        grid.draw_function_patterns()
        grid.draw_codewords(codewords)
        grid.apply_mask(m)
        grid.draw_format_bits(m)
        return grid

    if mask is None:
        grid = min((build(m) for m in range(8)), key=lambda g: g.penalty())
    else:
        grid = build(mask)
    return grid.dark


def qr_svg(text: str, label: str) -> Markup:
    """An inline SVG QR code with a 4-module quiet zone, navy on white."""
    matrix = qr_matrix(text)
    quiet = 4
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
    svg = (
        f'<svg class="qr" viewBox="0 0 {total} {total}" role="img" aria-label="QR code: {label}" '
        f'shape-rendering="crispEdges" xmlns="http://www.w3.org/2000/svg">'
        f'<rect width="{total}" height="{total}" fill="#FFFFFF"/>'
        f'<path fill="#0C234B" d="{"".join(path)}"/></svg>'
    )
    return Markup(svg)


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
            items.append(entry)
    return sorted(items, key=lambda i: i["iso_date"], reverse=True)


def studio_hours(pinned: list) -> dict | None:
    for item in pinned:
        if item.get("hours"):
            return item["hours"]
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
