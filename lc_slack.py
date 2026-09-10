"""LeetCode Slack integration: post the daily problem to a dedicated channel, then
reveal (thought process -> solution -> interviewer mindset) when you react with an emoji.

Reuses the same bot token as opportunity-finder (chat:write, reactions:read,
groups:history/read). Bot must be invited to the LeetCode channel.
"""

import datetime as dt
import json
import logging
import re
import subprocess
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

DATA = Path(__file__).parent / "data"
POSTED = DATA / "posted.json"          # slack ts -> {slug,title,difficulty,tags,revealed}
API = "https://slack.com/api"
DEFAULT_REVEAL = {"bulb", "brain", "eyes", "white_check_mark", "heavy_check_mark"}


def _load(p, d):
    return json.loads(p.read_text()) if p.exists() else d


def _save(p, o):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(o, indent=2))


def _token(scfg):
    p = Path(scfg.get("token_file", "")).expanduser()
    return p.read_text().strip() if p.exists() else ""


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _sanitize(text):
    if not text:
        return text
    return (text.replace(" — ", ", ").replace(" – ", ", ").replace("—", "-").replace("–", "-"))


def check_slack(scfg):
    t = _token(scfg)
    if not t:
        return f"❌ No bot token at {scfg.get('token_file')}"
    a = requests.get(f"{API}/auth.test", headers=_hdr(t), timeout=10).json()
    if not a.get("ok"):
        return f"❌ auth.test: {a.get('error')}"
    ch = scfg.get("channel_id", "")
    if not ch:
        return f"✓ authed as '{a.get('user')}' — but channel_id not set"
    info = requests.get(f"{API}/conversations.info", headers=_hdr(t), params={"channel": ch}, timeout=10).json()
    if info.get("ok"):
        return (f"✓ authed as '{a.get('user')}' · channel #{info['channel'].get('name')} "
                f"reachable, member={info['channel'].get('is_member')}")
    return f"✓ authed as '{a.get('user')}' · ❌ channel: {info.get('error')}"


def post_problem(scfg, prob, text):
    """Post the light problem card via bot; record ts->problem for later reveal."""
    t = _token(scfg)
    ch = scfg.get("channel_id", "")
    if not (t and ch):
        logger.warning("leetcode slack_bot not configured"); return False
    r = requests.post(f"{API}/chat.postMessage", headers=_hdr(t),
                      json={"channel": ch, "text": _sanitize(text)}, timeout=10).json()
    if not r.get("ok"):
        logger.warning("postMessage failed: %s", r.get("error")); return False
    posted = _load(POSTED, {})
    posted[r["ts"]] = {"slug": prob["slug"], "title": prob["title"],
                       "difficulty": prob["difficulty"], "tags": prob.get("tags", []),
                       "revealed": False}
    _save(POSTED, posted)
    return True


def _call_kiro(prompt, timeout=150):
    try:
        r = subprocess.run(["kiro-cli", "chat", prompt, "--legacy-ui", "--trust-tools=", "--agent", "gpu-minimal"],
                           capture_output=True, text=True, timeout=timeout)
        raw = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", r.stdout).replace("\r", "\n")
        lines = [l.rstrip() for l in raw.split("\n")
                 if not any(k in l for k in ["Thinking", "WARNING", "hooks", "Credits", "Model:",
                                             "changelog", "exit the CLI", "⠋", "⠙", "⠹", "⠸"])]
        return "\n".join(lines).strip()
    except Exception as e:
        logger.warning("kiro failed: %s", e); return ""


def generate_reveal(prob):
    prompt = (
        f"You are coaching a candidate on the LeetCode problem '{prob['title']}' "
        f"({prob['difficulty']}; topics: {', '.join(prob.get('tags', [])) or 'n/a'}). "
        "Write a concise reveal in three clearly-labeled sections. No code dumps (short pseudocode ok), "
        "no em dashes.\n\n"
        "*Thought process*: how to reason from the problem to the optimal approach, step by step.\n"
        "*Solution*: the optimal approach, the key insight, and time/space complexity.\n"
        "*Interviewer mindset*: what the interviewer is really evaluating when they ask this, what a "
        "strong answer demonstrates, the likely follow-up, and the most common mistake.")
    body = _call_kiro(prompt)
    return _sanitize(body) or "(Could not generate the reveal right now. Try reacting again in a minute.)"


def poll_reveals(scfg):
    """For each posted problem, if a reveal emoji is present and not yet revealed, post the reveal in-thread."""
    t = _token(scfg)
    ch = scfg.get("channel_id", "")
    if not (t and ch):
        return []
    reveal_set = set(scfg.get("reveal_emoji", [])) or DEFAULT_REVEAL
    posted = _load(POSTED, {})
    done = []
    for ts, info in posted.items():
        if info.get("revealed"):
            continue
        r = requests.get(f"{API}/reactions.get", headers=_hdr(t),
                         params={"channel": ch, "timestamp": ts}, timeout=10).json()
        if not r.get("ok"):
            continue
        names = {x["name"] for x in (r.get("message", {}).get("reactions") or [])}
        if names & reveal_set:
            reveal = generate_reveal(info)
            requests.post(f"{API}/chat.postMessage", headers=_hdr(t),
                          json={"channel": ch, "thread_ts": ts,
                                "text": f"🧠 *{info['title']} — walkthrough*\n\n{reveal}"}, timeout=15)
            info["revealed"] = True
            done.append(info["slug"])
    if done:
        _save(POSTED, posted)
    return done
