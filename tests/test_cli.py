from datetime import date

from restaurant_radar.cli import run_command
from restaurant_radar.config import load_settings
from restaurant_radar.store import Store


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
