"""Repository-wide rules from CLAUDE.md that are cheap to check automatically."""

import re
import subprocess

from conftest import ROOT

EM_DASH = chr(0x2014)
TEXT_SUFFIXES = {".py", ".json", ".j2", ".html", ".css", ".md", ".yml", ".yaml", ".txt", ""}


def tracked_files():
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return [ROOT / f for f in out.stdout.splitlines()]


def test_no_em_dashes_in_repository():
    offenders = [
        str(p.relative_to(ROOT))
        for p in tracked_files()
        if p.is_file() and p.suffix in TEXT_SUFFIXES and EM_DASH in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_page_has_no_external_resources():
    template = (ROOT / "templates" / "index.html.j2").read_text(encoding="utf-8")
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    assert "<script src" not in template
    assert "@import" not in css and "url(" not in css
    assert "<form" not in template and "<input" not in template


# Arizona Blue, white, and Arizona Red, plus the light gray and border tint of
# blue used by the brief layout. Nothing else.
ALLOWED_HEX = {"#0C234B", "#FFFFFF", "#AB0520", "#F5F7FB", "#DDE3EE"}
ALLOWED_RGB = {(12, 35, 75), (255, 255, 255)}


def test_page_uses_only_the_palette():
    for path in (ROOT / "static" / "style.css", ROOT / "templates" / "index.html.j2", ROOT / "scripts" / "build.py"):
        text = path.read_text(encoding="utf-8")
        hexes = {h.upper() for h in re.findall(r"#[0-9A-Fa-f]{6}\b", text)}
        assert hexes <= ALLOWED_HEX, (path.name, hexes - ALLOWED_HEX)
        rgbs = {tuple(int(v) for v in m) for m in re.findall(r"rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)", text)}
        assert rgbs <= ALLOWED_RGB, (path.name, rgbs - ALLOWED_RGB)


def _luminance(hex_color):
    channels = [int(hex_color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _blend(fg_hex, alpha, bg_hex):
    fg = [int(fg_hex[i:i + 2], 16) for i in (1, 3, 5)]
    bg = [int(bg_hex[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(alpha * f + (1 - alpha) * b):02X}" for f, b in zip(fg, bg))


def _contrast(a, b):
    la, lb = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def test_text_colors_meet_wcag_aa():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    ink_soft = float(re.search(r"--ink-soft: rgba\(12, 35, 75, ([\d.]+)\)", css).group(1))
    on_navy_soft = float(re.search(r"--on-navy-soft: rgba\(255, 255, 255, ([\d.]+)\)", css).group(1))
    pairs = [
        ("#0C234B", "#FFFFFF"),                                    # navy text on white cards
        ("#0C234B", "#F5F7FB"),                                    # navy text on the gray brief
        ("#AB0520", "#F5F7FB"),                                    # red kicker
        ("#FFFFFF", "#AB0520"),                                    # NEW tag
        ("#FFFFFF", "#0C234B"),                                    # panel and ticker text
        (_blend("#0C234B", ink_soft, "#FFFFFF"), "#FFFFFF"),       # secondary text on white
        (_blend("#0C234B", ink_soft, "#F5F7FB"), "#F5F7FB"),       # secondary text on gray
        (_blend("#FFFFFF", on_navy_soft, "#0C234B"), "#0C234B"),   # secondary text on navy
    ]
    for fg, bg in pairs:
        assert _contrast(fg, bg) >= 4.5, (fg, bg, _contrast(fg, bg))


def test_images_are_only_under_static_img():
    images = [
        p.relative_to(ROOT).as_posix()
        for p in tracked_files()
        if p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
    ]
    assert images and all(i.startswith("static/img/") for i in images), images
