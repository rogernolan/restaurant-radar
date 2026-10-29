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


def test_known_place_ids_only_includes_observations_before_run_date(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    for day, place_id in [(17, "first"), (24, "second"), (31, "future")]:
        observed_on = date(2026, 8, day)
        store.save_week(observed_on, [Observation(place(place_id), observed_on)], [])

    assert store.known_place_ids(date(2026, 8, 24)) == ["first"]
    assert store.known_place_ids(date(2026, 9, 1)) == ["first", "future", "second"]


def test_previous_entry_uses_latest_published_signal_before_current_week(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    original = place()
    changed = Place(original.place_id, original.name, original.address, 4.8, 45, None, original.maps_url)
    for day, value in [(17, original), (24, changed), (31, original)]:
        observed_on = date(2026, 8, day)
        store.save_week(observed_on, [Observation(value, observed_on)], [Entry(value, "low-volume", observed_on)])

    assert store.previous_entry(original.place_id, date(2026, 8, 17)) is None
    assert store.previous_entry(original.place_id, date(2026, 8, 31)).place.rating == 4.8


def test_replacing_a_week_removes_stale_observations_but_preserves_prior_weeks(tmp_path):
    store = Store(tmp_path / "radar.sqlite3")
    for day in (17, 24):
        observed_on = date(2026, 8, day)
        store.save_week(observed_on, [Observation(place(), observed_on)], [])
    store.save_week(date(2026, 8, 24), [], [])

    assert [o.observed_on for o in store.observations_for("place-1")] == [date(2026, 8, 17)]
