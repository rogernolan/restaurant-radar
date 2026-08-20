from datetime import date
from http.client import HTTPConnection
from threading import Thread

from restaurant_radar.models import Entry, Place
from restaurant_radar.store import Store
from restaurant_radar.web import RadarHandler, RadarHTTPServer


def test_web_serves_html_rss_and_health(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    place = Place("p1", "The Place", "1 Street", 4.6, 42, None, "https://maps.example/p1")
    week = date(2026, 8, 17)
    store.save_week(week, [], [Entry(place, "low-volume", week)])
    server = RadarHTTPServer(("127.0.0.1", 0), RadarHandler)
    server.store = store
    server.base_url = "http://127.0.0.1"
    thread = Thread(target=server.handle_request)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    connection.request("GET", "/")
    response = connection.getresponse()
    html = response.read().decode()
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("text/html")
    assert "The Place" in html
    thread.join()

    server = RadarHTTPServer(("127.0.0.1", 0), RadarHandler)
    server.store = store
    server.base_url = "http://127.0.0.1"
    thread = Thread(target=server.handle_request)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    connection.request("GET", "/feed.xml")
    response = connection.getresponse()
    rss = response.read().decode()
    assert response.status == 200
    assert response.getheader("Content-Type").startswith("application/rss+xml")
    assert "The Place" in rss
    thread.join()

    server = RadarHTTPServer(("127.0.0.1", 0), RadarHandler)
    server.store = store
    server.base_url = "http://127.0.0.1"
    thread = Thread(target=server.handle_request)
    thread.start()
    connection = HTTPConnection("127.0.0.1", server.server_port)
    connection.request("GET", "/health")
    response = connection.getresponse()
    assert response.status == 200
    assert response.read() == b"ok\n"
    thread.join()
