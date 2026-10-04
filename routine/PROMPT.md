# Daily Routine: update the Latest AI News board

You update `data/news.json` for the Latest AI News board shown on the TV in the
AI+ Studio, University of Arizona Libraries (Weaver Science-Engineering Library,
room 212). You run once a day. A person reviews and merges your pull request.

## Sources

Use only these sites (a subdomain of one of them is fine):

anthropic.com, openai.com, blog.google, deepmind.google, ai.meta.com,
huggingface.co, arxiv.org, github.com, responsibleai.arizona.edu, arizona.edu,
lib.arizona.edu, news.arizona.edu

- Look for AI news published in the last 14 days (America/Phoenix dates).
- Never invent an item. Every item must come from a page you actually opened
  in this run. If you could not open a page, do not use it.
- Use the date shown on the page itself for `date`. If a page has no clear
  date, do not use it.
- Link to the original page, not a search result or a listing page.

## Columns

- `models` (3 to 5 items): major model releases from Anthropic, OpenAI, Google,
  Meta, Hugging Face and similar labs.
- `tools` (3 to 5 items): notable tools, open-source releases, and important
  papers.
- `campus` (0 to 5 items): U of A GenAI updates (responsibleai.arizona.edu),
  University of Arizona Libraries AI news, and AI+ Studio news. Leave it empty
  if nothing qualifies. Pinned items in `data/pinned.json` fill the rest of the
  column automatically; do not copy them into `news.json`.

Prefer 4 items per column. Newest first within each column.

## Writing rules

- Plain, neutral, factual text. No hype words ("groundbreaking", "game
  changer", "revolutionary"), no exclamation marks, no opinions.
- No em dashes anywhere. Use commas, periods, or the word "to".
- No personal names of students or staff. Company and product names are fine.
- `headline`: 70 characters or fewer (the validator enforces this).
- `summary`: one sentence, 160 characters or fewer (the validator enforces
  this).
- `source`: the publisher, for example "Anthropic", "Google", "Hugging Face",
  "arXiv", "Office of Responsible AI", "University of Arizona Libraries".
- `url`: https only.
- No other keys, except the optional metrics below.

## Metrics (optional)

An item may carry up to 3 numbers that the spotlight shows as bars. The
shape looks like this (the numbers here are made up, for format only):

```json
"metrics": [
  {"label": "Score on SWE-bench Verified", "value": 71.4, "unit": "%"},
  {"label": "Output tokens per second", "value": 180}
],
"reported_by": "Anthropic"
```

- Add metrics only when the source page you opened states the exact numbers.
- Copy each number exactly as the page states it. Never estimate, round,
  convert, average, or combine numbers, and never take them from a different
  page than the item's `url`.
- If you are unsure about a number, its meaning, or its unit, leave the
  metrics out. An item without metrics is always fine.
- `label`: what the number measures, 30 characters or fewer, plain words.
- `value`: the number only (no text). For `"unit": "%"` it must be 0 to 100.
- `unit`: optional, 4 characters or fewer, for example `%`, `x`, `ms`, `s`.
- `reported_by`: required with metrics. Who reported the numbers, as the page
  says (for example "Anthropic" or "the paper's authors"). Do not add it
  without metrics.
- In the pull request description, quote the sentence from the source page
  that states each number, so the reviewer can check it.

## Branch and pull request

You always work on one branch, `claude/dev`, and keep at most one open pull
request from `claude/dev` into `main`. Every push to `claude/dev` publishes a
preview at https://ua-aistudio.github.io/ai-news-board/dev/ so a reviewer can
see the board before merging. The live board at
https://ua-aistudio.github.io/ai-news-board/ changes only when that pull
request is merged.

## Steps

1. Start from the live data:
   ```
   git fetch origin
   git checkout -B claude/dev origin/main
   ```
   This resets `claude/dev` to `main`, so each run starts clean.
2. Read `data/news.json` so you know what is already there. Keep items that are
   still within 14 days and still among the most important; drop anything
   older than 14 days.
3. Research and choose items following the rules above.
4. Edit only `data/news.json`. Do not touch any other file. Set `updated` to the
   current time in America/Phoenix with the offset, for example
   `2026-10-04T06:00:00-07:00`.
5. Run the validator in Routine mode:
   ```
   python scripts/validate.py --routine-pr origin/main
   ```
   Read every error, fix the data, and run it again until it prints
   "Validation passed." Always pass `--routine-pr`: without it, items older
   than 14 days are only warnings, but in your updates they are errors.
6. If you cannot reach 3 valid items in `models` or 3 valid items in `tools`,
   stop. Do not commit, do not push, and do not change any pull request.
   Report why.
7. Check that `git status` shows only `data/news.json` as changed. Commit with
   the message `News update YYYY-MM-DD` (today's Arizona date), run
   `python scripts/validate.py --routine-pr origin/main` once more (it now also
   confirms the commit changes only `data/news.json`), then force-push:
   ```
   git push --force origin claude/dev
   ```
8. Look for an open pull request from `claude/dev` into `main`:
   ```
   gh pr list --head claude/dev --base main --state open
   ```
   - If there is none, open one titled `News update YYYY-MM-DD`.
   - If there is one, update its title to `News update YYYY-MM-DD` and replace
     its description. Do not open a second pull request.
9. The pull request description must contain:
   - The preview link: https://ua-aistudio.github.io/ai-news-board/dev/
     (it updates a minute or two after the push).
   - Every item in the file by column, as `headline (source, date): url`,
     marking which ones are new compared with `main`.
10. Do not add attribution lines, "Co-Authored-By" lines, or any footer to the
    commit or pull request.
