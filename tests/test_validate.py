import json
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import validate
from conftest import FIXTURE_NOW, FIXTURES, ROOT, load_fixture

EM_DASH = chr(0x2014)


def errors_for(news, pinned):
    return validate.validate(news, pinned, now=FIXTURE_NOW)


def test_good_fixture_passes(good_news, good_pinned):
    assert errors_for(good_news, good_pinned) == []


@pytest.mark.parametrize(
    "fixture, expected",
    [
        ("bad_extra_key.json", "Additional properties are not allowed"),
        ("bad_host.json", "not on the allowlist"),
        ("bad_lookalike_host.json", "not on the allowlist"),
        ("bad_http.json", "not on the allowlist"),
        ("bad_old_date.json", "older than 14 days"),
        ("bad_future_date.json", "in the future"),
        ("bad_long_headline.json", "headline: 71 characters, must be 70 or fewer"),
        ("bad_long_summary.json", "summary: 161 characters, must be 160 or fewer"),
        ("bad_em_dash.json", "em dash"),
        ("bad_duplicate_url.json", "duplicate of"),
        ("bad_too_few_models.json", "columns.models"),
        ("bad_too_many_campus.json", "columns.campus"),
        ("bad_updated_offset.json", "-07:00"),
        ("bad_missing_date.json", "'date' is a required property"),
    ],
)
def test_bad_fixtures_fail(fixture, expected, good_pinned):
    errors = errors_for(load_fixture(fixture), good_pinned)
    assert errors, f"{fixture} should fail validation"
    assert any(expected in e for e in errors), errors


def test_date_boundaries(good_news, good_pinned):
    good_news["columns"]["models"][0]["date"] = "2026-06-01"  # exactly 14 days old
    good_news["columns"]["models"][1]["date"] = "2026-06-15"  # today
    assert errors_for(good_news, good_pinned) == []


def test_length_limits_are_inclusive(good_news, good_pinned):
    good_news["columns"]["models"][0]["headline"] = "h" * 70
    good_news["columns"]["models"][0]["summary"] = "s" * 159 + "."
    good_pinned[0]["headline"] = "p" * 70
    assert errors_for(good_news, good_pinned) == []


def test_pinned_length_limits(good_news, good_pinned):
    good_pinned[1]["summary"] = "s" * 161
    errors = errors_for(good_news, good_pinned)
    assert any(e.startswith("pinned.json") and "must be 160 or fewer" in e for e in errors)


def test_stale_items_are_errors_by_default(good_pinned):
    errors = errors_for(load_fixture("bad_old_date.json"), good_pinned)
    assert any("older than 14 days" in e for e in errors)


def test_stale_items_pass_when_not_strict(good_pinned):
    news = load_fixture("bad_old_date.json")
    assert validate.validate(news, good_pinned, now=FIXTURE_NOW, stale_is_error=False) == []
    errors, stale = validate.run_checks(news, good_pinned, now=FIXTURE_NOW)
    assert errors == []
    assert len(stale) == 1 and "older than 14 days" in stale[0]


def test_future_dates_fail_even_when_not_strict(good_pinned):
    news = load_fixture("bad_future_date.json")
    errors = validate.validate(news, good_pinned, now=FIXTURE_NOW, stale_is_error=False)
    assert any("in the future" in e for e in errors)


def test_today_uses_phoenix_time(good_news, good_pinned):
    # 03:00 UTC on June 16 is still June 15 in Arizona, so a June 16 item is in the future.
    now = datetime(2026, 6, 16, 3, 0, tzinfo=ZoneInfo("UTC"))
    good_news["columns"]["models"][0]["date"] = "2026-06-16"
    errors = validate.validate(good_news, good_pinned, now=now)
    assert any("in the future" in e for e in errors)


def test_invalid_calendar_date(good_news, good_pinned):
    good_news["columns"]["models"][0]["date"] = "2026-02-30"
    assert any("not a real date" in e for e in errors_for(good_news, good_pinned))


def test_updated_in_future(good_news, good_pinned):
    good_news["updated"] = "2026-06-15T12:00:00-07:00"
    assert any("updated" in e and "future" in e for e in errors_for(good_news, good_pinned))


def test_em_dash_in_pinned(good_news, good_pinned):
    good_pinned[0]["headline"] = f"Studio {EM_DASH} hours"
    errors = errors_for(good_news, good_pinned)
    assert any(e.startswith("pinned.json") and "em dash" in e for e in errors)


def test_pinned_rejects_date_and_bad_host(good_news, good_pinned):
    good_pinned[0]["date"] = "2026-06-15"
    good_pinned[1]["url"] = "https://example.org/hours"
    errors = errors_for(good_news, good_pinned)
    assert any("pinned.json" in e and "Additional properties" in e for e in errors)
    assert any("pinned.json" in e and "allowlist" in e for e in errors)


def test_pinned_may_repeat_urls(good_news, good_pinned):
    assert good_pinned[0]["url"] == good_pinned[1]["url"]
    assert errors_for(good_news, good_pinned) == []


@pytest.mark.parametrize(
    "url, ok",
    [
        ("https://anthropic.com/news", True),
        ("https://www.anthropic.com/news", True),
        ("https://lib.arizona.edu/study/ai-studio", True),
        ("https://some.dept.arizona.edu/page", True),
        ("https://ai.meta.com/blog/", True),
        ("https://meta.com/blog/", False),
        ("https://notanthropic.com/", False),
        ("https://anthropic.com.evil.net/", False),
        ("http://anthropic.com/", False),
        ("https://user@evil.net/anthropic.com", False),
    ],
)
def test_host_allowed(url, ok):
    assert validate.host_allowed(url) is ok


def test_cli_reports_errors_and_exits_1(tmp_path, good_pinned):
    pinned = tmp_path / "pinned.json"
    pinned.write_text(json.dumps(good_pinned))
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "validate.py"),
         "--news", str(FIXTURES / "bad_host.json"), "--pinned", str(pinned)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "not on the allowlist" in result.stderr


def _run_cli(*args):
    return subprocess.run(
        ["python", str(ROOT / "scripts" / "validate.py"), *args],
        capture_output=True, text=True, cwd=ROOT,
    )


def test_cli_stale_items_warn_and_pass(tmp_path, good_pinned):
    # good.json is dated June 2026, so every item is stale against the real clock.
    pinned = tmp_path / "pinned.json"
    pinned.write_text(json.dumps(good_pinned))
    result = _run_cli("--news", str(FIXTURES / "good.json"), "--pinned", str(pinned))
    assert result.returncode == 0, result.stderr
    assert "Warning: 7 stale item(s)" in result.stderr
    assert "Validation passed." in result.stdout


def test_cli_stale_items_fail_with_routine_pr(tmp_path, good_pinned):
    pinned = tmp_path / "pinned.json"
    pinned.write_text(json.dumps(good_pinned))
    # Comparing HEAD with itself changes no files, so only the freshness check can fail.
    result = _run_cli("--news", str(FIXTURES / "good.json"), "--pinned", str(pinned), "--routine-pr", "HEAD")
    assert result.returncode == 1
    assert "older than 14 days" in result.stderr
    assert "Warning" not in result.stderr


def test_cli_invalid_json(tmp_path):
    broken = tmp_path / "news.json"
    broken.write_text("{not json")
    result = subprocess.run(
        ["python", str(ROOT / "scripts" / "validate.py"), "--news", str(broken)],
        capture_output=True, text=True,
    )
    assert result.returncode == 1
    assert "not valid JSON" in result.stderr


def test_repository_data_is_well_formed():
    """The committed data passes every check as of its own "updated" time."""
    news = json.loads((ROOT / "data" / "news.json").read_text(encoding="utf-8"))
    pinned = json.loads((ROOT / "data" / "pinned.json").read_text(encoding="utf-8"))
    now = datetime.fromisoformat(news["updated"])
    assert validate.validate(news, pinned, now=now) == []


def _git(repo, *args):
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True,
                   env={"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
                        "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
                        "PATH": __import__("os").environ["PATH"]})


@pytest.fixture
def repo(tmp_path):
    _git(tmp_path, "init", "-q", "-b", "main")
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "news.json").write_text("{}")
    (tmp_path / "README.md").write_text("readme")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "base")
    _git(tmp_path, "checkout", "-q", "-b", "claude/news")
    return tmp_path


def test_routine_pr_only_news_passes(repo):
    (repo / "data" / "news.json").write_text('{"x": 1}')
    _git(repo, "commit", "-qam", "news")
    assert validate.check_routine_pr("main", cwd=repo) == []


def test_routine_pr_other_file_fails(repo):
    (repo / "data" / "news.json").write_text('{"x": 1}')
    (repo / "README.md").write_text("changed")
    _git(repo, "commit", "-qam", "news and readme")
    errors = validate.check_routine_pr("main", cwd=repo)
    assert len(errors) == 1 and "README.md" in errors[0]


def test_routine_pr_bad_base_ref(repo):
    errors = validate.check_routine_pr("no-such-branch", cwd=repo)
    assert errors and "could not list changed files" in errors[0]


def test_routine_pr_image_fails_with_its_own_message(repo):
    (repo / "static" / "img").mkdir(parents=True)
    (repo / "static" / "img" / "studio-poster.png").write_bytes(b"\x89PNG")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "image")
    errors = validate.check_routine_pr("main", cwd=repo)
    assert errors == [
        "routine PR check: static/img/studio-poster.png was changed, "
        "but only people add or change images in static/img/"
    ]


def test_ci_blocks_image_changes_on_claude_branches():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    step = ci[ci.index("- name: Check claude/ branch does not touch static/img/"):]
    step = step[:step.index("\n      - name:", 1)]
    assert "if: startsWith(github.head_ref, 'claude/')" in step
    assert "-- static/img/" in step and "exit 1" in step
    # It runs before the tests, so it is the first failure reported.
    assert ci.index("does not touch static/img/") < ci.index("- name: Run tests")


def test_stress_fixture_passes(good_pinned):
    """Five items per column at the maximum lengths, used for layout checks."""
    assert validate.validate(load_fixture("stress_max.json"), good_pinned, now=FIXTURE_NOW) == []
