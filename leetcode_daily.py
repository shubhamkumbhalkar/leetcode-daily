#!/usr/bin/env python3
"""LeetCode-a-day — one interview problem/day to Slack, with an interviewer-lens
pattern-recognition breakdown.

Sources (open, no auth):
  - neenza/leetcode-problems : full public JSON dataset of ~2,913 free problems
    (title, difficulty, topics, description, official hints) — cached locally, offline.
  - LeetCode public GraphQL   : fallback + official Daily Challenge.
  - Blind 75                  : embedded curated ordering (best for structured prep).

Each problem ships with:
  - LeetCode's own official hint
  - a "What the interviewer is looking for" breakdown (pattern · recognition cue ·
    what they're testing · what it transfers to) via kiro-cli — no spoilers.

Usage:
  python3 leetcode_daily.py [--dry-run|--no-lens|--progress|--reset|--validate|--install-cron]
"""

import argparse
import ast
import json
import logging
import os
import re
import subprocess
from pathlib import Path

import requests
import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent
DATA = SCRIPT_DIR / "data"
DELIVERED = DATA / "delivered.json"
DATASET_FILE = DATA / "problems.json"
DATASET_URL = "https://raw.githubusercontent.com/neenza/leetcode-problems/master/merged_problems.json"
GQL = "https://leetcode.com/graphql"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36",
    "Content-Type": "application/json", "Referer": "https://leetcode.com", "Origin": "https://leetcode.com",
}
DIFF_EMOJI = {"Easy": "🟢", "Medium": "🟡", "Hard": "🔴"}

BLIND75 = [
    "two-sum", "best-time-to-buy-and-sell-stock", "contains-duplicate",
    "product-of-array-except-self", "maximum-subarray", "maximum-product-subarray",
    "find-minimum-in-rotated-sorted-array", "search-in-rotated-sorted-array", "3sum",
    "container-with-most-water",
    "sum-of-two-integers", "number-of-1-bits", "counting-bits", "missing-number", "reverse-bits",
    "climbing-stairs", "coin-change", "longest-increasing-subsequence", "longest-common-subsequence",
    "word-break", "combination-sum", "house-robber", "house-robber-ii", "decode-ways",
    "unique-paths", "jump-game",
    "clone-graph", "course-schedule", "pacific-atlantic-water-flow", "number-of-islands",
    "longest-consecutive-sequence", "redundant-connection", "number-of-provinces",
    "insert-interval", "merge-intervals", "non-overlapping-intervals",
    "reverse-linked-list", "linked-list-cycle", "merge-two-sorted-lists", "merge-k-sorted-lists",
    "remove-nth-node-from-end-of-list", "reorder-list",
    "set-matrix-zeroes", "spiral-matrix", "rotate-image", "word-search",
    "longest-substring-without-repeating-characters", "longest-repeating-character-replacement",
    "minimum-window-substring", "valid-anagram", "group-anagrams", "valid-parentheses",
    "valid-palindrome", "longest-palindromic-substring", "palindromic-substrings",
    "maximum-depth-of-binary-tree", "same-tree", "invert-binary-tree", "binary-tree-maximum-path-sum",
    "binary-tree-level-order-traversal", "serialize-and-deserialize-binary-tree",
    "subtree-of-another-tree", "construct-binary-tree-from-preorder-and-inorder-traversal",
    "validate-binary-search-tree", "kth-smallest-element-in-a-bst",
    "lowest-common-ancestor-of-a-binary-search-tree", "implement-trie-prefix-tree",
    "design-add-and-search-words-data-structure", "word-search-ii",
    "top-k-frequent-elements", "find-median-from-data-stream",
]

# ---------- open dataset (neenza/leetcode-problems) ----------
_DS = None


def ensure_dataset():
    if DATASET_FILE.exists() and DATASET_FILE.stat().st_size > 1_000_000:
        return
    DATA.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading open LeetCode dataset (one-time, ~20MB)…")
    r = requests.get(DATASET_URL, headers=HEADERS, timeout=180)
    r.raise_for_status()
    DATASET_FILE.write_bytes(r.content)


def load_dataset():
    global _DS
    if _DS is None:
        try:
            ensure_dataset()
            qs = json.loads(DATASET_FILE.read_text()).get("questions", [])
            _DS = {q["problem_slug"]: q for q in qs}
            logger.info("Dataset loaded: %d problems", len(_DS))
        except Exception as e:
            logger.warning("dataset unavailable (%s) — falling back to LeetCode API", e)
            _DS = {}
    return _DS


def _plist(s):
    try:
        return ast.literal_eval(s) if isinstance(s, str) else (s or [])
    except Exception:
        return []


def dataset_problem(slug):
    q = load_dataset().get(slug)
    if not q:
        return None
    return {"id": q.get("frontend_id"), "title": q["title"], "slug": slug,
            "difficulty": q["difficulty"], "tags": _plist(q.get("topics")),
            "url": f"https://leetcode.com/problems/{slug}/",
            "official_hints": _plist(q.get("hints")), "description": q.get("description", "")}


# ---------- LeetCode API (fallback + daily) ----------
def gql(query, variables=None):
    r = requests.post(GQL, json={"query": query, "variables": variables or {}}, headers=HEADERS, timeout=20)
    r.raise_for_status()
    return r.json().get("data", {})


def fetch_problem(slug):
    d = gql("""query q($slug:String!){ question(titleSlug:$slug){
        questionFrontendId title titleSlug difficulty topicTags{name} isPaidOnly } }""", {"slug": slug})
    q = d.get("question")
    if not q or q.get("isPaidOnly"):
        return None
    return {"id": q["questionFrontendId"], "title": q["title"], "slug": q["titleSlug"],
            "difficulty": q["difficulty"], "tags": [t["name"] for t in q.get("topicTags", [])],
            "url": f"https://leetcode.com/problems/{slug}/", "official_hints": [], "description": ""}


def resolve(slug):
    return dataset_problem(slug) or fetch_problem(slug)


def fetch_daily():
    d = gql("""query { activeDailyCodingChallengeQuestion { link
        question { titleSlug } } }""")
    c = d.get("activeDailyCodingChallengeQuestion") or {}
    slug = (c.get("question") or {}).get("titleSlug")
    return resolve(slug) if slug else None


# ---------- interviewer-lens (pattern recognition) ----------
def _call_kiro(prompt, timeout=100):
    try:
        r = subprocess.run(["kiro-cli", "chat", prompt, "--legacy-ui", "--trust-tools=", "--agent", "gpu-minimal"],
                           capture_output=True, text=True, timeout=timeout)
        return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", r.stdout).replace("\r", "\n")
    except Exception as e:
        logger.warning("kiro call failed: %s", e)
        return ""


def interviewer_lens(prob):
    prompt = (
        f"For the LeetCode problem '{prob['title']}' ({prob['difficulty']}; topics: "
        f"{', '.join(prob['tags']) or 'n/a'}), output EXACTLY these four labeled lines, "
        "one sentence each, no code and no full solution:\n"
        "Pattern: <the core technique/pattern>\n"
        "Recognition cue: <what in a problem statement signals this pattern — phrase it as 'when you see X, reach for Y'>\n"
        "They're testing: <what an interviewer is really evaluating here>\n"
        "Transfers to: <the pattern family / other problems it unlocks>")
    raw = _call_kiro(prompt)
    labels = ("Pattern:", "Recognition cue:", "They're testing:", "Transfers to:")
    out = []
    for line in raw.splitlines():
        t = line.strip().lstrip("> ").strip().lstrip("*").strip()
        for lab in labels:
            if t.lower().startswith(lab.lower()):
                out.append("• *" + lab + "*" + t[len(lab):])
                break
    return "\n".join(out)


# ---------- state ----------
def load_delivered():
    return json.loads(DELIVERED.read_text()) if DELIVERED.exists() else []


def save_delivered(lst):
    DATA.mkdir(parents=True, exist_ok=True)
    DELIVERED.write_text(json.dumps(lst, indent=2))


def pick_next(mode, delivered):
    if mode == "daily":
        return fetch_daily()
    for slug in BLIND75:
        if slug not in delivered:
            p = resolve(slug)
            if p:
                return p
            delivered.append(slug)  # skip unresolved/paid
    return None


# ---------- format + send ----------
def format_msg(p, lens_text, mode, delivered):
    e = DIFF_EMOJI.get(p["difficulty"], "⚪")
    lines = [f"🧩 *LeetCode {'Daily Challenge' if mode=='daily' else 'Problem of the Day'}*\n",
             f"{e} *#{p['id']} — {p['title']}*  ({p['difficulty']})",
             f"🏷️ {', '.join(p['tags']) or '—'}",
             f"🔗 {p['url']}"]
    if mode == "list":
        lines.append(f"📈 Blind 75 progress: {len(delivered)+1}/{len(BLIND75)}")
    oh = p.get("official_hints") or []
    if oh:
        lines.append(f"\n💡 *LeetCode hint:* {oh[0]}")
    if lens_text:
        lines.append(f"\n🎯 *What the interviewer is looking for:*\n{lens_text}")
    lines.append("\n_Spot the pattern first, then code. Reply in-thread with your approach._")
    return "\n".join(lines)


def send_slack(webhook_file, msg):
    wf = Path(webhook_file).expanduser()
    if not wf.exists():
        logger.warning("no webhook at %s", wf); return False
    try:
        return requests.post(wf.read_text().strip(), json={"text": msg, "mrkdwn": True}, timeout=10).status_code == 200
    except Exception as e:
        logger.error("slack failed: %s", e); return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-lens", action="store_true")
    ap.add_argument("--progress", action="store_true")
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--validate", action="store_true")
    ap.add_argument("--install-cron", action="store_true")
    args = ap.parse_args()

    os.chdir(SCRIPT_DIR)
    cfg = yaml.safe_load(open("config.yaml"))

    if args.install_cron:
        wrapper = SCRIPT_DIR / "run_daily.sh"
        os.system(f'(crontab -l 2>/dev/null | grep -v "leetcode-daily/run_daily.sh"; '
                  f'echo "CRON_TZ=America/Chicago"; echo "0 8 * * * {wrapper}") | crontab -')
        print("✅ Cron installed: daily 8 AM America/Chicago."); return
    if args.progress:
        d = load_delivered()
        print(f"Blind 75: {len(d)}/{len(BLIND75)} delivered. Next:",
              next((s for s in BLIND75 if s not in d), "— complete!")); return
    if args.reset:
        save_delivered([]); print("Delivered history cleared."); return
    if args.validate:
        load_dataset()
        bad = [s for s in BLIND75 if not resolve(s)]
        print(f"{len(BLIND75)-len(bad)}/{len(BLIND75)} valid." + (f" Missing/paid: {bad}" if bad else " ✓")); return

    mode = cfg.get("mode", "list")
    delivered = load_delivered()
    p = pick_next(mode, delivered)
    if not p:
        msg = "🎉 Blind 75 complete! Set mode: daily in config.yaml, or --reset to loop."
        if not args.dry_run:
            send_slack(cfg.get("slack_webhook_file", ""), msg)
        print(msg); return

    lens_text = "" if (args.no_lens or not cfg.get("include_hint", True)) else interviewer_lens(p)
    msg = format_msg(p, lens_text, mode, delivered)

    if args.dry_run:
        print(msg); return
    if send_slack(cfg.get("slack_webhook_file", ""), msg):
        logger.info("Sent: #%s %s", p["id"], p["title"])
    if mode == "list":
        delivered.append(p["slug"]); save_delivered(delivered)


if __name__ == "__main__":
    main()
