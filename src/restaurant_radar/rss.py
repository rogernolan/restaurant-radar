from __future__ import annotations

from datetime import date, datetime, time, timezone
from email.utils import format_datetime
import xml.etree.ElementTree as ET

from .models import Entry


def preferred_url(entry: Entry) -> str:
    return entry.place.website_url or entry.place.maps_url


def _description(entries: list[Entry]) -> str:
    return "\n".join(
        f"{entry.place.name} — {entry.place.address} — {entry.place.rating:.1f} stars ({entry.place.review_count} reviews) — {entry.category} — {preferred_url(entry)}"
        for entry in entries
    ) or "No qualifying restaurants this week."


def render_rss(weeks: list[tuple[date, list[Entry]]], base_url: str) -> str:
    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = "Restaurant Radar"
    ET.SubElement(channel, "link").text = base_url
    ET.SubElement(channel, "description").text = "Weekly restaurant review signals."
    for week, entries in weeks:
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"Rising stars — week of {week.isoformat()}"
        ET.SubElement(item, "link").text = f"{base_url}/weeks/{week.isoformat()}"
        ET.SubElement(item, "guid").text = f"{base_url}/weeks/{week.isoformat()}"
        publication_time = datetime.combine(week, time(19), tzinfo=timezone.utc)
        ET.SubElement(item, "pubDate").text = format_datetime(publication_time)
        ET.SubElement(item, "description").text = _description(entries)
    return ET.tostring(rss, encoding="unicode", xml_declaration=True)
