# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025-2026 @yosagi
"""Command-line argument parsing."""
import argparse
import sys
from pathlib import Path
from datetime import datetime


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="osc-tap",
        description="A pty wrapper that captures OSC sequences",
        epilog="Example: osc-tap --output ./logs --matcher TITLE '0;(.*)' -- claude",
    )

    parser.add_argument(
        "--output", "-o",
        type=Path,
        help="log output directory (default: current directory)",
        default=Path.cwd(),
    )

    parser.add_argument(
        "--matcher", "-m",
        nargs=2,
        action="append",
        metavar=("NAME", "PATTERN"),
        help="matcher definition (name and pattern). Matched against OSC content. Can be specified multiple times",
        default=[],
    )

    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to run (specify after --)",
    )

    parsed = parser.parse_args(args)

    # Strip leading --
    if parsed.command and parsed.command[0] == "--":
        parsed.command = parsed.command[1:]

    # Require a command
    if not parsed.command:
        parser.error("a command is required (specify after --)")

    return parsed


def generate_log_filename() -> str:
    """Generate a timestamp-based log filename."""
    return datetime.now().strftime("%Y%m%d_%H%M%S.jsonl")
