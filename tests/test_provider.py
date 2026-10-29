import json
from datetime import date
from urllib.error import HTTPError

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

    def opener(request, **kwargs):
        requests.append(request)
        payload = responses.pop(0)
        return type("Response", (), {"read": lambda self: json.dumps(payload).encode()})()

    provider = GooglePlacesProvider("not-printed", opener=opener)
    places = provider.search("TN26 2JY", 10, 21)
    assert places[0].name == "The Test Kitchen"
    assert places[0].review_count == 42
    assert len(responses) == 0
    search_body = json.loads(requests[1].data)
    assert "locationRestriction" in search_body
    assert "locationBias" not in search_body


def test_google_provider_wraps_api_errors():
    def opener(request, **kwargs):
        raise OSError("offline")

    with pytest.raises(ProviderError, match="Google Places request failed"):
        GooglePlacesProvider("not-printed", opener=opener).search("TN26 2JY", 50, 1)


def google_place(place_id="restaurant-1", **changes):
    raw = {
        "id": place_id,
        "displayName": {"text": "A Restaurant"},
        "formattedAddress": "1 High Street",
        "rating": 4.8,
        "userRatingCount": 42,
        "location": {"latitude": 51.1, "longitude": 0.7},
        "businessStatus": "OPERATIONAL",
    }
    raw.update(changes)
    return raw


def response(payload):
    return type("Response", (), {"read": lambda self: json.dumps(payload).encode()})()


def test_google_search_covers_area_with_multiple_rectangles_and_deduplicates():
    rectangles = []

    def opener(request, **kwargs):
        if request.method == "GET":
            return response({"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]})
        rectangles.append(json.loads(request.data)["locationRestriction"]["rectangle"])
        return response({"places": [google_place(), google_place(f"local-{len(rectangles)}")]})

    places = GooglePlacesProvider("not-printed", opener=opener).search("TN26 2JY", 20, 60)

    assert len(rectangles) == 4
    assert len({json.dumps(rectangle, sort_keys=True) for rectangle in rectangles}) == 4
    assert len(places) == 5
    assert sum(p.place_id == "restaurant-1" for p in places) == 1
    assert min(r["low"]["latitude"] for r in rectangles) < 51.1 - 0.17
    assert max(r["high"]["latitude"] for r in rectangles) > 51.1 + 0.17
    assert min(r["low"]["longitude"] for r in rectangles) < 0.7 - 0.28
    assert max(r["high"]["longitude"] for r in rectangles) > 0.7 + 0.28


def test_google_result_limit_applies_per_rectangle_before_radius_filtering(caplog):
    searches = []

    def opener(request, **kwargs):
        if request.method == "GET":
            return response({"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]})
        body = json.loads(request.data)
        searches.append(body)
        assert len(searches) <= 4, "pagination fetched beyond the per-rectangle limit"
        return response({"places": [google_place(f"outside-{len(searches)}", location={"latitude": 0, "longitude": 0})], "nextPageToken": "more"})

    assert GooglePlacesProvider("not-printed", opener=opener).search("TN26 2JY", 20, 1) == []
    assert len(searches) == 4
    assert all("pageToken" not in body for body in searches)
    assert "limit" in caplog.text.lower()


def test_google_refreshes_known_ids_missing_from_search_once():
    details = []

    def opener(request, **kwargs):
        if "geocode" in request.full_url:
            return response({"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]})
        if request.method == "POST":
            return response({"places": [google_place("discovered")]})
        details.append(request)
        return response(google_place("tracked", userRatingCount=261))

    places = GooglePlacesProvider("not-printed", opener=opener).search(
        "TN26 2JY", 10, 60, known_place_ids=["tracked", "discovered", "tracked"]
    )

    assert {p.place_id for p in places} == {"discovered", "tracked"}
    assert len(details) == 1
    assert details[0].full_url.endswith("/places/tracked")
    mask = details[0].get_header("X-goog-fieldmask")
    assert "rating" in mask and "places.rating" not in mask
    assert "nextPageToken" not in mask


@pytest.mark.parametrize("case", ["not-found", "closed", "outside", "unrated"])
def test_google_omits_unavailable_known_places(case):
    def opener(request, **kwargs):
        if "geocode" in request.full_url:
            return response({"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]})
        if request.method == "POST":
            return response({"places": []})
        if case == "not-found":
            raise HTTPError(request.full_url, 404, "Not Found", {}, None)
        raw = google_place("tracked")
        if case == "closed":
            raw["businessStatus"] = "CLOSED_PERMANENTLY"
        if case == "outside":
            raw["location"] = {"latitude": 0, "longitude": 0}
        if case == "unrated":
            del raw["rating"]
        return response(raw)

    assert GooglePlacesProvider("not-printed", opener=opener).search(
        "TN26 2JY", 10, 60, known_place_ids=["tracked"]
    ) == []


def test_google_tracking_errors_fail_the_run():
    def opener(request, **kwargs):
        if "geocode" in request.full_url:
            return response({"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]})
        if request.method == "POST":
            return response({"places": []})
        raise HTTPError(request.full_url, 403, "Forbidden", {}, None)

    with pytest.raises(ProviderError, match="request failed"):
        GooglePlacesProvider("not-printed", opener=opener).search(
            "TN26 2JY", 10, 60, known_place_ids=["tracked"]
        )


def test_google_omits_permanently_closed_search_results():
    def opener(request, **kwargs):
        if request.method == "GET":
            return response({"results": [{"geometry": {"location": {"lat": 51.1, "lng": 0.7}}}]})
        return response({"places": [google_place(businessStatus="CLOSED_PERMANENTLY")]})

    assert GooglePlacesProvider("not-printed", opener=opener).search("TN26 2JY", 10, 60) == []
