"""osc-tap: A pty wrapper that captures OSC sequences."""
import sys

from .cli import parse_args, generate_log_filename
from .wrapper import OscTapWrapper, compile_matchers


def main() -> int:
    """Entry point."""
    args = parse_args()

    # Create output directory
    args.output.mkdir(parents=True, exist_ok=True)

    # Open log file
    log_path = args.output / generate_log_filename()
    log_file = open(log_path, "a", encoding="utf-8")

    try:
        # Compile matchers
        matchers = compile_matchers(args.matcher)

        # Works even without matchers (log will be empty)
        if not matchers:
            print(
                f"[osc-tap] Warning: no matchers specified. No OSC sequences will be captured.",
                file=sys.stderr,
            )

        print(f"[osc-tap] Logging to: {log_path}", file=sys.stderr)

        # Run the wrapper
        wrapper = OscTapWrapper(args.command, matchers, log_file)
        return wrapper.run()

    finally:
        log_file.close()


if __name__ == "__main__":
    sys.exit(main())
