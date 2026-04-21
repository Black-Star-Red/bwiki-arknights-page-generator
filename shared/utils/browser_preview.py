"""Preview helpers for showing generated content in browser."""

from __future__ import annotations

import html
import http.server
import socketserver
import threading
import webbrowser


def create_handler(html_content: str):
    """Return an HTTP handler class that serves fixed HTML content."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(html_content.encode("utf-8"))

        def log_message(self, format, *args):
            return

    return Handler


def view_in_browser(content: str):
    """Show generated template content in a temporary local browser page."""
    escaped_content = html.escape(content)
    html_content = f"<pre>{escaped_content}</pre>"
    handler_class = create_handler(html_content)

    def start_server():
        with socketserver.TCPServer(("localhost", 0), handler_class) as httpd:
            port = httpd.server_address[1]
            webbrowser.open(f"http://localhost:{port}")
            httpd.serve_forever()

    threading.Thread(target=start_server, daemon=True).start()
    input("按 Enter 退出…")


__all__ = ["create_handler", "view_in_browser"]
