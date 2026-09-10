#!/usr/bin/env python3
"""LeetCode reveal poller — posts the solution + interviewer mindset in-thread when
you react (💡/🧠) on the daily problem.

  python3 reaction_poller.py            # one cycle
  python3 reaction_poller.py --daemon   # loop
"""
import logging
import sys
import time
from pathlib import Path

import yaml

import lc_slack

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger(__name__)
SCRIPT_DIR = Path(__file__).parent


def main():
    cfg = yaml.safe_load(open(SCRIPT_DIR / "config.yaml"))
    scfg = cfg.get("slack_bot", {})
    if not scfg.get("enabled"):
        print("slack_bot.enabled is false — enable it in config.yaml after Slack setup.")
        return
    interval = int(scfg.get("poll_interval", 60))
    daemon = "--daemon" in sys.argv
    while True:
        try:
            done = lc_slack.poll_reveals(scfg)
            if done:
                logger.info("Revealed: %s", done)
        except Exception as e:
            logger.error("poll error: %s", e)
        if not daemon:
            break
        time.sleep(interval)


if __name__ == "__main__":
    main()
