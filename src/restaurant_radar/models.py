from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class Place:
    place_id: str
    name: str
    address: str
    rating: float
    review_count: int
    website_url: str | None
    maps_url: str


@dataclass(frozen=True)
class Observation:
    place: Place
    observed_on: date


@dataclass(frozen=True)
class Entry:
    place: Place
    category: str
    observed_on: date
