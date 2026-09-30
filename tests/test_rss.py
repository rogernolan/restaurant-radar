from datetime import date
from email.utils import parsedate_to_datetime
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
    description = item.findtext("description")
    assert description is not None
    assert "A &amp; B — 1 &lt;Street&gt; — 4.6 stars (42 reviews) — low-volume" in description
    assert '<a href="https://maps.example/p1">Google Maps</a>' in description
    assert parsedate_to_datetime(item.findtext("pubDate")).date() == date(2026, 8, 17)


def test_rss_prefers_website_and_has_stable_week_guid():
    place = Place("p1", "The Place", "1 Street", 4.6, 42, "https://place.example", "https://maps.example/p1")
    feed = render_rss([(date(2026, 8, 17), [Entry(place, "improving", date(2026, 8, 17))])], "https://radar.example")
    item = ET.fromstring(feed).find("./channel/item")
    assert item.findtext("guid") == "https://radar.example/weeks/2026-08-17"
    description = item.findtext("description")
    assert description is not None
    assert '<a href="https://place.example">Website</a>' in description


def test_rss_puts_multiple_entries_on_separate_lines():
    first = Place("p1", "First", "1 Street", 4.6, 42, None, "https://maps.example/p1")
    second = Place("p2", "Second", "2 Street", 4.8, 120, None, "https://maps.example/p2")
    feed = render_rss(
        [(date(2026, 8, 17), [Entry(first, "low-volume", date(2026, 8, 17)), Entry(second, "improving", date(2026, 8, 17))])],
        "https://radar.example",
    )
    description = ET.fromstring(feed).findtext("./channel/item/description")
    assert description is not None
    assert description.count("<p>") == 2
    assert "First — 1 Street — 4.6 stars (42 reviews) — low-volume" in description
    assert "Second — 2 Street — 4.8 stars (120 reviews) — improving" in description
    assert '<a href="https://maps.example/p1">Google Maps</a>' in description
    assert '<a href="https://maps.example/p2">Google Maps</a>' in description
