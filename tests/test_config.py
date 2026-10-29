from pathlib import Path

import pytest

from restaurant_radar.config import load_settings


def test_load_settings_uses_experiment_defaults(tmp_path: Path):
    settings = load_settings(tmp_path / "missing.toml")
    assert settings.centre == "TN26 2JY"
    assert settings.radius_km == 30
    assert settings.low_volume_min_reviews == 10
    assert settings.low_volume_max_reviews == 99
    assert settings.low_volume_min_rating == 4.7
    assert settings.established_min_reviews == 100
    assert settings.improvement_window_days == 30
    assert settings.search_cell_km == 20


def test_load_settings_rejects_overlapping_review_bands(tmp_path: Path):
    path = tmp_path / "config.toml"
    path.write_text("low_volume_max_reviews = 100\nestablished_min_reviews = 100\n")
    with pytest.raises(ValueError, match="review bands"):
        load_settings(path)


@pytest.mark.parametrize("cell_size", [0, -1])
def test_search_cell_size_must_be_positive(tmp_path, cell_size):
    path = tmp_path / "config.toml"
    path.write_text(f"search_cell_km = {cell_size}\n")
    with pytest.raises(ValueError, match="search cell"):
        load_settings(path)
