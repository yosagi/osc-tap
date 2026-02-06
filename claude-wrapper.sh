#!/bin/bash
# Wrapper script to launch Claude Code via osc-tap
#
# Usage:
#   ./claude-wrapper.sh [claude options...]
#
# Log output: ~/.claude/osc-logs/
#
# Prerequisites:
#   Configure hooks.SessionStart to run session_start.sh

LOG_DIR="${HOME}/.claude/osc-logs"

exec osc-tap \
    --output "$LOG_DIR" \
    --matcher TITLE '0;(.*)' \
    --matcher TRANSCRIPT '10321;TRANSCRIPT=(.*)' \
    --matcher CWD '10321;CWD=(.*)' \
    --matcher SESSION_ID '10321;SESSION_ID=(.*)' \
    -- claude "$@"
