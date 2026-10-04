# Latest AI News board: project rules

A static page shown full screen on the TV in the AI+ Studio, University of
Arizona Libraries. A daily Routine writes `data/news.json` and opens a pull
request; CI validates it; a person merges; merging builds and deploys to GitHub
Pages.

- Live (from `main`): https://ua-aistudio.github.io/ai-news-board/
- Dev preview (from `claude/dev`): https://ua-aistudio.github.io/ai-news-board/dev/

Review flow: check the dev link, then merge the `claude/dev` pull request.

## Hard rules

- No em dashes (U+2014) anywhere: code, comments, docs, data, commit messages,
  pull request text.
- Static site only: no forms, user input, database, analytics, cookies, external
  fonts, or third-party scripts.
- Public information only. No personal data of any kind.
- No secrets. No API keys anywhere.
- No icons, emojis, or decorative graphics.
- Colors: Arizona Blue #0C234B and white, with Arizona Red #AB0520 as the only
  accent (used for "now" signals such as the spotlight progress bar and NEW
  tags). No other colors.
- No Claude attribution in commits, pull requests, or the page.
- Python 3.12 in workflows.

## Motion rules

- Animate only `opacity` and `transform`. Use `will-change` sparingly.
- Pause all animation and timers while the page is hidden (`document.hidden`).
- Respect `prefers-reduced-motion`: no carousel motion, ticker, highlight,
  background drift, or pulse; show static content.
- All content must be readable without JavaScript.
- Text never moves while it is being read, except the ticker. Spotlight slides
  move only during their short transition, and the burn-in shift is at most
  2px every 10 minutes.

## Workflow rules

- The Routine only edits `data/news.json`, on the `claude/dev` branch, with at
  most one open pull request from `claude/dev` into `main`.
- The deploy builds both pages with `main`'s scripts and template; only data
  comes from `claude/dev`. Preview builds use `build.py --preview`.
- Design changes go through a branch and pull request. Never push to `main`.
- Never weaken `scripts/validate.py` without a reviewed pull request.
- Headlines are 70 characters or fewer and summaries 160 or fewer, enforced in
  both `schema/news.schema.json` and `scripts/validate.py`; change both together.
- The 14-day freshness rule is an error only with `validate.py --routine-pr`
  (Routine pull requests). Elsewhere it is a warning.
- The allowlist lives in `scripts/validate.py` (`ALLOWED_DOMAINS`) and in the
  Routine environment's network settings; change both together.

## File layout

```
data/news.json              content written by the Routine
data/pinned.json            hand-edited campus items, Studio hours and closures
schema/news.schema.json     JSON Schema for news.json (and pinned items)
scripts/validate.py         all checks; exits 1 on any failure
scripts/build.py            data + template -> site/index.html
templates/index.html.j2     page template (Jinja2, autoescape on)
static/style.css            page styles
static/board.js             page behavior, inlined into the page by build.py
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
