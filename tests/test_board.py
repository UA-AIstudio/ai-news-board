"""Tests for the live TV page: studio hours, NEW tags, ticker, spotlight, QR codes.

The hours and NEW tag logic runs in the browser (static/board.js), so those
tests call it with Node.js. GitHub's ubuntu-latest runners include Node.
"""

import json
import re
import shutil
import subprocess

import pytest

import build
import validate
from conftest import FIXTURE_NOW, ROOT, load_fixture

EM_DASH = chr(0x2014)
BOARD_JS = ROOT / "static" / "board.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="Node.js is not installed")

STUDIO_HOURS = json.loads((ROOT / "data" / "pinned.json").read_text(encoding="utf-8"))[0]["hours"]


def run_board(expression: str, **values):
    """Evaluate a JS expression with board.js loaded as `board`; return its JSON value."""
    script = (
        "const board = require(process.argv[1]);"
        "const v = JSON.parse(process.argv[2]);"
        f"process.stdout.write(JSON.stringify({expression}));"
    )
    result = subprocess.run(
        [NODE, "-e", script, str(BOARD_JS), json.dumps(values)],
        capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout)


def status_at(arizona_time: str):
    """Studio status at an Arizona wall-clock time like '2026-10-05T12:00'."""
    return run_board(
        "board.studioStatus(v.hours, Date.parse(v.at + ':00-07:00'))",
        hours=STUDIO_HOURS, at=arizona_time,
    )


# October 5, 2026 is a Monday; October 9 is a Friday.

@needs_node
@pytest.mark.parametrize(
    "at, is_open, text",
    [
        ("2026-10-05T12:00", True, "Open now, until 6pm"),
        ("2026-10-05T11:00", True, "Open now, until 6pm"),
        ("2026-10-05T10:59", False, "Closed, opens today 11am"),
        ("2026-10-05T00:30", False, "Closed, opens today 11am"),
        ("2026-10-05T17:59", True, "Open now, until 6pm"),
        ("2026-10-05T18:00", False, "Closed, opens Tuesday 11am"),
        ("2026-10-08T19:00", False, "Closed, opens Friday 11am"),
        ("2026-10-09T16:59", True, "Open now, until 5pm"),
        ("2026-10-09T17:00", False, "Closed, opens Monday 11am"),
        ("2026-10-10T12:00", False, "Closed, opens Monday 11am"),
        ("2026-10-11T23:59", False, "Closed, opens Monday 11am"),
    ],
)
def test_studio_status(at, is_open, text):
    assert status_at(at) == {"open": is_open, "text": text}


THANKSGIVING = [
    {"date": "2026-11-26", "note": "Thanksgiving"},
    {"date": "2026-11-27", "note": "Thanksgiving break"},
]


def closure_status_at(arizona_time: str, closures):
    return run_board(
        "board.studioStatus(v.hours, Date.parse(v.at + ':00-07:00'), v.closures)",
        hours=STUDIO_HOURS, at=arizona_time, closures=closures,
    )


# November 26, 2026 is a Thursday.

@needs_node
@pytest.mark.parametrize(
    "at, text",
    [
        ("2026-11-26T12:00", "Closed today, Thanksgiving"),        # during normal hours
        ("2026-11-26T08:00", "Closed today, Thanksgiving"),        # before opening
        ("2026-11-27T16:00", "Closed today, Thanksgiving break"),
        ("2026-11-25T19:00", "Closed, opens Monday 11am"),         # skips both closed days
        ("2026-11-25T09:00", "Closed, opens today 11am"),          # day before is normal
        ("2026-11-28T12:00", "Closed, opens Monday 11am"),         # weekend after
    ],
)
def test_studio_status_with_closures(at, text):
    assert closure_status_at(at, THANKSGIVING) == {"open": False, "text": text}


@needs_node
def test_closure_on_a_weekend_shows_the_note():
    status = closure_status_at("2026-11-28T12:00", [{"date": "2026-11-28", "note": "Building maintenance"}])
    assert status == {"open": False, "text": "Closed today, Building maintenance"}


@needs_node
def test_long_closure_names_the_reopening_date():
    winter = [{"date": f"2026-12-{d:02d}", "note": "Winter break"} for d in range(14, 32)]
    assert closure_status_at("2026-12-11T19:00", winter) == {
        "open": False, "text": "Closed, opens January 1 11am",
    }


@needs_node
def test_closures_do_not_affect_other_days():
    assert closure_status_at("2026-11-24T12:00", THANKSGIVING) == {"open": True, "text": "Open now, until 6pm"}


@needs_node
def test_arizona_date():
    # 01:00 UTC on October 6 is still October 5 in Arizona.
    parts = run_board("board.arizonaParts(Date.parse('2026-10-06T01:00:00Z'))")
    assert parts == {"date": "2026-10-05", "day": 1, "minutes": 18 * 60}


@needs_node
def test_studio_status_uses_arizona_time():
    # 01:00 UTC on Tuesday is 6:00 pm Monday in Arizona: just closed.
    status = run_board("board.studioStatus(v.hours, Date.parse('2026-10-06T01:00:00Z'))", hours=STUDIO_HOURS)
    assert status == {"open": False, "text": "Closed, opens Tuesday 11am"}


@needs_node
def test_studio_status_without_hours():
    assert run_board("board.studioStatus(null, Date.now())") is None


@needs_node
def test_format_hour():
    assert run_board("[1080, 1020, 660, 690, 720, 0].map(board.formatHour)") == [
        "6pm", "5pm", "11am", "11:30am", "12pm", "12am",
    ]


@needs_node
@pytest.mark.parametrize(
    "item_date, now, expected",
    [
        ("2026-10-02", "2026-10-04T00:00:00.000-07:00", True),   # exactly 48 hours
        ("2026-10-02", "2026-10-04T00:00:00.001-07:00", False),  # 48 hours and 1 ms
        ("2026-10-03", "2026-10-04T23:59:59.999-07:00", True),
        ("2026-10-04", "2026-10-04T08:00:00.000-07:00", True),
        ("2026-09-30", "2026-10-04T08:00:00.000-07:00", False),
        ("not-a-date", "2026-10-04T08:00:00.000-07:00", False),
    ],
)
def test_new_tag_boundary(item_date, now, expected):
    assert run_board("board.isNew(v.date, Date.parse(v.now))", date=item_date, now=now) is expected


def test_board_js_is_safe_to_inline():
    text = BOARD_JS.read_text(encoding="utf-8")
    assert "</script" not in text.lower()
    assert EM_DASH not in text


def test_ticker_includes_every_headline_twice(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    ticker = html[html.index('<div class="ticker"'):html.index('<footer')]
    headlines = [i["headline"] for col in good_news["columns"].values() for i in col]
    for headline in headlines:
        assert ticker.count(f'<span class="ticker-item">{headline}</span>') == 2, headline
    # Pinned items are Studio information, not news, so they stay out of the ticker.
    for pinned in good_pinned:
        assert pinned["headline"] not in ticker


def test_spotlight_has_models_and_tools_newest_first(good_news, good_pinned):
    spotlight = build.build_context(good_news, good_pinned)["spotlight"]
    expected = good_news["columns"]["models"] + good_news["columns"]["tools"]
    assert {s["url"] for s in spotlight} == {i["url"] for i in expected}
    dates = [s["iso_date"] for s in spotlight]
    assert dates == sorted(dates, reverse=True)
    assert all(s["qr"].startswith("<svg") for s in spotlight)


def test_columns_still_list_every_item(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    columns = html[html.index('<div class="columns">'):html.index("</main>")]
    for col in good_news["columns"].values():
        for item in col:
            assert f'href="{item["url"]}">{item["headline"]}</a>' in columns


def test_page_has_live_hooks_and_no_em_dash(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    assert 'id="clock"' in html and 'id="studio-status"' in html and 'id="studio-hours"' in html
    # One QR per spotlight slide, plus the Studio QR in the panel.
    assert html.count("<svg") == len(good_news["columns"]["models"]) + len(good_news["columns"]["tools"]) + 1
    assert '<meta name="theme-color" content="#0C234B">' in html
    assert 'cache: "no-store"' in html and "response.ok" in html
    assert EM_DASH not in html


def test_closures_are_passed_to_the_page(good_news, good_pinned):
    good_pinned[0]["closures"] = THANKSGIVING
    html = build.render(good_news, good_pinned)
    data = html[html.index('id="studio-hours">') + len('id="studio-hours">'):]
    data = json.loads(data[:data.index("</script>")])
    assert data["hours"] == good_pinned[0]["hours"]
    assert data["closures"] == THANKSGIVING


def test_no_hours_means_no_status_badge(good_news, good_pinned):
    for p in good_pinned:
        p.pop("hours", None)
    html = build.render(good_news, good_pinned)
    assert 'id="studio-status"' not in html and 'id="studio-hours"' not in html


def _dark_modules_in_svg(svg: str) -> int:
    path = re.search(r'<path fill="#0C234B" d="([^"]*)"', svg).group(1)
    return sum(int(w) for w in re.findall(r"h(\d+)v1", path))


@pytest.mark.parametrize(
    "url",
    ["https://lib.arizona.edu/study/ai-studio", "https://example.org/" + "x" * 300],
)
def test_qr_svg_draws_every_module_with_quiet_zone(url):
    matrix = build.qr_matrix(url)
    size = len(matrix)
    assert size >= 21 and (size - 17) % 4 == 0
    svg = str(build.qr_svg(url, "example"))
    total = size + 2 * build.QR_QUIET_ZONE
    assert f'viewBox="0 0 {total} {total}"' in svg
    assert f'<rect width="{total}" height="{total}" fill="#FFFFFF"/>' in svg
    assert _dark_modules_in_svg(svg) == sum(sum(row) for row in matrix)
    # Finder pattern at the top left, offset by the quiet zone.
    assert all(matrix[0][x] for x in range(7))


def test_qr_svg_escapes_label():
    svg = str(build.qr_svg("https://example.org/", '<b>"x"</b>'))
    assert "<b>" not in svg and "&lt;b&gt;" in svg


def test_every_slide_has_a_captioned_qr(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    slides = len(good_news["columns"]["models"]) + len(good_news["columns"]["tools"])
    assert html.count('<figure class="slide-qr">') == slides
    assert html.count("<figcaption>Scan to read the source</figcaption>") == slides


def test_pinned_hours_schema(good_news, good_pinned):
    good_pinned[0]["hours"] = dict(STUDIO_HOURS)
    assert validate.validate(good_news, good_pinned, now=FIXTURE_NOW) == []
    good_pinned[0]["hours"]["mon"] = ["11:00", "25:00"]
    assert validate.validate(good_news, good_pinned, now=FIXTURE_NOW)
    good_pinned[0]["hours"] = {"mon": None}
    assert any("required" in e for e in validate.validate(good_news, good_pinned, now=FIXTURE_NOW))


@pytest.mark.parametrize(
    "closures, expected",
    [
        ([{"date": "2026-11-26", "note": "x" * 40}], None),
        ([], None),
        ([{"date": "2026-11-26", "note": "x" * 41}], "is too long"),
        ([{"date": "2026-11-26", "note": ""}], "should be non-empty"),
        ([{"date": "2026-11-26"}], "'note' is a required property"),
        ([{"date": "2026-11-26", "note": "Holiday", "hours": "none"}], "Additional properties"),
        ([{"date": "2026-13-01", "note": "Holiday"}], "does not match"),
        ([{"date": "11/26/2026", "note": "Holiday"}], "does not match"),
        ([{"date": "2026-02-30", "note": "Holiday"}], "not a real date"),
        ([{"date": "2026-11-26", "note": "A"}, {"date": "2026-11-26", "note": "B"}], "listed more than once"),
        ([{"date": "2026-11-26", "note": f"Closed {EM_DASH} holiday"}], "em dash"),
        ({"date": "2026-11-26", "note": "Holiday"}, "is not of type 'array'"),
    ],
)
def test_closures_schema(good_news, good_pinned, closures, expected):
    good_pinned[0]["closures"] = closures
    errors = validate.validate(good_news, good_pinned, now=FIXTURE_NOW)
    if expected is None:
        assert errors == []
    else:
        assert any(expected in e for e in errors), errors
