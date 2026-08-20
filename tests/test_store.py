from datetime import date
import sqlite3

import pytest

from restaurant_radar.models import Entry, Observation, Place
from restaurant_radar.store import Store


def place(place_id="place-1"):
    return Place(place_id, "The Place", "1 Street", 4.6, 42, None, "https://maps.example/place-1")


def test_store_persists_observations_and_entries(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    observed_on = date(2026, 8, 17)
    store.save_week(observed_on, [Observation(place(), observed_on)], [Entry(place(), "low-volume", observed_on)])

    assert store.weeks() == [observed_on]
    assert store.observations_for("place-1")[0].place == place()
    assert store.entries_for_week(observed_on)[0].category == "low-volume"


def test_store_repeating_a_week_is_idempotent(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    observed_on = date(2026, 8, 17)
    store.save_week(observed_on, [Observation(place(), observed_on)], [Entry(place(), "low-volume", observed_on)])
    changed = place()
    changed = Place(changed.place_id, changed.name, changed.address, 4.8, changed.review_count, changed.website_url, changed.maps_url)
    store.save_week(observed_on, [Observation(changed, observed_on)], [Entry(changed, "low-volume", observed_on)])

    assert len(store.observations_for("place-1")) == 1
    assert store.observations_for("place-1")[0].place.rating == 4.8


def test_store_rolls_back_a_failed_week(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    observed_on = date(2026, 8, 17)
    with pytest.raises(sqlite3.IntegrityError):
        store.save_week(
            observed_on,
            [Observation(place(), observed_on)],
            [Entry(place(), "low-volume", observed_on), Entry(place(), "improving", observed_on)],
        )
    assert store.weeks() == []
