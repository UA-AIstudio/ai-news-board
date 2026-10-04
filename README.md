# Latest AI News board

A one-page news board for the TV in the AI+ Studio, University of Arizona
Libraries (Weaver Science-Engineering Library, room 212). It shows recent AI
news in three columns: New models, Tools and research, and On campus.

Live page: https://ua-aistudio.github.io/ai-news-board/

## How the daily loop works

1. Once a day a Claude Code Routine follows `routine/PROMPT.md`. It reads AI
   news from a short list of allowed sites, writes `data/news.json`, runs the
   validator, and opens a pull request from a `claude/` branch.
2. CI runs the tests, validates the data, builds the page, and checks that the
   pull request changes only `data/news.json`.
3. A person reviews the pull request and merges it.
4. Merging to `main` builds `site/index.html` from the fixed template and
   deploys it to GitHub Pages.
5. The TV page checks the site every 10 minutes and reloads when the site is
   reachable. If the network is down, it keeps showing the current page.

The Routine never edits code or HTML. Campus items that should always show
(Studio hours, the AI desk) live in `data/pinned.json` and are edited by hand.

## Local setup

Requires Python 3.12.

```
pip install -r requirements.txt
python -m pytest
python scripts/validate.py
python scripts/build.py
```

Then open `site/index.html` in a browser. For a TV preview, set the window to
1920x1080 and use full screen.

## What the validator checks

`scripts/validate.py` fails, with a message for each problem, if:

- `news.json` does not match `schema/news.schema.json` (including extra keys,
  or too few or too many items in a column).
- Any link is not https or points outside the allowlist in `ALLOWED_DOMAINS`.
- Any item date is in the future or more than 14 days old (Arizona time).
- Any headline is 90 characters or longer.
- Any text in `news.json` or `pinned.json` contains an em dash.
- Two items share a link.
- With `--routine-pr BASE_REF`: any file other than `data/news.json` changed.

Note: because of the 14-day rule, CI on any pull request fails if the news has
not been updated for two weeks. Merge a fresh news update first.

## How to review a news pull request

1. Check that CI passed.
2. Open the Files tab. Only `data/news.json` should be changed.
3. Open each new link. Confirm the page exists, is on the right topic, and has
   the date shown in the item.
4. Read each headline and summary. They should match the source, be neutral
   and factual, and contain no personal names of students or staff.
5. Merge. The page updates within a few minutes. If something is wrong, close
   the pull request instead; the TV keeps showing the last merged version.

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
