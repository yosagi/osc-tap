# osc-tap

A pty wrapper that captures OSC sequences.

Intercepts OSC sequences (title changes, User Variables, etc.) emitted by terminal applications and logs them in JSON Lines format, while passing all output through transparently.

## Installation

```bash
pipx install git+https://github.com/yosagi/osc-tap.git
```

For development:

```bash
git clone https://github.com/yosagi/osc-tap.git
cd osc-tap
uv run osc-tap --help
```

## Usage

```bash
osc-tap [options] -- command [args...]
```

### Options

- `--output`, `-o`: Log output directory (default: current directory)
- `--matcher`, `-m`: Matcher definition (name and pattern). Can be specified multiple times

### Examples

```bash
# Capture Claude Code window titles
osc-tap \
  --output ~/.claude/logs/ \
  --matcher TITLE '0;(.*)' \
  -- claude

# Multiple matchers
osc-tap \
  --output ~/.claude/logs/ \
  --matcher TITLE '0;(.*)' \
  --matcher SESSION_START '1337;SetUserVar=SESSION_START=(.*)' \
  --matcher CONTEXT '1337;SetUserVar=CONTEXT=(.*)' \
  -- claude

# Capture titles and session info (see "Session identification hook" below)
osc-tap \
  --output ~/.claude/osc-logs/ \
  --matcher TITLE '0;(.*)' \
  --matcher TRANSCRIPT '10321;TRANSCRIPT=(.*)' \
  --matcher CWD '10321;CWD=(.*)' \
  --matcher SESSION_ID '10321;SESSION_ID=(.*)' \
  -- claude
```

## Session identification hook (Claude Code)

osc-tap logs are named by launch time, so by themselves they carry no clue
about which Claude Code session they belong to. `hooks/osc_session_start.sh`
fills this gap: registered as a Claude Code `SessionStart` hook, it emits the
session ID, transcript path, and working directory as OSC 10321 sequences at
session start, which osc-tap captures alongside titles (see the last example
above for the matching matchers). The number 10321 has no special meaning —
it is just an arbitrary code picked from the unassigned range to avoid
collisions; any number not used by your terminal works, as long as the hook
and the matchers agree.

```bash
# Copies itself to ~/.claude/hooks/ and registers in ~/.claude/settings.json
./hooks/osc_session_start.sh --install

# Check / remove
./hooks/osc_session_start.sh --status
./hooks/osc_session_start.sh --uninstall
```

A log file containing a `SESSION_ID` entry can then be associated with that
session, e.g.:

```jsonl
{"ts": "2026-07-08T22:27:04+09:00", "matcher": "SESSION_ID", "string": "d3ad4a94-..."}
```

Note: since Claude Code 2.1.139, hook processes are spawned without a
controlling terminal, so a plain `> /dev/tty` no longer works. The hook works
around this by walking up the parent process chain and writing to the first
pty file descriptor it finds.

## Log Format

Output is in JSON Lines format:

```jsonl
{"ts": "2026-01-23T14:30:52+09:00", "matcher": "TITLE", "string": "⠋ Claude Code"}
{"ts": "2026-01-23T14:31:05+09:00", "matcher": "CONTEXT", "string": "25"}
```

- `ts`: ISO 8601 timestamp with timezone
- `matcher`: Name of the matched matcher
- `string`: Extracted string (capture group 1 if present, otherwise the full match)

## Notes

- Requires a tty environment
- Only captures OSC sequences (`ESC ] ... BEL`)
- Matcher patterns are matched against the OSC content (between `ESC ]` and `BEL`)
