# Latest AI News board

A one-page news board for the TV in the AI+ Studio, University of Arizona
Libraries (Weaver Science-Engineering Library, room 212). It shows recent AI
news in three columns: New models, Tools and research, and On campus.

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

The Routine never edits code or HTML. Campus items that should always show
(Studio hours, the AI desk) live in `data/pinned.json` and are edited by hand.

The Studio hours item also has structured `hours` (24-hour times, Arizona
time, `null` for closed days). The page uses them to show "Open now, until
6pm" or "Closed, opens Monday 11am". Holiday closures are not known to the
page: for a holiday or a temporary change, edit `hours` in `data/pinned.json`
in a pull request, and change it back afterwards.

## What the TV page does

- A spotlight band cycles through every model and tool item, newest first,
  12 seconds each, with a QR code for the item's link.
- A live Arizona clock sits top right, above the "Updated" line.
- Items dated within 48 hours of the page load get a red NEW tag.
- A ticker above the footer scrolls every headline.
- Each column softly highlights one item at a time.
- The background drifts very slowly, and the whole layout shifts by up to
  2px every 10 minutes to protect the TV from burn-in.
- Every 10 minutes the page checks that the site is reachable and reloads
  between spotlight slides. If the network is down, it keeps the current page.
- All motion pauses while the page is hidden and turns off for viewers who
  ask their system for reduced motion. Without JavaScript, every item is
  still shown.

## Local setup

Requires Python 3.12.

```
pip install -r requirements.txt
python -m pytest
python scripts/validate.py
python scripts/build.py
```

Then open `site/index.html` in a browser. To see the preview version with the
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
- With `--routine-pr BASE_REF`: any file other than `data/news.json` changed,
  or any item is more than 14 days old.

Without `--routine-pr` (design pull requests and deploys), items more than 14
days old are printed as warnings and the run still passes, so stale news never
blocks a code change or a deploy. CI applies `--routine-pr` to pull requests
from `claude/` branches, so news updates must be fresh.

## How to review a news pull request

1. Check that CI passed.
2. Open the dev link, https://ua-aistudio.github.io/ai-news-board/dev/, and
   check that the board looks right: three columns, nothing cut off, the
   "Updated" time is today.
3. Open the Files tab. Only `data/news.json` should be changed.
4. Open each new link. Confirm the page exists, is on the right topic, and has
   the date shown in the item.
5. Read each headline and summary. They should match the source, be neutral
   and factual, and contain no personal names of students or staff.
6. Merge. The live board updates within a few minutes. If something is wrong,
   close the pull request instead; the TV keeps showing the last merged
   version, and the next Routine run starts over from `main`.

## How to change the design

1. Create a branch from `main`.
2. Edit `templates/index.html.j2` and `static/style.css`.
3. Run `python scripts/build.py` and check `site/index.html` at 1920x1080,
   including a column with five items.
4. Open a pull request. Merge after review.

To change the allowed sites, edit `ALLOWED_DOMAINS` in `scripts/validate.py`
and the Routine environment's network settings in the same change.

## Pilot log

| Date | Test | Who | Result |
| ---- | ---- | --- | ------ |
