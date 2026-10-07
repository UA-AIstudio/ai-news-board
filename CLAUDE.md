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
- No icons, emojis, or decorative graphics. The one image is the AI+ Studio
  poster artwork in the Studio panel (see Images).
- Colors: Arizona Blue #0C234B, white, light gray #F5F7FB (the brief
  background) and border #DDE3EE, with Arizona Red #AB0520 as the only
  accent: the top bar, the kicker, NEW tags, metric bars, the spotlight
  progress bar and the "checked" dot. Navy and white may be used with
  opacity. No other colors. Text meets WCAG AA (4.5:1);
  `tests/test_repo_rules.py` checks the palette and the contrast.
- This is a TV: no search, navigation tabs, buttons, pagination, or anything
  that looks clickable.
- No Claude attribution in commits, pull requests, or the page.
- Python 3.12 in workflows.

## Layout (1920x1080, scales to 4K)

All sizes in `static/style.css` are multiples of `--px` (1px at 1920x1080,
2px at 3840x2160), so the layout is identical at any 16:9 size.

- Top: a 6px Arizona Red bar. Header on white: "AI+ Studio" label, a thin
  divider, "Latest AI News" (weight 800). Right: a bordered card "Checked at
  <time> Arizona time" with the date and a red dot, then the live clock.
- Left, 64 percent, on light gray: red "YOUR DAILY BRIEF" kicker; the
  spotlight card (category and source, headline, summary, metrics, NEW tag,
  QR on the right); then three white cards: New models, Tools and research,
  On campus. Each card shows 2 items at a time: NEW tag, source and category,
  date, the full headline and the full summary (never clamped or cut off).
- Column paging: items are split into pages of 2 (`build.py` `paginate`).
  A card with more pages turns every 10 seconds with a 600ms crossfade and
  loops; New models starts at 0s, Tools and research at 3s, On campus at 6s.
  A page never turns while a spotlight slide is moving. The card header
  shows a "1 of 3" counter and dots, omitted for a single page. All pages
  share one grid cell, so a card is as tall as its tallest page.
- On campus shows campus news only. When it is empty it says "No new campus
  AI news this week". Pinned items never appear in the columns or ticker.
- Right, 36 percent, navy Studio panel: the poster in the top 55 percent,
  then "What you can do here" with four text tiles, the open/closed badge,
  room, hours (built from `pinned.json` `hours`), email, the other pinned
  items as short notes, and a QR to the Studio page.
- Bottom: the headline ticker on navy across the full width, then a thin
  footer.
- Every change is checked with `tests/fixtures/stress_max.json` (5 items per
  column at maximum length) at 1920x1080 and 3840x2160, live and preview:
  every page fits in full, with no clipping, overlap, or scrollbars.

## Images

- Only people add or change images, under `static/img/`. The Routine never
  adds, changes, or removes images; CI fails any `claude/` branch pull
  request that touches `static/img/`, and `validate.py --routine-pr` reports
  it too.
- The poster original stays in the repo as `static/img/studio-poster.png`.
  `build.py` crops it to `POSTER_FOCUS` (the students and the robot, without
  the poster's own text) and writes `img/studio-poster.webp` under 400 KB
  with Pillow. When the poster is replaced, check `POSTER_FOCUS`.
- The panel shows it with `object-fit: cover` (never stretched),
  `saturate(0.8)`, and a navy gradient from the bottom. No glow effects.

## Motion rules

- Animate only `opacity` and `transform`. Use `will-change` sparingly.
- Pause all animation and timers while the page is hidden (`document.hidden`).
- Respect `prefers-reduced-motion`: no carousel motion, ticker, page crossfade,
  background drift (the faint light behind the Studio panel text), or pulse;
  show static content.
- All content must be readable without JavaScript: each card shows its first
  page, and every headline is in the ticker.
- With reduced motion, column pages switch without animation every 15 seconds.
- The 10-minute reload happens only at a column page change (or a slide
  change when nothing pages), never in the middle of a transition.
- Text never moves while it is being read, except the ticker. Spotlight slides
  and column pages move only during their short transition, and the burn-in
  shift is at most 2px every 10 minutes.

## Workflow rules

- The Routine only edits `data/news.json`, on the `claude/dev` branch, with at
  most one open pull request from `claude/dev` into `main`.
- The deploy builds both pages with `main`'s scripts and template; only data
  comes from `claude/dev`. Preview builds use `build.py --preview`.
- Design changes go through a branch and pull request. Never push to `main`.
- Never weaken `scripts/validate.py` without a reviewed pull request.
- Headlines are 70 characters or fewer and summaries 160 or fewer, enforced in
  both `schema/news.schema.json` and `scripts/validate.py`; change both together.
- Metrics are optional, at most 3 per item, and must be copied exactly from
  the item's source page (never estimated, rounded, or combined).
  `reported_by` is required with metrics and only allowed with them; `%`
  values are 0 to 100. Bars are drawn only when they have a real scale
  (percent of 100, or two or more metrics sharing a unit); the value text is
  always the exact number and never animates.
- QR codes are generated at build time with the `qrcode` package and inlined
  as SVG, navy on a white square with a quiet zone, at least 160px at 1080p.
- The 14-day freshness rule is an error only with `validate.py --routine-pr`
  (Routine pull requests). Elsewhere it is a warning.
- The allowlist lives in `scripts/validate.py` (`ALLOWED_DOMAINS`) and in the
  Routine environment's network settings; change both together.

## File layout

```
data/news.json              content written by the Routine
data/pinned.json            hand-edited Studio hours, closures and notes (Studio panel)
schema/news.schema.json     JSON Schema for news.json (and pinned items)
scripts/validate.py         all checks; exits 1 on any failure
scripts/build.py            data + template -> site/index.html
templates/index.html.j2     page template (Jinja2, autoescape on)
static/style.css            page styles
static/board.js             page behavior, inlined into the page by build.py
static/img/                 images, added by people only (studio-poster.png)
routine/PROMPT.md           instructions for the daily Routine
tests/                      pytest tests and fixtures (stress_max.json for layout)
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
