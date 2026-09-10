#!/bin/bash
export PATH="$HOME/.local/bin:$HOME/.toolbox/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd /local/home/shoobham/leetcode-daily
if ! pgrep -f "reaction_poller.py --daemon --tag leetcode" >/dev/null; then
    setsid nohup python3 reaction_poller.py --daemon --tag leetcode </dev/null >>/tmp/leetcode_poller.log 2>&1 &
fi
python3 leetcode_daily.py >> /tmp/leetcode_daily.log 2>&1
