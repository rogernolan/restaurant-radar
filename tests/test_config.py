from pathlib import Path

import pytest

from restaurant_radar.config import load_settings


def test_load_settings_uses_experiment_defaults(tmp_path: Path):
    settings = load_settings(tmp_path / "missing.toml")
    assert settings.centre == "TN26 2JY"
    assert settings.radius_km == 50
    assert settings.low_volume_min_reviews == 10
    assert settings.low_volume_max_reviews == 99
    assert settings.established_min_reviews == 100
    assert settings.improvement_window_days == 30


def test_load_settings_rejects_overlapping_review_bands(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text("low_volume_max_reviews = 100\nestablished_min_reviews = 100\n")
    with pytest.raises(ValueError, match="review bands"):
        load_settings(path)
