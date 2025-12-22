"""Prometheus metrics HTTP server.

Exposes claude-watch metrics in Prometheus text format on /metrics endpoint.
"""

import http.server
import socketserver
import threading
import time
from datetime import datetime, timezone
from typing import Callable, Optional

# Metric names following Prometheus conventions
METRIC_SESSION_PERCENT = "claude_usage_session_percent"
METRIC_WEEKLY_PERCENT = "claude_usage_weekly_percent"
METRIC_API_CALLS_TOTAL = "claude_usage_api_calls_total"
METRIC_LAST_FETCH_TIMESTAMP = "claude_usage_last_fetch_timestamp"
METRIC_FETCH_DURATION_SECONDS = "claude_usage_fetch_duration_seconds"
METRIC_FETCH_ERRORS_TOTAL = "claude_usage_fetch_errors_total"


class MetricsState:
    """Thread-safe container for metrics state."""

    def __init__(self):
        self.session_percent: float = 0.0
        self.weekly_percent: float = 0.0
        self.api_calls: int = 0
        self.last_fetch: float = 0.0
        self.fetch_duration: float = 0.0
        self.fetch_errors: int = 0
        self._lock = threading.Lock()

    def update(
        self,
        session_percent: float,
        weekly_percent: float,
        fetch_duration: float,
    ) -> None:
        """Update metrics state atomically."""
        with self._lock:
            self.session_percent = session_percent
            self.weekly_percent = weekly_percent
            self.last_fetch = time.time()
            self.fetch_duration = fetch_duration
            self.api_calls += 1

    def record_error(self) -> None:
        """Record a fetch error."""
        with self._lock:
            self.fetch_errors += 1
            self.api_calls += 1

    def get_snapshot(self) -> dict:
        """Get a consistent snapshot of all metrics."""
        with self._lock:
            return {
                "session_percent": self.session_percent,
                "weekly_percent": self.weekly_percent,
                "api_calls": self.api_calls,
                "last_fetch": self.last_fetch,
                "fetch_duration": self.fetch_duration,
                "fetch_errors": self.fetch_errors,
            }


# Global metrics state
_metrics_state = MetricsState()


def generate_metrics() -> str:
    """Generate Prometheus text format metrics.

    Returns:
        Prometheus text format string.
    """
    snapshot = _metrics_state.get_snapshot()

    lines = [
        # Session usage gauge
        f"# HELP {METRIC_SESSION_PERCENT} Current 5-hour session usage percentage",
        f"# TYPE {METRIC_SESSION_PERCENT} gauge",
        f'{METRIC_SESSION_PERCENT} {snapshot["session_percent"]:.2f}',
        "",
        # Weekly usage gauge
        f"# HELP {METRIC_WEEKLY_PERCENT} Current 7-day weekly usage percentage",
        f"# TYPE {METRIC_WEEKLY_PERCENT} gauge",
        f'{METRIC_WEEKLY_PERCENT} {snapshot["weekly_percent"]:.2f}',
        "",
        # API calls counter
        f"# HELP {METRIC_API_CALLS_TOTAL} Total number of API calls made",
        f"# TYPE {METRIC_API_CALLS_TOTAL} counter",
        f'{METRIC_API_CALLS_TOTAL} {snapshot["api_calls"]}',
        "",
        # Last fetch timestamp
        f"# HELP {METRIC_LAST_FETCH_TIMESTAMP} Timestamp of last successful fetch",
        f"# TYPE {METRIC_LAST_FETCH_TIMESTAMP} gauge",
        f'{METRIC_LAST_FETCH_TIMESTAMP} {snapshot["last_fetch"]:.3f}',
        "",
        # Fetch duration histogram (simplified as gauge for now)
        f"# HELP {METRIC_FETCH_DURATION_SECONDS} Duration of last API fetch in seconds",
        f"# TYPE {METRIC_FETCH_DURATION_SECONDS} gauge",
        f'{METRIC_FETCH_DURATION_SECONDS} {snapshot["fetch_duration"]:.3f}',
        "",
        # Fetch errors counter
        f"# HELP {METRIC_FETCH_ERRORS_TOTAL} Total number of fetch errors",
        f"# TYPE {METRIC_FETCH_ERRORS_TOTAL} counter",
        f'{METRIC_FETCH_ERRORS_TOTAL} {snapshot["fetch_errors"]}',
        "",
    ]

    return "\n".join(lines)


class MetricsHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler for Prometheus metrics endpoint."""

    def log_message(self, format: str, *args) -> None:
        """Suppress default logging."""
        pass

    def do_GET(self) -> None:
        """Handle GET requests."""
        if self.path == "/metrics":
            content = generate_metrics()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        elif self.path == "/health":
            content = "OK"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()


class MetricsServer:
    """Prometheus metrics HTTP server."""

    def __init__(
        self,
        port: int = 9100,
        fetch_func: Optional[Callable] = None,
        fetch_interval: int = 60,
    ):
        """Initialize metrics server.

        Args:
            port: Port to listen on.
            fetch_func: Function to fetch usage data.
            fetch_interval: How often to fetch data in seconds.
        """
        self.port = port
        self.fetch_func = fetch_func
        self.fetch_interval = fetch_interval
        self._server: Optional[socketserver.TCPServer] = None
        self._server_thread: Optional[threading.Thread] = None
        self._fetch_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def _fetch_loop(self) -> None:
        """Background thread to fetch usage data periodically."""
        while not self._stop_event.is_set():
            if self.fetch_func:
                start = time.time()
                try:
                    data = self.fetch_func()
                    if data:
                        five_hour = data.get("five_hour") or {}
                        seven_day = data.get("seven_day") or {}
                        _metrics_state.update(
                            session_percent=five_hour.get("utilization", 0),
                            weekly_percent=seven_day.get("utilization", 0),
                            fetch_duration=time.time() - start,
                        )
                except Exception:
                    _metrics_state.record_error()

            # Wait for next fetch or stop signal
            self._stop_event.wait(self.fetch_interval)

    def start(self) -> None:
        """Start the metrics server and fetch loop."""
        # Allow address reuse
        socketserver.TCPServer.allow_reuse_address = True

        self._server = socketserver.TCPServer(("0.0.0.0", self.port), MetricsHandler)

        # Start server thread
        self._server_thread = threading.Thread(
            target=self._server.serve_forever,
            daemon=True,
        )
        self._server_thread.start()

        # Start fetch thread
        if self.fetch_func:
            self._fetch_thread = threading.Thread(
                target=self._fetch_loop,
                daemon=True,
            )
            self._fetch_thread.start()

    def stop(self) -> None:
        """Stop the metrics server."""
        self._stop_event.set()
        if self._server:
            self._server.shutdown()

    def wait(self) -> None:
        """Wait for server to stop."""
        if self._server_thread:
            self._server_thread.join()


def run_metrics_server(
    port: int,
    fetch_func: Callable,
    fetch_interval: int = 60,
    verbose: bool = False,
) -> None:
    """Run the metrics server (blocking).

    Args:
        port: Port to listen on.
        fetch_func: Function to fetch usage data.
        fetch_interval: How often to fetch data in seconds.
        verbose: Whether to print status messages.
    """
    from claude_watch.display.colors import Colors

    server = MetricsServer(
        port=port,
        fetch_func=fetch_func,
        fetch_interval=fetch_interval,
    )

    if verbose:
        print(f"{Colors.CYAN}Starting Prometheus metrics server...{Colors.RESET}")
        print(f"  Port: {port}")
        print(f"  Fetch interval: {fetch_interval}s")
        print(f"  Metrics endpoint: http://0.0.0.0:{port}/metrics")
        print(f"  Health endpoint: http://0.0.0.0:{port}/health")
        print()
        print(f"  {Colors.DIM}Press Ctrl+C to stop{Colors.RESET}")
        print()

    server.start()

    # Do initial fetch
    if verbose:
        print(f"{Colors.DIM}Performing initial fetch...{Colors.RESET}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if verbose:
            print()
            print(f"{Colors.CYAN}Stopping metrics server...{Colors.RESET}")
        server.stop()
