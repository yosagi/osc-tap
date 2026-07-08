#!/bin/bash
# SessionStart hook: emit session info as OSC 10321 sequences
#
# Together with the osc-tap matchers (SESSION_ID / TRANSCRIPT / CWD),
# this lets osc-tap logs be associated with a Claude Code session.
#
# Install (copies itself to ~/.claude/hooks/ and registers in settings.json):
#   ./osc_session_start.sh --install
#
# Reads JSON from stdin:
#   {"session_id": "...", "transcript_path": "...", "cwd": "...", ...}
#
# Note: since Claude Code 2.1.139, hook processes are spawned without a
# controlling terminal, so writing to /dev/tty fails. As a workaround,
# walk up the parent process chain and find an fd attached to /dev/pts/*.

set -euo pipefail

SCRIPT_NAME="osc_session_start.sh"
HOOKS_DIR="$HOME/.claude/hooks"
SETTINGS_FILE="$HOME/.claude/settings.json"

show_help() {
    cat << EOF
Usage: $SCRIPT_NAME [OPTIONS]

Claude Code SessionStart hook - emit session info as OSC 10321 sequences
so that osc-tap can associate its log with the session.

Options:
  --install     Copy this script to $HOOKS_DIR and register it in settings.json
  --uninstall   Remove the script and its settings.json entry
  --status      Show installation status
  --help        Show this help

Normal execution (as a hook):
  Reads JSON from stdin and emits SESSION_ID / TRANSCRIPT / CWD as
  OSC 10321 sequences to the terminal. No-op when no terminal is found.
EOF
}

find_tty_device() {
    # Use /dev/tty directly when a controlling terminal exists
    local tty_nr
    tty_nr=$(awk '{print $7}' /proc/self/stat 2>/dev/null)
    if [ "${tty_nr:-0}" -ne 0 ] 2>/dev/null; then
        echo "/dev/tty"
        return 0
    fi
    # No controlling terminal: search parent processes for a pty fd
    local pid=$$
    while [ "$pid" -gt 1 ]; do
        pid=$(awk '{print $4}' /proc/$pid/stat 2>/dev/null) || break
        local fd
        for fd in /proc/$pid/fd/0 /proc/$pid/fd/1 /proc/$pid/fd/2; do
            local target
            target=$(readlink "$fd" 2>/dev/null) || continue
            if [[ "$target" == /dev/pts/* ]]; then
                echo "$target"
                return 0
            fi
        done
    done
    return 1
}

do_install() {
    echo "Installing SessionStart hook..."

    mkdir -p "$HOOKS_DIR"

    local target="$HOOKS_DIR/$SCRIPT_NAME"
    echo "  copy: $target"
    cp "$0" "$target"
    chmod +x "$target"

    if [[ ! -f "$SETTINGS_FILE" ]]; then
        echo '{}' > "$SETTINGS_FILE"
    fi

    # Merge into hooks.SessionStart: keep other entries, add/update our own
    echo "  edit: $SETTINGS_FILE"
    local tmp
    tmp=$(mktemp)
    jq --arg cmd "$target" '
        .hooks = (.hooks // {}) |
        .hooks.SessionStart = (
            [.hooks.SessionStart // [] | .[] | select(.hooks[0].command != $cmd)] +
            [{"hooks": [{"type": "command", "command": $cmd}]}]
        )
    ' "$SETTINGS_FILE" > "$tmp" && mv "$tmp" "$SETTINGS_FILE"

    echo ""
    echo "Done. The hook takes effect on newly started sessions."
}

do_uninstall() {
    echo "Uninstalling SessionStart hook..."

    local target="$HOOKS_DIR/$SCRIPT_NAME"

    if [[ -f "$SETTINGS_FILE" ]]; then
        echo "  edit: $SETTINGS_FILE"
        local tmp
        tmp=$(mktemp)
        jq --arg cmd "$target" '
            if .hooks.SessionStart then
                .hooks.SessionStart =
                    [.hooks.SessionStart[] | select(.hooks[0].command != $cmd)]
            else . end
        ' "$SETTINGS_FILE" > "$tmp" && mv "$tmp" "$SETTINGS_FILE"
    fi

    if [[ -f "$target" ]]; then
        echo "  remove: $target"
        rm "$target"
    fi

    echo "Done."
}

do_status() {
    local target="$HOOKS_DIR/$SCRIPT_NAME"
    if [[ -f "$target" ]]; then
        echo "script: installed ($target)"
    else
        echo "script: not installed"
    fi
    if [[ -f "$SETTINGS_FILE" ]] && \
       jq -e --arg cmd "$target" \
           '.hooks.SessionStart // [] | .[] | select(.hooks[0].command == $cmd)' \
           "$SETTINGS_FILE" >/dev/null 2>&1; then
        echo "settings.json: registered"
    else
        echo "settings.json: not registered"
    fi
}

run_hook() {
    # Read JSON from stdin
    local input
    input=$(cat)

    local session_id transcript cwd
    session_id=$(echo "$input" | jq -r '.session_id // empty')
    transcript=$(echo "$input" | jq -r '.transcript_path // empty')
    cwd=$(echo "$input" | jq -r '.cwd // empty')
    [ -n "$cwd" ] || cwd="$PWD"

    # Emit session info as OSC 10321 to the terminal (no-op if none found)
    local tty_dev
    tty_dev=$(find_tty_device) || exit 0
    [ -c "$tty_dev" ] || exit 0

    printf '\033]10321;TRANSCRIPT=%s\007' "$transcript" > "$tty_dev"
    printf '\033]10321;CWD=%s\007' "$cwd" > "$tty_dev"
    printf '\033]10321;SESSION_ID=%s\007' "$session_id" > "$tty_dev"
}

case "${1:-}" in
    --install)
        do_install
        ;;
    --uninstall)
        do_uninstall
        ;;
    --status)
        do_status
        ;;
    --help)
        show_help
        ;;
    *)
        run_hook
        ;;
esac
