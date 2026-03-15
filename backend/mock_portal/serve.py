"""Serve the mock custodian portal on http://localhost:8080.

Run from any directory:
    python backend/mock_portal/serve.py

Or from the backend/ directory:
    python mock_portal/serve.py
"""
import http.server
import os
import socketserver
import sys
from pathlib import Path

PORT = 8080
PORTAL_DIR = Path(__file__).parent.resolve()


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve files from the portal directory; suppress noisy access logs."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(PORTAL_DIR), **kwargs)

    def log_message(self, fmt, *args):  # noqa: A002
        # Only log errors, not every GET
        if args and str(args[1]) not in ("200", "304"):
            super().log_message(fmt, *args)


def main() -> None:
    os.chdir(PORTAL_DIR)

    with socketserver.TCPServer(("", PORT), QuietHandler) as httpd:
        httpd.allow_reuse_address = True
        print(f"Mock custodian portal running at http://localhost:{PORT}")
        print(f"  Login page  : http://localhost:{PORT}/index.html")
        print(f"  Dashboard   : http://localhost:{PORT}/dashboard.html?client=CLT001")
        print("Press Ctrl-C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nPortal server stopped.")
            sys.exit(0)


if __name__ == "__main__":
    main()
