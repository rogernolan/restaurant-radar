from __future__ import annotations

from datetime import date
from pathlib import Path
import sqlite3

from .models import Entry, Observation, Place


class Store:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS weekly_runs (
                    run_date TEXT PRIMARY KEY,
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS observations (
                    place_id TEXT NOT NULL,
                    observed_on TEXT NOT NULL,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    rating REAL NOT NULL,
                    review_count INTEGER NOT NULL,
                    website_url TEXT,
                    maps_url TEXT NOT NULL,
                    PRIMARY KEY (place_id, observed_on)
                );
                CREATE TABLE IF NOT EXISTS entries (
                    run_date TEXT NOT NULL,
                    place_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    address TEXT NOT NULL,
                    rating REAL NOT NULL,
                    review_count INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    website_url TEXT,
                    maps_url TEXT NOT NULL,
                    PRIMARY KEY (run_date, place_id),
                    FOREIGN KEY (run_date) REFERENCES weekly_runs(run_date)
                );
                """
            )

    def observations_for(self, place_id: str) -> list[Observation]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM observations WHERE place_id = ? ORDER BY observed_on",
                (place_id,),
            ).fetchall()
        return [self._observation_from_row(row) for row in rows]

    def save_week(self, run_date: date, observations: list[Observation], entries: list[Entry]) -> None:
        run_value = run_date.isoformat()
        with self._connect() as connection:
            connection.execute("DELETE FROM entries WHERE run_date = ?", (run_value,))
            connection.execute("DELETE FROM weekly_runs WHERE run_date = ?", (run_value,))
            connection.execute("INSERT INTO weekly_runs(run_date, status) VALUES (?, 'complete')", (run_value,))
            connection.executemany(
                """
                INSERT INTO observations
                    (place_id, observed_on, name, address, rating, review_count, website_url, maps_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(place_id, observed_on) DO UPDATE SET
                    name=excluded.name, address=excluded.address, rating=excluded.rating,
                    review_count=excluded.review_count, website_url=excluded.website_url,
                    maps_url=excluded.maps_url
                """,
                [self._place_values(observation.place, observation.observed_on) for observation in observations],
            )
            connection.executemany(
                """
                INSERT INTO entries
                    (run_date, place_id, name, address, rating, review_count, category, website_url, maps_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [self._entry_values(entry, run_value) for entry in entries],
            )

    def weeks(self) -> list[date]:
        with self._connect() as connection:
            rows = connection.execute("SELECT run_date FROM weekly_runs ORDER BY run_date DESC").fetchall()
        return [date.fromisoformat(row[0]) for row in rows]

    def entries_for_week(self, run_date: date) -> list[Entry]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM entries WHERE run_date = ? ORDER BY category, name",
                (run_date.isoformat(),),
            ).fetchall()
        return [self._entry_from_row(row) for row in rows]

    def all_entries(self) -> list[tuple[date, list[Entry]]]:
        return [(run_date, self.entries_for_week(run_date)) for run_date in self.weeks()]

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _place_values(place: Place, observed_on: date) -> tuple:
        return (place.place_id, observed_on.isoformat(), place.name, place.address, place.rating, place.review_count, place.website_url, place.maps_url)

    @staticmethod
    def _entry_values(entry: Entry, run_date: str) -> tuple:
        place = entry.place
        return (run_date, place.place_id, place.name, place.address, place.rating, place.review_count, entry.category, place.website_url, place.maps_url)

    @staticmethod
    def _place_from_row(row: sqlite3.Row, prefix: str = "") -> Place:
        return Place(row[f"{prefix}place_id"], row[f"{prefix}name"], row[f"{prefix}address"], row[f"{prefix}rating"], row[f"{prefix}review_count"], row[f"{prefix}website_url"], row[f"{prefix}maps_url"])

    @classmethod
    def _observation_from_row(cls, row: sqlite3.Row) -> Observation:
        return Observation(cls._place_from_row(row), date.fromisoformat(row["observed_on"]))

    @classmethod
    def _entry_from_row(cls, row: sqlite3.Row) -> Entry:
        return Entry(cls._place_from_row(row), row["category"], date.fromisoformat(row["run_date"]))
