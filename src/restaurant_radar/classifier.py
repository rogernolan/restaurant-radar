from __future__ import annotations

from datetime import date, timedelta

from .config import Settings
from .models import Observation, Place


def classify(
    place: Place,
    current_date: date,
    prior: list[Observation],
    settings: Settings,
) -> str | None:
    if (
        settings.low_volume_min_reviews < place.review_count <= settings.low_volume_max_reviews
        and place.rating >= settings.low_volume_min_rating
    ):
        return "low-volume"

    if place.review_count < settings.established_min_reviews:
        return None

    cutoff = current_date - timedelta(days=settings.improvement_window_days)
    eligible = [observation for observation in prior if observation.observed_on <= cutoff]
    if not eligible:
        return None
    baseline = max(eligible, key=lambda observation: observation.observed_on)
    if place.rating - baseline.place.rating >= settings.improvement_min_rating_delta:
        return "improving"
    return None
