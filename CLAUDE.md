# Latest AI News board: project rules

A static page shown full screen on the TV in the AI+ Studio, University of
Arizona Libraries. A daily Routine writes `data/news.json` and opens a pull
request; CI validates it; a person merges; merging builds and deploys to GitHub
Pages.

## Hard rules

- No em dashes (U+2014) anywhere: code, comments, docs, data, commit messages,
  pull request text.
- Static site only: no forms, user input, database, analytics, cookies, external
  fonts, or third-party scripts.
- Public information only. No personal data of any kind.
- No secrets. No API keys anywhere.
- No icons, emojis, or decorative graphics.
- No Claude attribution in commits, pull requests, or the page.
- Python 3.12 in workflows.

## Workflow rules

- The Routine only edits `data/news.json`.
- Design changes go through a branch and pull request. Never push to `main`.
- Never weaken `scripts/validate.py` without a reviewed pull request.
- The allowlist lives in `scripts/validate.py` (`ALLOWED_DOMAINS`) and in the
  Routine environment's network settings; change both together.

## File layout

```
data/news.json              content written by the Routine
data/pinned.json            hand-edited campus items, exempt from the 14-day rule
schema/news.schema.json     JSON Schema for news.json (and pinned items)
scripts/validate.py         all checks; exits 1 on any failure
scripts/build.py            data + template -> site/index.html
templates/index.html.j2     page template (Jinja2, autoescape on)
static/style.css            page styles (navy #0C234B and white only)
routine/PROMPT.md           instructions for the daily Routine
tests/                      pytest tests and fixtures
.github/workflows/ci.yml    pull request checks
.github/workflows/deploy.yml  build and deploy on push to main
```

## Commands

```
pip install -r requirements.txt
python -m pytest
python scripts/validate.py
python scripts/build.py
```
