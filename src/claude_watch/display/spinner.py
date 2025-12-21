"""Animated loading spinner for CLI feedback.

Provides a simple threaded spinner with braille animation frames.
"""

import itertools
import sys
import threading
import time

from claude_watch.display.colors import Colors


class Spinner:
    """Simple CLI spinner for loading states.

    Usage:
        with Spinner("Loading data"):
            # do work
            pass

        # Or manually:
        spinner = Spinner("Processing").start()
        # do work
        spinner.stop()
    """

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Loading"):
        """Initialize spinner with a message.

        Args:
            message: Text to display next to the spinner.
        """
        self.message = message
        self.running = False
        self.thread: threading.Thread | None = None
        self.frame_cycle = itertools.cycle(self.FRAMES)

    def _spin(self) -> None:
        """Internal method to animate the spinner."""
        while self.running:
            frame = next(self.frame_cycle)
            sys.stdout.write(f"\r{Colors.CYAN}{frame}{Colors.RESET} {self.message}...")
            sys.stdout.flush()
            time.sleep(0.08)

    def start(self) -> "Spinner":
        """Start the spinner animation.

        Returns:
            Self for chaining.
        """
        if not sys.stdout.isatty():
            return self
        self.running = True
        self.thread = threading.Thread(target=self._spin, daemon=True)
        self.thread.start()
        return self

    def stop(self, clear: bool = True) -> None:
        """Stop the spinner animation.

        Args:
            clear: Whether to clear the spinner line from output.
        """
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.2)
        if sys.stdout.isatty():
            if clear:
                sys.stdout.write(f"\r{' ' * (len(self.message) + 10)}\r")
            sys.stdout.flush()

    def __enter__(self) -> "Spinner":
        """Context manager entry."""
        return self.start()

    def __exit__(self, *args: object) -> None:
        """Context manager exit."""
        self.stop()


__all__ = ["Spinner"]
