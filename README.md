# Latest AI News board

A one-page news board for the TV in the AI+ Studio, University of Arizona
Libraries (Weaver Science-Engineering Library, room 212). It shows recent AI
news as a daily brief: a spotlight card and three columns (New models, Tools
and research, On campus), next to a navy Studio panel with the AI+ Studio
poster artwork, what you can do in the Studio, its hours and a QR code.

- Live board (shown on the TV, built from `main`):
  https://ua-aistudio.github.io/ai-news-board/
- Dev preview (the pending news update, built from `claude/dev`):
  https://ua-aistudio.github.io/ai-news-board/dev/

The dev preview has a "Preview, not live. Awaiting review." banner and exists
only while the `claude/dev` branch exists.

## How the daily loop works

1. Once a day a Claude Code Routine follows `routine/PROMPT.md`. It resets the
   `claude/dev` branch to `main`, reads AI news from a short list of allowed
   sites, writes `data/news.json`, runs the validator, and force-pushes
   `claude/dev`.
2. The push deploys the site: the live board from `main` at `/`, and the
   preview from `claude/dev` at `/dev/`. Both use the template and scripts on
   `main`; only the data comes from `claude/dev`. If the `claude/dev` data fails
   validation, only the live board is deployed and the run shows a warning.
3. The Routine opens a pull request from `claude/dev` into `main`, or updates
   the one already open. There is never more than one.
4. CI runs the tests, validates the data, builds the page, and checks that the
   pull request changes only `data/news.json`.
5. A person checks the dev link, then merges.
6. Merging to `main` deploys the new live board.
7. The TV page checks the site every 10 minutes and reloads when the site is
   reachable. If the network is down, it keeps showing the current page.

The Routine never edits code, HTML, or images. Studio information that
should always show (Studio hours, the AI desk) lives in `data/pinned.json`,
is edited by hand, and appears in the Studio panel, not in the On campus
column or the ticker. When there is no campus news, the column says "No new
campus AI news this week".

The Studio hours item also has structured `hours` (24-hour times, Arizona
time, `null` for closed days). The page uses them to show "Open now, until
6pm" or "Closed, opens Monday 11am", and the build turns them into the hours
line in the panel ("Mon to Thu 11am to 6pm, Fri 11am to 5pm").

### Adding a holiday or other closure

The page does not know about holidays. To close the Studio on a day it would
normally be open, add an entry to `closures` on the "AI+ Studio hours" item in
`data/pinned.json`, in a pull request:

```json
"closures": [
  {"date": "2026-11-26", "note": "Thanksgiving"},
  {"date": "2026-11-27", "note": "Thanksgiving break"}
]
```

- `date` is the Arizona date, `YYYY-MM-DD`. Each date may appear once.
- `note` is required, 1 to 40 characters, with no em dashes.
- On that date the badge shows "Closed today, Thanksgiving". On the days
  before, "Closed, opens ..." skips closed dates. For a break longer than a
  week it names the reopening date, for example "opens January 4 11am".
- Past entries do no harm, but remove them now and then to keep the list short.
- For a permanent change in hours, edit `hours` instead.

`python scripts/validate.py` checks the format and that each date is real.

## What the TV page does

The layout is 1920x1080 and scales exactly to 3840x2160.

- Header: a red top bar, "AI+ Studio | Latest AI News", a "Checked at <time>
  Arizona time" card with the date, and a live Arizona clock.
- Left (64 percent): a red "YOUR DAILY BRIEF" kicker, then the spotlight
  card, which cycles through every model and tool item, newest first, 12
  seconds each. Each slide has a QR code for the item's source ("Scan to
  read the source"), generated at build time with the `qrcode` package.
- Items with metrics show them on their slide as Arizona Red bars that grow
  in over 800ms, with the label, the exact value, and "Reported by ...".
  Percentages fill against 100; other values fill against the largest value
  with the same unit on that item, and a value with nothing to compare
  against shows as text only.
- Below the spotlight, three white cards show two items at a time, each with
  source, category and date, the full headline, and the full summary. A
  card with more than two items turns to its next page every 10 seconds
  with a 600ms crossfade and loops back to the first. The cards start 3
  seconds apart (New models, then Tools and research, then On campus), and a
  page never turns while a spotlight slide is moving. A "1 of 3" counter and
  dots in the card header show the page; a card with one page has none.
  Every card is as tall as its tallest page, so it never changes size.
- Right (36 percent): the Studio panel. The poster artwork (cropped, slightly
  desaturated, fading into navy), "What you can do here" with four tiles,
  the open/closed badge, room, hours, email, the AI desk note, and a QR code
  to the Studio page ("Scan to visit the Studio").
- Items dated within 48 hours of the page load get a red NEW tag.
- A navy ticker above the footer scrolls every news headline.
- A faint light drifts very slowly behind the Studio panel text, and the
  whole layout shifts by up to 2px every 10 minutes to protect the TV from
  burn-in.
- Every 10 minutes the page checks that the site is reachable and reloads
  at the next column page change (or the next spotlight slide when no card
  has more than one page). If the network is down, it keeps the current page.
- All motion pauses while the page is hidden and turns off for viewers who
  ask their system for reduced motion; then pages switch without animation
  every 15 seconds. Without JavaScript, each card shows its first page and
  every headline is still in the ticker.

## Local setup

Requires Python 3.12.

```
pip install -r requirements.txt
python -m pytest
python scripts/validate.py
python scripts/build.py
```

The build needs Pillow (in `requirements.txt`) to convert the poster to
WebP. Then open `site/index.html` in a browser. To see the preview version with the
banner, run `python scripts/build.py --preview --out site/dev` and open
`site/dev/index.html`. For a TV preview, set the window to
1920x1080 and use full screen.

## What the validator checks

`scripts/validate.py` fails, with a message for each problem, if:

- `news.json` does not match `schema/news.schema.json` (including extra keys,
  or too few or too many items in a column).
- Any link is not https or points outside the allowlist in `ALLOWED_DOMAINS`.
- Any item date is in the future (Arizona time).
- Any headline is longer than 70 characters or any summary is longer than 160
  characters (news and pinned items).
- Any text in `news.json` or `pinned.json` contains an em dash.
- Two items share a link.
- An item has more than 3 metrics, a metric label over 30 characters, a unit
  over 4 characters, a value that is not a finite number, or a `%` value
  outside 0 to 100.
- An item has metrics without `reported_by`, or `reported_by` without metrics.
- With `--routine-pr BASE_REF`: any file other than `data/news.json` changed
  (with its own message for images under `static/img/`), or any item is more
  than 14 days old.

Without `--routine-pr` (design pull requests and deploys), items more than 14
days old are printed as warnings and the run still passes, so stale news never
blocks a code change or a deploy. CI applies `--routine-pr` to pull requests
from `claude/` branches, so news updates must be fresh.

## How to review a news pull request

1. Check that CI passed.
2. Open the dev link, https://ua-aistudio.github.io/ai-news-board/dev/, and
   check that the board looks right: spotlight, three columns, Studio panel,
   nothing cut off, and the "Checked at" date is today.
3. Open the Files tab. Only `data/news.json` should be changed.
4. Open each new link. Confirm the page exists, is on the right topic, and has
   the date shown in the item.
5. Read each headline and summary. They should match the source, be neutral
   and factual, and contain no personal names of students or staff.
   If an item has metrics, find each number on the source page and check that
   the value, unit and label match exactly. If any number is not on the page,
   ask for it to be removed.
6. Merge. The live board updates within a few minutes. If something is wrong,
   close the pull request instead; the TV keeps showing the last merged
   version, and the next Routine run starts over from `main`.

## How to change the design

1. Create a branch from `main`.
2. Edit `templates/index.html.j2` and `static/style.css`. Size everything in
   `--px` units so 4K stays an exact 2x.
3. Run `python scripts/build.py` and check `site/index.html` at 1920x1080 and
   3840x2160, live and with `--preview`. Also build with
   `tests/fixtures/stress_max.json` (5 items per column at maximum length):
   every page of every card must fit in full, and nothing may be cut off,
   overlap, or scroll.
4. Use only the palette in CLAUDE.md; `python -m pytest` checks the colors
   and their contrast.
5. Open a pull request. Merge after review.

## Images

Only people add or change images, under `static/img/`. The Routine never
does, and CI fails any `claude/` branch pull request that touches that folder.

The poster is `static/img/studio-poster.png` (the original, kept in the repo).
The build crops it to `POSTER_FOCUS` in `scripts/build.py` (the students and
the robot, leaving out the poster's own text, which the panel shows as real
text) and writes a WebP under 400 KB. To replace the poster, commit a new PNG
with the same name in a pull request, then check `POSTER_FOCUS` and the
panel at 1920x1080.

To change the allowed sites, edit `ALLOWED_DOMAINS` in `scripts/validate.py`
and the Routine environment's network settings in the same change.

## Pilot log

| Date | Test | Who | Result |
| ---- | ---- | --- | ------ |
