#!/usr/bin/env python3
"""Validate data/news.json and data/pinned.json for the Latest AI News board.

Used by the daily Routine before it opens a pull request, and by CI.
Prints every problem it finds and exits 1 if there are any.

Usage:
    python scripts/validate.py
    python scripts/validate.py --routine-pr origin/main
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
MAX_HEADLINE = 89
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


def check_dates(news: dict, today: date) -> list[str]:
    errors = []
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
            errors.append(
                f"news.json {loc}.date: {raw} is older than {MAX_AGE_DAYS} days "
                f"(oldest allowed is {oldest})"
            )
    return errors


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


def check_headlines(items, label: str) -> list[str]:
    errors = []
    for loc, item in items:
        headline = item.get("headline")
        if isinstance(headline, str) and len(headline) > MAX_HEADLINE:
            errors.append(
                f"{label} {loc}.headline: {len(headline)} characters, must be under 90"
            )
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


def validate(news: object, pinned: object, now: datetime | None = None) -> list[str]:
    """Run every content check and return a list of error messages."""
    now = now or datetime.now(TZ)
    today = now.astimezone(TZ).date()
    schema = load_schema()
    pinned_schema = {**schema, "$ref": "#/$defs/pinned"}
    for key in ("type", "required", "properties", "additionalProperties"):
        pinned_schema.pop(key, None)

    errors = check_schema(news, schema, "news.json")
    errors += check_schema(pinned, pinned_schema, "pinned.json")

    if isinstance(news, dict):
        items = list(iter_items(news))
        errors += check_urls(items, "news.json")
        errors += check_dates(news, today)
        errors += check_updated(news, now)
        errors += check_headlines(items, "news.json")
        errors += check_duplicate_urls(news)
    if isinstance(pinned, list):
        pinned_items = [(f"[{i}]", p) for i, p in enumerate(pinned) if isinstance(p, dict)]
        errors += check_urls(pinned_items, "pinned.json")
        errors += check_headlines(pinned_items, "pinned.json")

    errors += check_em_dashes(news, "news.json")
    errors += check_em_dashes(pinned, "pinned.json")

    # The schema and the explicit checks can report the same problem; keep one copy.
    return list(dict.fromkeys(errors))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--news", type=Path, default=NEWS_PATH, help="path to news.json")
    parser.add_argument("--pinned", type=Path, default=PINNED_PATH, help="path to pinned.json")
    parser.add_argument(
        "--routine-pr",
        metavar="BASE_REF",
        help="also fail if any file other than data/news.json differs from BASE_REF",
    )
    args = parser.parse_args(argv)

    news, errors = load_json(args.news)
    pinned, pinned_errors = load_json(args.pinned)
    errors += pinned_errors
    if not errors:
        errors = validate(news, pinned)
    if args.routine_pr:
        errors += check_routine_pr(args.routine_pr)

    if errors:
        print(f"Validation failed with {len(errors)} problem(s):", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    print("Validation passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
