import json

import build
from conftest import ROOT, load_fixture


def test_format_updated():
    assert build.format_updated("2026-10-04T08:05:00-07:00") == "Sunday, October 4, 8:05 am"
    assert build.format_updated("2026-10-04T12:30:00-07:00") == "Sunday, October 4, 12:30 pm"
    assert build.format_updated("2026-10-04T00:15:00-07:00") == "Sunday, October 4, 12:15 am"
    # A UTC timestamp is converted to Arizona time.
    assert build.format_updated("2026-10-04T20:00:00+00:00") == "Sunday, October 4, 1:00 pm"


def test_item_date_and_domain():
    assert build.format_item_date("2026-09-08") == "Sep 8"
    assert build.domain("https://www.anthropic.com/news/x") == "anthropic.com"
    assert build.domain("https://blog.google/x") == "blog.google"


def test_render_page(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    assert "<title>Latest AI News</title>" in html
    assert "Updated Monday, June 15, 8:00 am Arizona time" in html
    for title in ("New models", "Tools and research", "On campus"):
        assert title in html
    assert "AI+ Studio, University of Arizona Libraries" in html
    assert 'href="https://www.anthropic.com/news/a"' in html
    assert "Anthropic, Jun 14" in html
    assert 'cache: "no-store"' in html
    assert "response.ok" in html


def test_campus_news_first_then_pinned_max_five(good_news, good_pinned):
    campus = good_news["columns"]["campus"][0]
    good_news["columns"]["campus"] = [dict(campus, headline=f"Campus {i}") for i in range(4)]
    ctx = build.build_context(good_news, good_pinned)
    headlines = [i["headline"] for i in ctx["columns"][2]["items"]]
    assert headlines == ["Campus 0", "Campus 1", "Campus 2", "Campus 3", "Studio hours"]


def test_empty_campus_shows_pinned(good_news, good_pinned):
    good_news["columns"]["campus"] = []
    ctx = build.build_context(good_news, good_pinned)
    assert [i["headline"] for i in ctx["columns"][2]["items"]] == ["Studio hours", "Help desk"]


def test_html_is_escaped(good_news, good_pinned):
    good_news["columns"]["models"][0]["headline"] = "<script>alert(1)</script>"
    html = build.render(good_news, good_pinned)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_main_writes_site(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "SITE_DIR", tmp_path / "site")
    assert build.main() == 0
    assert (tmp_path / "site" / "index.html").is_file()
    assert (tmp_path / "site" / "style.css").is_file()
