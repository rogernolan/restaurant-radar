from datetime import date
from http.client import HTTPConnection
from threading import Thread

from restaurant_radar.models import Entry, Place
from restaurant_radar.store import Store
from restaurant_radar.web import RadarHandler, RadarHTTPServer


def _get(store, path):
    server = RadarHTTPServer(("127.0.0.1", 0), RadarHandler)
    server.store = store
    server.base_url = "http://127.0.0.1"
    thread = Thread(target=server.handle_request)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    connection.request("GET", path)
    response = connection.getresponse()
    body = response.read()
    thread.join()
    server.server_close()
    return response, body


def test_web_serves_html_rss_and_health(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    place = Place("p1", "The Place", "1 Street", 4.6, 42, None, "https://maps.example/p1")
    week = date(2026, 8, 17)
    store.save_week(week, [], [Entry(place, "low-volume", week)])

    response, html = _get(store, "/")
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("text/html")
    assert "The Place" in html.decode()

    response, rss = _get(store, "/feed.xml")
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("application/rss+xml")
    assert "The Place" in rss.decode()

    response, body = _get(store, "/health")
    assert response.status == 200
    assert body == b"ok\n"


def test_web_serves_week_page_and_404s_unknown_week(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    place = Place("p1", "The Place", "1 Street", 4.6, 42, None, "https://maps.example/p1")
    week = date(2026, 8, 17)
    store.save_week(week, [], [Entry(place, "low-volume", week)])

    response, html = _get(store, "/weeks/2026-08-17")
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("text/html")
    assert "The Place" in html.decode()
    assert "2026-08-17" in html.decode()

    response, _ = _get(store, "/weeks/2026-08-24")
    assert response.status == 404

    response, _ = _get(store, "/weeks/not-a-date")
    assert response.status == 404
