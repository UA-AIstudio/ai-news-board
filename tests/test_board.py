"""Tests for the live TV page: studio hours, NEW tags, ticker, spotlight, QR codes.

The hours and NEW tag logic runs in the browser (static/board.js), so those
tests call it with Node.js. GitHub's ubuntu-latest runners include Node.
"""

import hashlib
import json
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
    headlines += [p["headline"] for p in good_pinned]
    for headline in headlines:
        assert ticker.count(f'<span class="ticker-item">{headline}</span>') == 2, headline


def test_spotlight_has_models_and_tools_newest_first(good_news, good_pinned):
    spotlight = build.build_context(good_news, good_pinned)["spotlight"]
    expected = good_news["columns"]["models"] + good_news["columns"]["tools"]
    assert {s["url"] for s in spotlight} == {i["url"] for i in expected}
    dates = [s["iso_date"] for s in spotlight]
    assert dates == sorted(dates, reverse=True)
    assert all(s["qr"].startswith("<svg") for s in spotlight)


def test_columns_still_list_every_item(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    columns = html[html.index('<main class="columns">'):html.index("</main>")]
    for col in good_news["columns"].values():
        for item in col:
            assert f'href="{item["url"]}">{item["headline"]}</a>' in columns


def test_page_has_live_hooks_and_no_em_dash(good_news, good_pinned):
    html = build.render(good_news, good_pinned)
    assert 'id="clock"' in html and 'id="studio-status"' in html and 'id="studio-hours"' in html
    assert html.count("<svg") == len(good_news["columns"]["models"]) + len(good_news["columns"]["tools"])
    assert '<meta name="theme-color" content="#0C234B">' in html
    assert 'cache: "no-store"' in html and "response.ok" in html
    assert EM_DASH not in html


def test_no_hours_means_no_status_badge(good_news, good_pinned):
    for p in good_pinned:
        p.pop("hours", None)
    html = build.render(good_news, good_pinned)
    assert 'id="studio-status"' not in html and 'id="studio-hours"' not in html


def _digest(matrix):
    return hashlib.sha256("".join("1" if c else "0" for row in matrix for c in row).encode()).hexdigest()[:16]


@pytest.mark.parametrize(
    "text, mask, size, digest",
    [
        # Reference digests from the python-qrcode library (level M, byte mode).
        ("https://lib.arizona.edu/study/ai-studio", 2, 29, "cebe1949b1d1937e"),
        ("https://example.org/" + "x" * 180, 5, 57, "63550de6aea688d6"),
    ],
)
def test_qr_matches_reference(text, mask, size, digest):
    matrix = build.qr_matrix(text, mask=mask)
    assert len(matrix) == size
    assert _digest(matrix) == digest


def test_qr_too_long_raises():
    with pytest.raises(ValueError):
        build.qr_matrix("https://example.org/" + "x" * 300)


def test_pinned_hours_schema(good_news, good_pinned):
    good_pinned[0]["hours"] = dict(STUDIO_HOURS)
    assert validate.validate(good_news, good_pinned, now=FIXTURE_NOW) == []
    good_pinned[0]["hours"]["mon"] = ["11:00", "25:00"]
    assert validate.validate(good_news, good_pinned, now=FIXTURE_NOW)
    good_pinned[0]["hours"] = {"mon": None}
    assert any("required" in e for e in validate.validate(good_news, good_pinned, now=FIXTURE_NOW))
