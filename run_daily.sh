#!/bin/bash
export PATH="$HOME/.local/bin:$HOME/.toolbox/bin:/home/linuxbrew/.linuxbrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
cd /local/home/shoobham/leetcode-daily
python3 leetcode_daily.py >> /tmp/leetcode_daily.log 2>&1
