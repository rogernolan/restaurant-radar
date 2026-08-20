from dataclasses import replace
from datetime import date

from restaurant_radar.classifier import classify
from restaurant_radar.config import Settings
from restaurant_radar.models import Observation, Place


def settings() -> Settings:
    return Settings()


def place_with(*, rating: float = 4.0, review_count: int = 50) -> Place:
    return Place(
        place_id="test-place",
        name="Test Place",
        address="1 Test Street",
        rating=rating,
        review_count=review_count,
        website_url=None,
        maps_url="https://maps.example/test-place",
    )


def test_classify_low_volume_high_score():
    place = place_with(review_count=11, rating=4.5)
    assert classify(place, date(2026, 8, 17), [], settings()) == "low-volume"


def test_classify_established_improvement_uses_snapshot_at_least_30_days_old():
    place = place_with(review_count=100, rating=4.4)
    prior = [Observation(place_with(rating=4.0, review_count=120), date(2026, 7, 18))]
    assert classify(place, date(2026, 8, 17), prior, settings()) == "improving"


def test_classify_omits_boundaries_and_non_improvement():
    current = date(2026, 8, 17)
    assert classify(place_with(review_count=10, rating=5), current, [], settings()) is None
    assert classify(place_with(review_count=100, rating=4.2), current, [], settings()) is None
    recent = [Observation(place_with(rating=4.0, review_count=120), date(2026, 8, 1))]
    assert classify(place_with(review_count=120, rating=4.2), current, recent, settings()) is None


def test_classify_does_not_use_snapshot_before_full_comparison_window():
    prior = [Observation(place_with(rating=4.0, review_count=120), date(2026, 7, 19))]
    assert classify(place_with(review_count=120, rating=4.4), date(2026, 8, 17), prior, settings()) is None
