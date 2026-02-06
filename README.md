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
```

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
