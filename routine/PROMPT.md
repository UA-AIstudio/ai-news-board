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
- `headline`: under 90 characters; aim for 70 or fewer so it fits on two lines.
- `summary`: one sentence, under 200 characters; aim for 160 or fewer.
- `source`: the publisher, for example "Anthropic", "Google", "Hugging Face",
  "arXiv", "Office of Responsible AI", "University of Arizona Libraries".
- `url`: https only.
- No other keys.

## Steps

1. Read the current `data/news.json` so you know what is already there. Keep
   items that are still within 14 days and still among the most important;
   drop anything older than 14 days.
2. Research and choose items following the rules above.
3. Edit only `data/news.json`. Do not touch any other file. Set `updated` to the
   current time in America/Phoenix with the offset, for example
   `2026-10-04T06:00:00-07:00`.
4. Run `python scripts/validate.py`. Read every error, fix the data, and run it
   again until it prints "Validation passed."
5. If you cannot reach 3 valid items in `models` or 3 valid items in `tools`,
   stop. Do not commit and do not open a pull request. Report why.
6. Commit on your `claude/` branch with the message `News update YYYY-MM-DD`
   (today's Arizona date), push, and open a pull request into `main` titled
   `News update YYYY-MM-DD`. In the description, list every item in the file
   by column as `headline (source, date): url`, and mark which ones are new
   since the last update.
7. Do not add attribution lines, "Co-Authored-By" lines, or any footer to the
   commit or pull request.
