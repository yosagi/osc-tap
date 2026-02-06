# SPDX-License-Identifier: BSD-3-Clause
# Copyright (c) 2025-2026 @yosagi
"""Core pty wrapper implementation."""
import pty
import os
import sys
import signal
import select
import fcntl
import termios
import tty
import re
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO


# OSC sequence pattern: ESC ] ... BEL
OSC_PATTERN = re.compile(rb"\x1b\]([^\x07]*)\x07")


class OscTapWrapper:
    """A pty wrapper that captures OSC sequences."""

    def __init__(
        self,
        command: list[str],
        matchers: list[tuple[str, re.Pattern]],
        log_file: TextIO,
    ):
        self.command = command
        self.matchers = matchers
        self.log_file = log_file
        self.child_fd: int | None = None
        self.child_pid: int | None = None
        self.buffer = b""
        self.old_settings = None

    def _set_winsize(self, fd: int) -> None:
        """Set the current terminal size on the given fd."""
        try:
            winsize = fcntl.ioctl(sys.stdin.fileno(), termios.TIOCGWINSZ, b"\x00" * 8)
            fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def _handle_sigwinch(self, signum: int, frame) -> None:
        """Forward window size changes to the child process."""
        if self.child_fd is not None:
            self._set_winsize(self.child_fd)

    def _handle_sigtstp(self, signum: int, frame) -> None:
        """Restore terminal settings before suspend."""
        if self.old_settings is not None:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, self.old_settings)
        # Send SIGTSTP to child process as well
        if self.child_pid is not None:
            os.kill(self.child_pid, signal.SIGTSTP)
        # Restore default handler and stop ourselves
        signal.signal(signal.SIGTSTP, signal.SIG_DFL)
        os.kill(os.getpid(), signal.SIGTSTP)

    def _handle_sigcont(self, signum: int, frame) -> None:
        """Re-enable raw mode after resume."""
        # Re-register SIGTSTP handler
        signal.signal(signal.SIGTSTP, self._handle_sigtstp)
        # Re-enable raw mode
        if self.old_settings is not None:
            tty.setraw(sys.stdin.fileno())
        # Send SIGCONT to child process as well
        if self.child_pid is not None:
            os.kill(self.child_pid, signal.SIGCONT)

    def _handle_sigchld(self, signum: int, frame) -> None:
        """Detect child process state changes."""
        if self.child_pid is None:
            return
        try:
            pid, status = os.waitpid(self.child_pid, os.WNOHANG | os.WUNTRACED)
            if pid == self.child_pid and os.WIFSTOPPED(status):
                # Child stopped -> stop ourselves too
                if self.old_settings is not None:
                    termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, self.old_settings)
                signal.signal(signal.SIGTSTP, signal.SIG_DFL)
                os.kill(os.getpid(), signal.SIGTSTP)
        except ChildProcessError:
            pass

    def _log_match(self, matcher_name: str, value: str) -> None:
        """Write a match result as a JSON Lines entry."""
        entry = {
            "ts": datetime.now(timezone.utc).astimezone().isoformat(),
            "matcher": matcher_name,
            "string": value,
        }
        self.log_file.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.log_file.flush()

    def _process_osc(self, osc_content: bytes) -> None:
        """Check OSC content against each matcher."""
        try:
            content_str = osc_content.decode("utf-8", errors="replace")
        except UnicodeDecodeError:
            return

        for name, pattern in self.matchers:
            match = pattern.search(content_str)
            if match:
                # Use group 1 if present, otherwise the full match
                value = match.group(1) if match.lastindex else match.group(0)
                self._log_match(name, value)

    def _process_buffer(self) -> None:
        """Process OSC sequences found in the buffer."""
        while True:
            match = OSC_PATTERN.search(self.buffer)
            if not match:
                break

            osc_content = match.group(1)
            self._process_osc(osc_content)
            self.buffer = self.buffer[match.end():]

        # Truncate buffer if it grows too large
        if len(self.buffer) > 10000:
            self.buffer = self.buffer[-1000:]

    def run(self) -> int:
        """Run the wrapper."""
        # Require a tty
        if not sys.stdin.isatty():
            print("Error: osc-tap must be run in a tty environment", file=sys.stderr)
            return 1

        pid, fd = pty.fork()

        if pid == 0:
            # Child process
            os.execvp(self.command[0], self.command)
            sys.exit(1)

        # Parent process
        self.child_fd = fd
        self.child_pid = pid
        self._set_winsize(fd)
        signal.signal(signal.SIGWINCH, self._handle_sigwinch)
        signal.signal(signal.SIGTSTP, self._handle_sigtstp)
        signal.signal(signal.SIGCONT, self._handle_sigcont)
        signal.signal(signal.SIGCHLD, self._handle_sigchld)

        # Save original terminal settings and switch to raw mode
        self.old_settings = termios.tcgetattr(sys.stdin)
        try:
            tty.setraw(sys.stdin.fileno())

            while True:
                rlist, _, _ = select.select([sys.stdin, fd], [], [])

                if sys.stdin in rlist:
                    # User input -> child process
                    data = os.read(sys.stdin.fileno(), 1024)
                    if not data:
                        break
                    os.write(fd, data)

                if fd in rlist:
                    # Child output -> screen (+ OSC capture)
                    try:
                        data = os.read(fd, 1024)
                    except OSError:
                        break
                    if not data:
                        break
                    os.write(sys.stdout.fileno(), data)

                    # Scan for OSC sequences
                    self.buffer += data
                    self._process_buffer()

        finally:
            termios.tcsetattr(sys.stdin, termios.TCSAFLUSH, self.old_settings)
            os.close(fd)
            try:
                _, status = os.waitpid(pid, 0)
                return os.WEXITSTATUS(status) if os.WIFEXITED(status) else 1
            except ChildProcessError:
                return 1


def compile_matchers(matcher_args: list[list[str]]) -> list[tuple[str, re.Pattern]]:
    """Compile matcher arguments into regex patterns."""
    result = []
    for name, pattern in matcher_args:
        try:
            compiled = re.compile(pattern)
            result.append((name, compiled))
        except re.error as e:
            print(f"Error: invalid pattern for matcher '{name}': {e}", file=sys.stderr)
            sys.exit(1)
    return result
