from __future__ import annotations

from datetime import date
import json
import os
from typing import Callable, Mapping, Protocol
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import Settings
from .models import Place


class ProviderError(RuntimeError):
    pass


class PlaceProvider(Protocol):
    def search(self, centre: str, radius_km: int, max_results: int) -> list[Place]: ...


class FixtureProvider:
    def for_week(self, week_start: date) -> list[Place]:
        weeks_since_anchor = max(0, (week_start - date(2026, 7, 13)).days // 7)
        improving_rating = min(4.8, 4.0 + (weeks_since_anchor * 0.1))
        return [
            Place("low-volume-1", "The Small Lantern", "1 High Street", 4.7, 40, "https://small-lantern.example", "https://maps.example/low-volume-1"),
            Place("low-volume-2", "The Quiet Spoon", "2 Station Road", 4.4, 35, None, "https://maps.example/low-volume-2"),
            Place("too-new-1", "The New Table", "3 Market Road", 5.0, 8, None, "https://maps.example/too-new-1"),
            Place("improving-1", "The Test Kitchen", "4 Church Street", improving_rating, 140 + weeks_since_anchor, None, "https://maps.example/improving-1"),
            Place("steady-1", "The Steady Plate", "5 Mill Lane", 4.2, 180, "https://steady-plate.example", "https://maps.example/steady-1"),
        ]

    def search(self, centre: str, radius_km: int, max_results: int) -> list[Place]:
        return self.for_week(date.today())[:max_results]


class GooglePlacesProvider:
    _search_url = "https://places.googleapis.com/v1/places:searchText"
    _geocode_url = "https://maps.googleapis.com/maps/api/geocode/json"
    _field_mask = ",".join(
        [
            "places.id",
            "places.displayName",
            "places.formattedAddress",
            "places.rating",
            "places.userRatingCount",
            "places.websiteUri",
            "places.googleMapsUri",
            "nextPageToken",
        ]
    )

    def __init__(self, api_key: str, opener: Callable = urlopen):
        self.api_key = api_key
        self.opener = opener

    def search(self, centre: str, radius_km: int, max_results: int) -> list[Place]:
        latitude, longitude = self._geocode(centre)
        places: list[Place] = []
        page_token: str | None = None
        while len(places) < max_results:
            body: dict[str, object] = {
                "textQuery": "restaurants",
                "pageSize": min(20, max_results - len(places)),
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": latitude, "longitude": longitude},
                        "radius": radius_km * 1000,
                    }
                },
                "includedType": "restaurant",
                "strictTypeFiltering": True,
                "regionCode": "GB",
            }
            if page_token:
                body["pageToken"] = page_token
            payload = self._json_request(self._search_url, body, method="POST")
            places.extend(self._places_from_payload(payload))
            page_token = payload.get("nextPageToken")
            if not page_token or not payload.get("places"):
                break
        return places[:max_results]

    def _geocode(self, centre: str) -> tuple[float, float]:
        url = f"{self._geocode_url}?address={quote(centre)}&key={quote(self.api_key)}"
        payload = self._json_request(url, None, method="GET")
        results = payload.get("results") or []
        try:
            location = results[0]["geometry"]["location"]
            return float(location["lat"]), float(location["lng"])
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Google geocoding returned no usable centre point") from exc

    def _json_request(self, url: str, body: dict[str, object] | None, *, method: str) -> dict:
        headers = {"X-Goog-Api-Key": self.api_key}
        if method == "POST":
            headers["Content-Type"] = "application/json"
            headers["X-Goog-FieldMask"] = self._field_mask
            request = Request(url, data=json.dumps(body).encode(), headers=headers, method=method)
        else:
            request = Request(url, headers=headers, method=method)
        try:
            response = self.opener(request)
            payload = json.loads(response.read())
            close = getattr(response, "close", None)
            if close:
                close()
        except Exception as exc:
            raise ProviderError("Google Places request failed") from exc
        if not isinstance(payload, dict):
            raise ProviderError("Google Places returned an invalid response")
        if payload.get("error"):
            raise ProviderError("Google Places returned an API error")
        return payload

    @staticmethod
    def _places_from_payload(payload: dict) -> list[Place]:
        places: list[Place] = []
        for raw in payload.get("places", []):
            try:
                place_id = str(raw["id"])
                name = str(raw["displayName"]["text"])
                address = str(raw["formattedAddress"])
                rating = float(raw["rating"])
                review_count = int(raw["userRatingCount"])
            except (KeyError, TypeError, ValueError):
                continue
            maps_url = raw.get("googleMapsUri") or f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={quote(place_id)}"
            places.append(Place(place_id, name, address, rating, review_count, raw.get("websiteUri"), maps_url))
        return places


def provider_for(settings: Settings, env: Mapping[str, str] | None = None) -> PlaceProvider:
    environment = os.environ if env is None else env
    if settings.provider == "fixtures":
        return FixtureProvider()
    api_key = environment.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ProviderError("GOOGLE_MAPS_API_KEY is required for the Google provider")
    return GooglePlacesProvider(api_key)
