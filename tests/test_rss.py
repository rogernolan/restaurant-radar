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
    assert "A &amp; B" in feed
    description = item.find("description")
    paragraph = description.find("p")
    assert "A & B" in paragraph.text
    assert '1 &lt;Street&gt;' in feed
    link = paragraph.find("a")
    assert link.get("href") == "https://maps.example/p1"
    assert link.text == "Google Maps"
    assert parsedate_to_datetime(item.findtext("pubDate")).date() == date(2026, 8, 17)


def test_rss_prefers_website_and_has_stable_week_guid():
    place = Place("p1", "The Place", "1 Street", 4.6, 42, "https://place.example", "https://maps.example/p1")
    feed = render_rss([(date(2026, 8, 17), [Entry(place, "improving", date(2026, 8, 17))])], "https://radar.example")
    item = ET.fromstring(feed).find("./channel/item")
    assert item.findtext("guid") == "https://radar.example/weeks/2026-08-17"
    link = item.find("./description/p/a")
    assert link.get("href") == "https://place.example"
    assert link.text == "Website"


def test_rss_puts_multiple_entries_on_separate_lines():
    first = Place("p1", "First", "1 Street", 4.6, 42, None, "https://maps.example/p1")
    second = Place("p2", "Second", "2 Street", 4.8, 120, None, "https://maps.example/p2")
    feed = render_rss(
        [(date(2026, 8, 17), [Entry(first, "low-volume", date(2026, 8, 17)), Entry(second, "improving", date(2026, 8, 17))])],
        "https://radar.example",
    )
    paragraphs = ET.fromstring(feed).findall("./channel/item/description/p")
    assert len(paragraphs) == 2
    assert "First" in paragraphs[0].text
    assert "Second" in paragraphs[1].text
    assert paragraphs[0].find("a").get("href") == "https://maps.example/p1"
    assert paragraphs[1].find("a").get("href") == "https://maps.example/p2"