"""Repository-wide rules from CLAUDE.md that are cheap to check automatically."""

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
