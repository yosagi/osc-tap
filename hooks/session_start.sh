#!/bin/bash
# SessionStart hook: emit session info as OSC 10321 sequences
#
# Configure in Claude Code hooks.SessionStart:
#   "hooks": {
#     "SessionStart": [
#       { "matcher": "", "hooks": [{"type": "command", "command": "/path/to/session_start.sh"}] }
#     ]
#   }
#
# Reads JSON from stdin:
#   {"session_id": "...", "transcript_path": "...", ...}

# Read JSON from stdin
INPUT=$(cat)

# Extract values with jq
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path')

# Emit session info as OSC 10321 to /dev/tty
printf '\033]10321;TRANSCRIPT=%s\007' "$TRANSCRIPT" > /dev/tty
printf '\033]10321;CWD=%s\007' "$PWD" > /dev/tty
printf '\033]10321;SESSION_ID=%s\007' "$SESSION_ID" > /dev/tty
