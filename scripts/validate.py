#!/usr/bin/env python3
"""Validate data/news.json and data/pinned.json for the Latest AI News board.

Used by the daily Routine before it opens a pull request, and by CI.
Prints every problem it finds and exits 1 if there are any.

Usage:
    python scripts/validate.py
    python scripts/validate.py --routine-pr origin/main

Items older than 14 days are errors only with --routine-pr (the daily news
update). In every other run (design pull requests, deploys) they are printed as
warnings, so stale news never blocks a code change or a deploy.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parent.parent
NEWS_PATH = ROOT / "data" / "news.json"
PINNED_PATH = ROOT / "data" / "pinned.json"
SCHEMA_PATH = ROOT / "schema" / "news.schema.json"

TZ = ZoneInfo("America/Phoenix")
MAX_AGE_DAYS = 14
MAX_HEADLINE = 70
MAX_SUMMARY = 160
EM_DASH = "\u2014"

# The only sites news items may link to. A host passes if it equals one of
# these or is a subdomain of one. Keep in sync with the Routine environment.
ALLOWED_DOMAINS = (
    "anthropic.com",
    "openai.com",
    "blog.google",
    "deepmind.google",
    "ai.meta.com",
    "huggingface.co",
    "arxiv.org",
    "github.com",
    "responsibleai.arizona.edu",
    "arizona.edu",
    "lib.arizona.edu",
    "news.arizona.edu",
)

# The only file a Routine pull request may change.
ROUTINE_ALLOWED_FILES = {"data/news.json"}


def load_json(path: Path) -> tuple[object | None, list[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), []
    except FileNotFoundError:
        return None, [f"{path.name}: file not found at {path}"]
    except json.JSONDecodeError as exc:
        return None, [f"{path.name}: not valid JSON ({exc})"]


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _location(path) -> str:
    parts = []
    for p in path:
        parts.append(f"[{p}]" if isinstance(p, int) else (f".{p}" if parts else str(p)))
    return "".join(parts) or "(top level)"


def check_schema(data: object, schema: dict, label: str) -> list[str]:
    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.absolute_path))
    return [f"{label} {_location(e.absolute_path)}: {e.message}" for e in errors]


def iter_items(news: dict):
    """Yield (location, item) for every news item that looks like a dict."""
    columns = news.get("columns") if isinstance(news, dict) else None
    if not isinstance(columns, dict):
        return
    for column, items in columns.items():
        if not isinstance(items, list):
            continue
        for i, item in enumerate(items):
            if isinstance(item, dict):
                yield f"columns.{column}[{i}]", item


def host_allowed(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower().rstrip(".")
    return any(host == d or host.endswith("." + d) for d in ALLOWED_DOMAINS)


def check_urls(items, label: str) -> list[str]:
    errors = []
    for loc, item in items:
        url = item.get("url")
        if isinstance(url, str) and not host_allowed(url):
            errors.append(
                f"{label} {loc}.url: host of {url!r} is not on the allowlist "
                f"({', '.join(ALLOWED_DOMAINS)})"
            )
    return errors


def check_dates(news: dict, today: date) -> tuple[list[str], list[str]]:
    """Return (errors, stale): bad or future dates, and items older than 14 days."""
    errors, stale = [], []
    oldest = today - timedelta(days=MAX_AGE_DAYS)
    for loc, item in iter_items(news):
        raw = item.get("date")
        if not isinstance(raw, str):
            continue
        try:
            d = date.fromisoformat(raw)
        except ValueError:
            errors.append(f"news.json {loc}.date: {raw!r} is not a real date (YYYY-MM-DD)")
            continue
        if d > today:
            errors.append(f"news.json {loc}.date: {raw} is in the future (today is {today} in Arizona)")
        elif d < oldest:
            stale.append(
                f"news.json {loc}.date: {raw} is older than {MAX_AGE_DAYS} days "
                f"(oldest allowed is {oldest})"
            )
    return errors, stale


def check_updated(news: dict, now: datetime) -> list[str]:
    raw = news.get("updated") if isinstance(news, dict) else None
    if not isinstance(raw, str):
        return []
    try:
        stamp = datetime.fromisoformat(raw)
    except ValueError:
        return [f"news.json updated: {raw!r} is not a valid ISO 8601 timestamp"]
    if stamp.tzinfo is None:
        return [f"news.json updated: {raw!r} has no UTC offset"]
    errors = []
    if stamp.utcoffset() != timedelta(hours=-7):
        errors.append(f"news.json updated: {raw!r} must use the America/Phoenix offset -07:00")
    if stamp > now + timedelta(minutes=10):
        errors.append(f"news.json updated: {raw} is in the future")
    return errors


def check_lengths(items, label: str) -> list[str]:
    errors = []
    for loc, item in items:
        for field, limit in (("headline", MAX_HEADLINE), ("summary", MAX_SUMMARY)):
            text = item.get(field)
            if isinstance(text, str) and len(text) > limit:
                errors.append(
                    f"{label} {loc}.{field}: {len(text)} characters, must be {limit} or fewer"
                )
    return errors


def check_closures(pinned_items) -> list[str]:
    """Closure dates must be real calendar dates and not repeat."""
    errors = []
    for loc, item in pinned_items:
        closures = item.get("closures")
        if not isinstance(closures, list):
            continue
        seen = set()
        for i, closure in enumerate(closures):
            raw = closure.get("date") if isinstance(closure, dict) else None
            if not isinstance(raw, str):
                continue
            try:
                date.fromisoformat(raw)
            except ValueError:
                errors.append(f"pinned.json {loc}.closures[{i}].date: {raw!r} is not a real date (YYYY-MM-DD)")
                continue
            if raw in seen:
                errors.append(f"pinned.json {loc}.closures[{i}].date: {raw} is listed more than once")
            seen.add(raw)
    return errors


def check_em_dashes(value: object, label: str, loc: str = "") -> list[str]:
    errors = []
    if isinstance(value, str):
        if EM_DASH in value:
            errors.append(f"{label} {loc or '(top level)'}: contains an em dash (U+2014): {value!r}")
    elif isinstance(value, dict):
        for key, sub in value.items():
            sub_loc = f"{loc}.{key}" if loc else str(key)
            errors += check_em_dashes(key, label, sub_loc + " (key)")
            errors += check_em_dashes(sub, label, sub_loc)
    elif isinstance(value, list):
        for i, sub in enumerate(value):
            errors += check_em_dashes(sub, label, f"{loc}[{i}]")
    return errors


def check_duplicate_urls(news: dict) -> list[str]:
    errors = []
    seen: dict[str, str] = {}
    for loc, item in iter_items(news):
        url = item.get("url")
        if not isinstance(url, str):
            continue
        key = url.rstrip("/")
        if key in seen:
            errors.append(f"news.json {loc}.url: duplicate of {seen[key]} ({url})")
        else:
            seen[key] = loc
    return errors


def changed_files(base_ref: str, cwd: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--name-only", f"{base_ref}...HEAD"],
        cwd=cwd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"git diff against {base_ref} failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def check_routine_pr(base_ref: str, cwd: Path = ROOT) -> list[str]:
    try:
        files = changed_files(base_ref, cwd)
    except (RuntimeError, OSError) as exc:
        return [f"routine PR check: could not list changed files against {base_ref}: {exc}"]
    errors = [
        f"routine PR check: {f} was changed, but a Routine pull request may only change data/news.json"
        for f in files
        if f not in ROUTINE_ALLOWED_FILES
    ]
    return errors


def run_checks(
    news: object, pinned: object, now: datetime | None = None
) -> tuple[list[str], list[str]]:
    """Run every content check. Return (errors, stale), where stale lists items
    older than 14 days; the caller decides whether those are errors or warnings."""
    now = now or datetime.now(TZ)
    today = now.astimezone(TZ).date()
    schema = load_schema()
    pinned_schema = {**schema, "$ref": "#/$defs/pinned"}
    for key in ("type", "required", "properties", "additionalProperties"):
        pinned_schema.pop(key, None)

    errors = check_schema(news, schema, "news.json")
    errors += check_schema(pinned, pinned_schema, "pinned.json")
    stale: list[str] = []

    if isinstance(news, dict):
        items = list(iter_items(news))
        errors += check_urls(items, "news.json")
        date_errors, stale = check_dates(news, today)
        errors += date_errors
        errors += check_updated(news, now)
        errors += check_lengths(items, "news.json")
        errors += check_duplicate_urls(news)
    if isinstance(pinned, list):
        pinned_items = [(f"[{i}]", p) for i, p in enumerate(pinned) if isinstance(p, dict)]
        errors += check_urls(pinned_items, "pinned.json")
        errors += check_lengths(pinned_items, "pinned.json")
        errors += check_closures(pinned_items)

    errors += check_em_dashes(news, "news.json")
    errors += check_em_dashes(pinned, "pinned.json")

    # The schema and the explicit checks can report the same problem; keep one copy.
    return list(dict.fromkeys(errors)), stale


def validate(
    news: object, pinned: object, now: datetime | None = None, stale_is_error: bool = True
) -> list[str]:
    """Return error messages. With stale_is_error=False, items older than 14 days pass."""
    errors, stale = run_checks(news, pinned, now)
    return errors + stale if stale_is_error else errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--news", type=Path, default=NEWS_PATH, help="path to news.json")
    parser.add_argument("--pinned", type=Path, default=PINNED_PATH, help="path to pinned.json")
    parser.add_argument(
        "--routine-pr",
        metavar="BASE_REF",
        help=(
            "Routine mode: fail if any file other than data/news.json differs from "
            "BASE_REF, and treat items older than 14 days as errors"
        ),
    )
    args = parser.parse_args(argv)

    news, errors = load_json(args.news)
    pinned, pinned_errors = load_json(args.pinned)
    errors += pinned_errors
    stale: list[str] = []
    if not errors:
        errors, stale = run_checks(news, pinned)
    if args.routine_pr:
        errors += stale
        stale = []
        errors += check_routine_pr(args.routine_pr)

    if stale:
        print(
            f"Warning: {len(stale)} stale item(s). This is an error only with --routine-pr:",
            file=sys.stderr,
        )
        for w in stale:
            print(f"  - {w}", file=sys.stderr)
        if not errors:
            print(f"::warning title=Stale news::{len(stale)} item(s) older than {MAX_AGE_DAYS} days")
    if errors:
        print(f"Validation failed with {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
