# LeetCode-a-day

One interview problem per day to Slack — with **LeetCode's official hint** and a
**"What the interviewer is looking for"** pattern-recognition breakdown.

## Sources (all open, no auth)
- **[neenza/leetcode-problems](https://github.com/neenza/leetcode-problems)** — full public JSON
  dataset of ~2,913 free problems (title, difficulty, topics, description, official hints).
  Downloaded once and cached in gitignored `data/problems.json` → runs **offline**.
- **LeetCode public GraphQL** — fallback + the official Daily Challenge.
- **Blind 75** — embedded curated ordering (premium-only problems swapped for free equivalents).

## The interviewer lens (the point of this tool)
For each problem, a `kiro-cli`-generated breakdown — no code, no spoilers:
- **Pattern** — the core technique
- **Recognition cue** — "when you see X, reach for Y" (trains pattern spotting)
- **They're testing** — what the interviewer actually evaluates
- **Transfers to** — the pattern family / related problems

## Modes (`config.yaml`)
- `list` (default) — walk **Blind 75** in order, one new problem/day (structured prep).
- `daily` — LeetCode's official **Daily Challenge**.

## Usage
```bash
python3 leetcode_daily.py            # today's problem + lens → Slack
python3 leetcode_daily.py --dry-run  # preview, don't send / don't advance
python3 leetcode_daily.py --no-lens  # skip the LLM breakdown (faster)
python3 leetcode_daily.py --progress # how far through the list
python3 leetcode_daily.py --validate # check all curated slugs resolve
python3 leetcode_daily.py --reset    # restart the list
python3 leetcode_daily.py --install-cron   # daily 8 AM America/Chicago
```

## Notes
- Progress in `data/delivered.json`; dataset cached in `data/problems.json` (both gitignored, not committed).
- Reuses your existing Slack webhook. Lens uses the free local `kiro-cli` backend.
- Dataset is community-maintained (a static snapshot); brand-new problems may not appear — fine for interview prep.
