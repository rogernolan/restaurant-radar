from dataclasses import replace
from datetime import date

import pytest

from restaurant_radar.cli import run_command
from restaurant_radar.config import load_settings
from restaurant_radar.store import Store
from restaurant_radar.models import Entry, Observation, Place
from restaurant_radar.providers import ProviderError


def write_config(path, database_path, provider="fixtures"):
    path.write_text(f'database_path = "{database_path}"\nprovider = "{provider}"\n')


def test_backfill_creates_historical_comparison_entries(tmp_path):
    database = tmp_path / "radar.sqlite3"
    config = tmp_path / "config.toml"
    write_config(config, database)

    assert run_command(["--config", str(config), "backfill", "--weeks", "6", "--date", "2026-08-17"]) == 0
    store = Store(database)
    assert len(store.weeks()) == 6
    assert any(entry.category == "improving" for entry in store.entries_for_week(date(2026, 8, 17)))


def test_repeated_backfill_is_idempotent(tmp_path):
    database = tmp_path / "radar.sqlite3"
    config = tmp_path / "config.toml"
    write_config(config, database)

    assert run_command(["--config", str(config), "backfill", "--weeks", "2", "--date", "2026-08-17"]) == 0
    assert run_command(["--config", str(config), "backfill", "--weeks", "2", "--date", "2026-08-17"]) == 0
    assert len(Store(database).weeks()) == 2


def test_provider_failure_keeps_existing_history(tmp_path):
    database = tmp_path / "radar.sqlite3"
    fixture_config = tmp_path / "fixture.toml"
    google_config = tmp_path / "google.toml"
    write_config(fixture_config, database)
    write_config(google_config, database, provider="google")

    assert run_command(["--config", str(fixture_config), "run", "--date", "2026-08-17"]) == 0
    assert run_command(["--config", str(google_config), "run", "--date", "2026-08-24"]) == 1
    assert Store(database).weeks() == [date(2026, 8, 17)]


def restaurant(**changes):
    return replace(Place("tracked", "Corner House", "1 High Street", 5.0, 20, None, "https://maps.example/tracked"), **changes)


def test_weekly_run_suppresses_repeats_but_keeps_observing(tmp_path, monkeypatch):
    database, config = tmp_path / "radar.sqlite3", tmp_path / "config.toml"
    write_config(config, database, provider="google")
    known = []

    class Provider:
        def search(self, centre, radius_km, max_results, *, known_place_ids=()):
            known.append(known_place_ids)
            return [restaurant(review_count=20 + len(known))]

    monkeypatch.setattr("restaurant_radar.cli.provider_for", lambda settings: Provider())
    for run_date in ("2026-08-17", "2026-08-24", "2026-08-24"):
        assert run_command(["--config", str(config), "run", "--date", run_date]) == 0

    store = Store(database)
    assert len(store.entries_for_week(date(2026, 8, 17))) == 1
    assert store.entries_for_week(date(2026, 8, 24)) == []
    assert len(store.observations_for("tracked")) == 2
    assert known == [[], ["tracked"], ["tracked"]]


@pytest.mark.parametrize("changes,category", [({"rating": 4.9}, "low-volume"), ({"rating": 4.8, "review_count": 120}, "improving")])
def test_weekly_run_publishes_changed_signals_and_reruns_deterministically(tmp_path, monkeypatch, changes, category):
    database, config = tmp_path / "radar.sqlite3", tmp_path / "config.toml"
    write_config(config, database, provider="google")
    store = Store(database)
    baseline_date, previous_date, run_date = date(2026, 7, 13), date(2026, 8, 10), date(2026, 8, 17)
    baseline = restaurant(rating=4.2, review_count=110)
    store.save_week(baseline_date, [Observation(baseline, baseline_date)], [])
    prior = restaurant(rating=4.8 if category == "improving" else 5.0)
    store.save_week(previous_date, [Observation(prior, previous_date)], [Entry(prior, "low-volume", previous_date)])

    class Provider:
        def search(self, *args, **kwargs):
            return [restaurant(**changes)]

    monkeypatch.setattr("restaurant_radar.cli.provider_for", lambda settings: Provider())
    for _ in range(2):
        assert run_command(["--config", str(config), "run", "--date", run_date.isoformat()]) == 0
        assert [e.category for e in store.entries_for_week(run_date)] == [category]


def test_refresh_failure_preserves_existing_week_and_observations(tmp_path, monkeypatch):
    database, config = tmp_path / "radar.sqlite3", tmp_path / "config.toml"
    write_config(config, database, provider="google")
    store = Store(database)
    original_date = date(2026, 8, 17)
    store.save_week(original_date, [Observation(restaurant(), original_date)], [Entry(restaurant(), "low-volume", original_date)])

    class Provider:
        def search(self, *args, **kwargs):
            raise ProviderError("Google Places request failed")

    monkeypatch.setattr("restaurant_radar.cli.provider_for", lambda settings: Provider())
    assert run_command(["--config", str(config), "run", "--date", "2026-08-17"]) == 1
    assert store.observations_for("tracked")[0].place == restaurant()
    assert store.entries_for_week(original_date)[0].place == restaurant()
