from datetime import date
import xml.etree.ElementTree as ET

from restaurant_radar.models import Entry, Place
from restaurant_radar.rss import render_rss


def test_rss_contains_one_item_per_week_and_uses_maps_fallback():
    place = Place("p1", "A & B", "1 <Street>", 4.6, 42, None, "https://maps.example/p1")
    feed = render_rss([(date(2026, 8, 17), [Entry(place, "low-volume", date(2026, 8, 17))])], "https://radar.example")
    root = ET.fromstring(feed)
    item = root.find("./channel/item")
    assert item is not None
    assert item.findtext("title") == "Rising stars — week of 2026-08-17"
    assert "A &amp; B" in feed
    assert "A & B" in item.findtext("description")
    assert "https://maps.example/p1" in item.findtext("description")


def test_rss_prefers_website_and_has_stable_week_guid():
    place = Place("p1", "The Place", "1 Street", 4.6, 42, "https://place.example", "https://maps.example/p1")
    feed = render_rss([(date(2026, 8, 17), [Entry(place, "improving", date(2026, 8, 17))])], "https://radar.example")
    item = ET.fromstring(feed).find("./channel/item")
    assert item.findtext("guid") == "https://radar.example/weeks/2026-08-17"
    assert "https://place.example" in item.findtext("description")
