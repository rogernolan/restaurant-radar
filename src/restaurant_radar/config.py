from __future__ import annotations

from dataclasses import dataclass, fields
from pathlib import Path
import tomllib


@dataclass(frozen=True)
class Settings:
    centre: str = "TN26 2JY"
    radius_km: int = 50
    run_time: str = "19:00"
    timezone: str = "server"
    provider: str = "fixtures"
    low_volume_min_reviews: int = 10
    low_volume_max_reviews: int = 99
    low_volume_min_rating: float = 4.5
    established_min_reviews: int = 100
    improvement_window_days: int = 30
    improvement_min_rating_delta: float = 0.3
    max_places_results: int = 60
    database_path: str = "data/restaurant-radar.sqlite3"

    def validate(self) -> None:
        if not self.centre.strip():
            raise ValueError("centre must not be empty")
        if self.radius_km <= 0 or self.max_places_results <= 0:
            raise ValueError("radius and max places results must be positive")
        if not 0 <= self.low_volume_min_rating <= 5:
            raise ValueError("low-volume rating must be between 0 and 5")
        if self.low_volume_min_reviews < 0:
            raise ValueError("low-volume minimum reviews must not be negative")
        if self.low_volume_max_reviews <= self.low_volume_min_reviews:
            raise ValueError("low-volume review range must have a positive width")
        if self.low_volume_max_reviews >= self.established_min_reviews:
            raise ValueError("review bands must not overlap")
        if self.established_min_reviews <= 0 or self.improvement_window_days <= 0:
            raise ValueError("established minimum and improvement window must be positive")
        if self.improvement_min_rating_delta < 0:
            raise ValueError("improvement delta must not be negative")
        if self.provider not in {"fixtures", "google"}:
            raise ValueError("provider must be fixtures or google")


def load_settings(path: Path) -> Settings:
    values: dict[str, object] = {}
    if path.exists():
        with path.open("rb") as config_file:
            values = tomllib.load(config_file)
    allowed = {field.name for field in fields(Settings)}
    unknown = set(values) - allowed
    if unknown:
        raise ValueError(f"unknown settings: {', '.join(sorted(unknown))}")
    settings = Settings(**values)
    settings.validate()
    return settings
