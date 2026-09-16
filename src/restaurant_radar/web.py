from __future__ import annotations

from datetime import date
from http.server import BaseHTTPRequestHandler, HTTPServer
import html
import socketserver

from .rss import preferred_url, render_rss


def _week_section(week, entries, link: bool) -> str:
    items = "".join(
        f'<li><a href="{html.escape(preferred_url(entry), quote=True)}">{html.escape(entry.place.name)}</a> — '
        f'{html.escape(entry.place.address)} — {entry.place.rating:.1f} stars ({entry.place.review_count} reviews) — '
        f'{html.escape(entry.category)}</li>'
        for entry in entries
    ) or "<li>No qualifying restaurants this week.</li>"
    heading = f"Week of {week.isoformat()}"
    if link:
        heading = f'<a href="/weeks/{week.isoformat()}">{heading}</a>'
    return f"<section><h2>{heading}</h2><ul>{items}</ul></section>"


def _page(body: str) -> str:
    return (
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Restaurant Radar</title></head><body><main>"
        "<h1>Restaurant Radar</h1><p>Weekly restaurant review signals.</p>"
        f"{body}</main></body></html>"
    )


def render_index(weeks) -> str:
    body = "".join(_week_section(week, entries, link=True) for week, entries in weeks) or "<p>No weekly runs yet.</p>"
    return _page(body)


def render_week(week, entries) -> str:
    return _page(_week_section(week, entries, link=False))


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
        if self.path.startswith("/weeks/"):
            try:
                week = date.fromisoformat(self.path.removeprefix("/weeks/"))
            except ValueError:
                self._send(404, "text/plain; charset=utf-8", b"not found\n")
                return
            if week not in self.server.store.weeks():
                self._send(404, "text/plain; charset=utf-8", b"not found\n")
                return
            body = render_week(week, self.server.store.entries_for_week(week)).encode()
            self._send(200, "text/html; charset=utf-8", body)
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
