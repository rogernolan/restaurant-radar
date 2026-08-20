from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import socketserver

from .rss import preferred_url, render_rss


def render_index(weeks) -> str:
    sections = []
    for week, entries in weeks:
        items = "".join(
            f'<li><a href="{html.escape(preferred_url(entry), quote=True)}">{html.escape(entry.place.name)}</a> — '
            f'{html.escape(entry.place.address)} — {entry.place.rating:.1f} stars ({entry.place.review_count} reviews) — '
            f'{html.escape(entry.category)}</li>'
            for entry in entries
        ) or "<li>No qualifying restaurants this week.</li>"
        sections.append(f"<section><h2>Week of {week.isoformat()}</h2><ul>{items}</ul></section>")
    body = "".join(sections) or "<p>No weekly runs yet.</p>"
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Restaurant Radar</title></head><body><main>"
        "<h1>Restaurant Radar</h1><p>Weekly restaurant review signals.</p>"
        f"{body}</main></body></html>"
    )


class RadarHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path == "/health":
            self._send(200, "text/plain; charset=utf-8", b"ok\n")
            return
        if self.path == "/":
            body = render_index(self.server.store.all_entries()).encode()
            self._send(200, "text/html; charset=utf-8", body)
            return
        if self.path == "/feed.xml":
            body = render_rss(self.server.store.all_entries(), self.server.base_url).encode()
            self._send(200, "application/rss+xml; charset=utf-8", body)
            return
        self._send(404, "text/plain; charset=utf-8", b"not found\n")

    def _send(self, status: int, content_type: str, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args) -> None:
        return


class RadarHTTPServer(HTTPServer):
    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        self.server_name = self.server_address[0]
        self.server_port = self.server_address[1]


def serve_http(store, host: str, port: int, base_url: str) -> None:
    server = RadarHTTPServer((host, port), RadarHandler)
    server.store = store
    server.base_url = base_url
    server.serve_forever()
