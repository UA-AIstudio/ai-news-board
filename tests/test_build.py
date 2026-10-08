import json

import pytest
from PIL import Image

import build
from conftest import ROOT, load_fixture

BANNER = "Preview, not live. Awaiting review."


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


def test_format_checked():
    assert build.format_checked("2026-10-04T08:05:00-07:00") == {"time": "8:05 am", "date": "Sunday, October 4"}
    assert build.format_checked("2026-10-04T20:00:00+00:00") == {"time": "1:00 pm", "date": "Sunday, October 4"}


def test_render_page(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    assert "<title>Latest AI News</title>" in html
    assert "Checked at 8:00 am Arizona time" in html
    assert '<span class="checked-date">Monday, June 15</span>' in html
    assert '<p class="brand-label">AI+ Studio</p>' in html
    assert '<p class="kicker">Your daily brief</p>' in html
    for title in ("New models", "Tools and research", "On campus"):
        assert title in html
    assert "AI+ Studio, University of Arizona Libraries" in html
    assert 'href="https://www.anthropic.com/news/a"' in html
    assert '<span class="source">Anthropic</span> <span class="sep">New models</span> <span class="date">Jun 14</span>' in html
    assert 'cache: "no-store"' in html
    assert "response.ok" in html


def test_campus_column_has_news_only(good_news, good_pinned):
    campus = good_news["columns"]["campus"][0]
    good_news["columns"]["campus"] = [dict(campus, headline=f"Campus {i}") for i in range(5)]
    ctx = build.build_context(good_news, good_pinned)
    headlines = [i["headline"] for i in ctx["columns"][2]["items"]]
    assert headlines == [f"Campus {i}" for i in range(5)]


@pytest.mark.parametrize("campus_items", [0, 1, 5])
def test_third_column_always_renders(good_news, good_pinned, campus_items):
    campus = good_news["columns"]["campus"][0]
    good_news["columns"]["campus"] = [dict(campus, headline=f"Campus {i}") for i in range(campus_items)]
    ctx = build.build_context(good_news, good_pinned)
    assert [c["key"] for c in ctx["columns"]] == ["models", "tools", "campus"]
    html = build.render(good_news, good_pinned)
    columns = html[html.index('<div class="columns">'):html.index("</main>")]
    assert columns.count('<section class="column"') == 3
    assert '<h2 id="col-campus">On campus</h2>' in columns
    empty = '<p class="empty">No new campus AI news this week</p>'
    assert (empty in columns) is (campus_items == 0)
    assert "Studio hours" not in columns and "Help desk" not in columns


def test_three_equal_columns_in_css():
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    rule = css[css.index(".columns {"):]
    assert "grid-template-columns: repeat(3, minmax(0, 1fr));" in rule[:rule.index("}")]


def test_pinned_items_go_to_the_studio_panel(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    panel = html[html.index('<aside class="studio"'):html.index("</aside>")]
    # The hours item becomes the status badge and hours line; other pinned items are notes.
    assert 'id="studio-status"' in panel
    assert "Mon to Thu 11am to 6pm, Fri 11am to 5pm" in panel
    help_desk = good_pinned[1]
    assert f'<span class="note-title">{help_desk["headline"]}.</span> {help_desk["summary"]}' in panel
    assert "Studio hours" not in panel


@pytest.mark.parametrize(
    "hours, text",
    [
        ({"mon": ["11:00", "18:00"], "tue": ["11:00", "18:00"], "wed": ["11:00", "18:00"],
          "thu": ["11:00", "18:00"], "fri": ["11:00", "17:00"], "sat": None, "sun": None},
         "Mon to Thu 11am to 6pm, Fri 11am to 5pm"),
        ({"mon": ["09:30", "12:00"], "tue": None, "wed": ["09:30", "12:00"], "thu": None,
          "fri": None, "sat": None, "sun": ["00:00", "23:59"]},
         "Mon 9:30am to 12pm, Wed 9:30am to 12pm, Sun 12am to 11:59pm"),
        ({k: None for k in ("mon", "tue", "wed", "thu", "fri", "sat", "sun")}, ""),
    ],
)
def test_format_hours(hours, text):
    assert build.format_hours(hours) == text


def test_studio_panel(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    panel = html[html.index('<aside class="studio"'):html.index("</aside>")]
    assert '<h2 id="studio-title">What you can do here</h2>' in panel
    for offer in ("Use local LLMs", "Talk to an AI specialist", "Attend workshops and events", "Plan an AI challenge"):
        assert f"<li>{offer}</li>" in panel
    assert "Room 212, Weaver Science-Engineering Library" in panel
    assert "lbry-aistudio@arizona.edu" in panel
    assert "<figcaption>Scan to visit the Studio</figcaption>" in panel
    assert str(build.qr_svg("https://lib.arizona.edu/study/ai-studio", "lib.arizona.edu")) in panel
    # Nothing in the panel looks clickable.
    assert "<a " not in panel and "<button" not in panel


def test_panel_image_is_cropped_not_stretched(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    poster = build.poster_info()
    assert poster is not None
    assert f'<img src="img/studio-art.webp" width="{poster["width"]}" height="{poster["height"]}"' in html
    css = (ROOT / "static" / "style.css").read_text(encoding="utf-8")
    rule = css[css.index(".studio-art img {"):]
    rule = rule[:rule.index("}")]
    assert "object-fit: cover" in rule and "saturate(0.7) brightness(0.9)" in rule
    blend = css[css.index(".studio-art::after {"):]
    blend = blend[:blend.index("}")]
    assert "rgba(12, 35, 75, 0.55) 0%, rgba(12, 35, 75, 0) 25%" in blend
    assert "rgba(12, 35, 75, 0.9) 0%, rgba(12, 35, 75, 0) 40%" in blend


def test_poster_crop_is_inside_the_poster_and_keeps_its_aspect():
    with Image.open(build.POSTER_SOURCE) as image:
        width, height = image.size
    left, top, right, bottom = build.POSTER_CROP
    assert 0 <= left < right <= width and 0 <= top < bottom <= height
    info = build.poster_info()
    assert info["width"] == build.POSTER_WIDTH == 1382
    assert abs(info["width"] / info["height"] - (right - left) / (bottom - top)) < 0.01


def test_studio_art_is_used_whole_when_present(monkeypatch, tmp_path):
    art = tmp_path / "studio-art.png"
    Image.new("RGB", (2400, 1600), (40, 80, 120)).save(art)
    monkeypatch.setattr(build, "ART_SOURCE", art)
    assert build.art_source() == (art, None)
    assert build.poster_info() == {"src": "img/studio-art.webp", "width": 1382, "height": 921}
    out = tmp_path / "out.webp"
    build.write_poster(art, out)
    with Image.open(out) as image:
        assert image.size == (1382, 921)


def test_poster_is_cropped_when_there_is_no_studio_art(monkeypatch, tmp_path):
    monkeypatch.setattr(build, "ART_SOURCE", tmp_path / "missing.png")
    assert build.art_source() == (build.POSTER_SOURCE, build.POSTER_CROP)


def test_no_poster_means_no_image(good_news, good_pinned, monkeypatch, tmp_path):
    monkeypatch.setattr(build, "ART_SOURCE", tmp_path / "missing-art.png")
    monkeypatch.setattr(build, "POSTER_SOURCE", tmp_path / "missing.png")
    assert build.poster_info() is None
    html = build.render(good_news, good_pinned)
    assert "<img" not in html and "What you can do here" in html


def test_write_poster_stays_under_the_limit(tmp_path):
    out = tmp_path / "poster.webp"
    size = build.write_poster(build.POSTER_SOURCE, out, build.POSTER_CROP)
    assert build.POSTER_MAX_BYTES == 500_000
    assert size == out.stat().st_size <= build.POSTER_MAX_BYTES
    with Image.open(out) as image:
        assert image.format == "WEBP"
        assert image.size == (build.poster_info()["width"], build.poster_info()["height"])
    # A tight limit makes the build lower the quality, then the size, until it fits.
    small = build.write_poster(build.POSTER_SOURCE, out, build.POSTER_CROP, max_bytes=8_000)
    assert small <= 8_000


def test_stress_fixture_renders_three_pages_per_column(good_pinned):
    news = load_fixture("stress_max.json")
    for column in news["columns"].values():
        assert len(column) == 5
        assert all(len(i["headline"]) == 70 and len(i["summary"]) == 160 for i in column)
    html = build.render(news, good_pinned)
    assert html.count('<span class="page-count">1 of 3</span>') == 3
    assert html.count('class="items page') == 9


@pytest.mark.parametrize("count, sizes", [(0, []), (1, [1]), (2, [2]), (3, [2, 1]), (4, [2, 2]), (5, [2, 2, 1])])
def test_paginate_splits_items_into_pages_of_two(count, sizes):
    items = list(range(count))
    pages = build.paginate(items)
    assert [len(page) for page in pages] == sizes
    assert [i for page in pages for i in page] == items


def column_html(html: str, key: str) -> str:
    start = html.index(f'aria-labelledby="col-{key}"')
    return html[start:html.index("</section>", start)]


@pytest.mark.parametrize("count, pages", [(1, 1), (2, 1), (3, 2), (4, 2), (5, 3)])
def test_page_counter_only_with_more_than_one_page(good_news, good_pinned, count, pages):
    item = good_news["columns"]["models"][0]
    good_news["columns"]["models"] = [dict(item, url=f"https://www.anthropic.com/news/p{i}") for i in range(count)]
    column = column_html(build.render(good_news, good_pinned), "models")
    assert column.count('class="items page') == pages
    if pages == 1:
        assert "page-foot" not in column and "page-count" not in column
    else:
        assert f'<span class="page-count">1 of {pages}</span>' in column
        assert column.count('<li class="dot') == pages


def test_only_the_first_page_is_active_without_javascript(good_news, good_pinned):
    item = good_news["columns"]["models"][0]
    good_news["columns"]["models"] = [dict(item, url=f"https://www.anthropic.com/news/p{i}") for i in range(5)]
    column = column_html(build.render(good_news, good_pinned), "models")
    assert column.count('class="items page is-active"') == 1
    assert column.count('class="items page" aria-hidden="true"') == 2
    assert column.index('class="items page is-active"') < column.index('class="items page" aria-hidden')


def test_html_is_escaped(good_news, good_pinned):
    good_news["columns"]["models"][0]["headline"] = "<script>alert(1)</script>"
    html = build.render(good_news, good_pinned)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_main_writes_site(tmp_path, monkeypatch):
    monkeypatch.setattr(build, "SITE_DIR", tmp_path / "site")
    assert build.main([]) == 0
    assert (tmp_path / "site" / "index.html").is_file()
    assert (tmp_path / "site" / "style.css").is_file()
    poster = tmp_path / "site" / "img" / "studio-art.webp"
    assert 0 < poster.stat().st_size <= build.POSTER_MAX_BYTES
    assert BANNER not in (tmp_path / "site" / "index.html").read_text(encoding="utf-8")


def test_live_build_has_no_preview_banner(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    assert BANNER not in html
    assert "preview-banner" not in html


def test_preview_build_has_banner_and_noindex(good_news, good_pinned):
    html = build.render(good_news, good_pinned, preview=True)
    assert BANNER in html
    assert '<meta name="robots" content="noindex">' in html
    # The banner comes before the page title so it is the first thing on screen.
    assert html.index(BANNER) < html.index("<h1>Latest AI News</h1>")


def test_preview_cli_uses_data_dir_and_out(tmp_path):
    data_dir = tmp_path / "dev" / "data"
    data_dir.mkdir(parents=True)
    news = load_fixture("good.json")
    news["columns"]["models"][0]["headline"] = "Headline only on the dev branch"
    (data_dir / "news.json").write_text(json.dumps(news), encoding="utf-8")
    (data_dir / "pinned.json").write_text(json.dumps(load_fixture("pinned_good.json")), encoding="utf-8")
    out = tmp_path / "site" / "dev"

    assert build.main(["--preview", "--data-dir", str(data_dir), "--out", str(out)]) == 0
    html = (out / "index.html").read_text(encoding="utf-8")
    assert BANNER in html
    assert '<meta name="robots" content="noindex">' in html
    assert "Headline only on the dev branch" in html
    assert (out / "style.css").is_file()
    assert (out / "img" / "studio-art.webp").is_file()
