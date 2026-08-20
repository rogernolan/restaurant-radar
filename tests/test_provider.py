import json
from datetime import date
from urllib.parse import urlparse

import pytest

from restaurant_radar.config import Settings
from restaurant_radar.providers import FixtureProvider, GooglePlacesProvider, ProviderError, provider_for


def by_id(places, place_id):
    return next(place for place in places if place.place_id == place_id)


def test_fixture_provider_is_deterministic():
    first = FixtureProvider().for_week(date(2026, 8, 17))
    second = FixtureProvider().for_week(date(2026, 8, 17))
    assert first == second


def test_fixture_provider_changes_improving_rating_over_weeks():
    old = by_id(FixtureProvider().for_week(date(2026, 7, 13)), "improving-1")
    new = by_id(FixtureProvider().for_week(date(2026, 8, 17)), "improving-1")
    assert new.rating > old.rating


def test_fixture_provider_is_selected_without_an_api_key():
    assert isinstance(provider_for(Settings(), {}), FixtureProvider)


def test_google_provider_maps_places_response_and_paginates():
    requests = []
    responses = [
        {"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]},
        {
            "places": [{
                "id": "google-1",
                "displayName": {"text": "The Test Kitchen"},
                "formattedAddress": "1 High Street",
                "rating": 4.6,
                "userRatingCount": 42,
                "location": {"latitude": 51.1, "longitude": 0.7},
                "websiteUri": "https://example.test",
                "googleMapsUri": "https://maps.google.test/google-1",
            }],
            "nextPageToken": "next",
        },
        {"places": []},
    ]

    def opener(request):
        requests.append(request)
        payload = responses.pop(0)
        return type("Response", (), {"read": lambda self: json.dumps(payload).encode()})()

    provider = GooglePlacesProvider("not-printed", opener=opener)
    places = provider.search("TN26 2JY", 50, 21)
    assert places[0].name == "The Test Kitchen"
    assert places[0].review_count == 42
    assert len(responses) == 0
    search_body = json.loads(requests[1].data)
    assert "locationBias" in search_body
    assert "locationRestriction" not in search_body


def test_google_provider_wraps_api_errors():
    def opener(request):
        raise OSError("offline")

    with pytest.raises(ProviderError, match="Google Places request failed"):
        GooglePlacesProvider("not-printed", opener=opener).search("TN26 2JY", 50, 1)
