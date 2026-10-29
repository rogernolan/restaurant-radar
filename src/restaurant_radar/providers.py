from __future__ import annotations

from datetime import date
import json
import logging
import math
import os
from typing import Callable, Iterable, Mapping, Protocol
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from .config import Settings
from .models import Place


class ProviderError(RuntimeError):
    pass


class PlaceProvider(Protocol):
    def search(self, centre: str, radius_km: int, max_results: int, *, known_place_ids: Iterable[str] = ()) -> list[Place]: ...


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

    def search(self, centre: str, radius_km: int, max_results: int, *, known_place_ids: Iterable[str] = ()) -> list[Place]:
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
            "places.location",
            "places.businessStatus",
            "nextPageToken",
        ]
    )

    def __init__(self, api_key: str, opener: Callable = urlopen, *, search_cell_km: int = 20):
        self.api_key = api_key
        self.opener = opener
        self.search_cell_km = search_cell_km

    def search(self, centre: str, radius_km: int, max_results: int, *, known_place_ids: Iterable[str] = ()) -> list[Place]:
        point = self._geocode(centre)
        places: dict[str, Place] = {}
        seen_ids: set[str] = set()
        for rectangle in _search_rectangles(point, radius_km, self.search_cell_km):
            payloads = self._search_rectangle(rectangle, min(max_results, 60))
            for payload in payloads:
                seen_ids.update(raw["id"] for raw in payload.get("places", []) if isinstance(raw, dict) and "id" in raw)
                places.update((place.place_id, place) for place in self._places_from_payload(payload, point, radius_km))
        details_mask = ",".join(field.removeprefix("places.") for field in self._field_mask.split(",") if field != "nextPageToken")
        for place_id in sorted(set(known_place_ids) - seen_ids):
            payload = self._json_request(
                f"https://places.googleapis.com/v1/places/{quote(place_id, safe='')}",
                None, method="GET", field_mask=details_mask, missing_ok=True,
            )
            places.update((place.place_id, place) for place in self._places_from_payload({"places": [payload]}, point, radius_km))
        return list(places.values())

    def _search_rectangle(self, rectangle: dict, max_results: int) -> list[dict]:
        payloads = []
        raw_count = 0
        page_token: str | None = None
        while raw_count < max_results:
            body: dict[str, object] = {
                "textQuery": "restaurants",
                "pageSize": min(20, max_results - raw_count),
                "locationRestriction": {"rectangle": rectangle},
                "includedType": "restaurant",
                "strictTypeFiltering": True,
                "regionCode": "GB",
            }
            if page_token:
                body["pageToken"] = page_token
            payload = self._json_request(self._search_url, body, method="POST")
            payloads.append(payload)
            raw_count += len(payload.get("places", []))
            page_token = payload.get("nextPageToken")
            if not page_token or not payload.get("places"):
                break
        if raw_count >= max_results:
            logging.getLogger(__name__).warning("Search rectangle reached its %s-result limit; discovery may be incomplete", max_results)
        return payloads

    def _geocode(self, centre: str) -> tuple[float, float]:
        url = f"{self._geocode_url}?address={quote(centre)}&key={quote(self.api_key)}"
        payload = self._json_request(url, None, method="GET")
        results = payload.get("results") or []
        try:
            location = results[0]["geometry"]["location"]
            return float(location["lat"]), float(location["lng"])
        except (IndexError, KeyError, TypeError, ValueError) as exc:
            raise ProviderError("Google geocoding returned no usable centre point") from exc

    def _json_request(self, url: str, body: dict[str, object] | None, *, method: str, field_mask: str | None = None, missing_ok: bool = False) -> dict:
        headers = {"X-Goog-Api-Key": self.api_key}
        if field_mask:
            headers["X-Goog-FieldMask"] = field_mask
        if method == "POST":
            headers["Content-Type"] = "application/json"
            headers["X-Goog-FieldMask"] = self._field_mask
            request = Request(url, data=json.dumps(body).encode(), headers=headers, method=method)
        else:
            request = Request(url, headers=headers, method=method)
        response = None
        try:
            response = self.opener(request, timeout=30)
            payload = json.loads(response.read())
        except HTTPError as exc:
            if missing_ok and exc.code == 404:
                return {}
            raise ProviderError("Google Places request failed") from exc
        except Exception as exc:
            raise ProviderError("Google Places request failed") from exc
        finally:
            close = getattr(response, "close", None)
            if close:
                close()
        if not isinstance(payload, dict):
            raise ProviderError("Google Places returned an invalid response")
        if payload.get("error"):
            raise ProviderError("Google Places returned an API error")
        return payload

    @staticmethod
    def _places_from_payload(payload: dict, centre: tuple[float, float], radius_km: int) -> list[Place]:
        places: list[Place] = []
        for raw in payload.get("places", []):
            if not isinstance(raw, dict) or raw.get("businessStatus") == "CLOSED_PERMANENTLY":
                continue
            try:
                place_id = str(raw["id"])
                name = str(raw["displayName"]["text"])
                address = str(raw["formattedAddress"])
                rating = float(raw["rating"])
                review_count = int(raw["userRatingCount"])
            except (KeyError, TypeError, ValueError):
                continue
            location = raw.get("location") or {}
            try:
                if _distance_km(centre, (float(location["latitude"]), float(location["longitude"]))) > radius_km:
                    continue
            except (KeyError, TypeError, ValueError):
                continue
            maps_url = raw.get("googleMapsUri") or f"https://www.google.com/maps/search/?api=1&query=Google&query_place_id={quote(place_id)}"
            places.append(Place(place_id, name, address, rating, review_count, raw.get("websiteUri"), maps_url))
        return places


def _distance_km(first: tuple[float, float], second: tuple[float, float]) -> float:
    latitude_1, longitude_1 = map(math.radians, first)
    latitude_2, longitude_2 = map(math.radians, second)
    delta_latitude = latitude_2 - latitude_1
    delta_longitude = longitude_2 - longitude_1
    haversine = math.sin(delta_latitude / 2) ** 2 + math.cos(latitude_1) * math.cos(latitude_2) * math.sin(delta_longitude / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(haversine))


def _search_rectangles(centre: tuple[float, float], radius_km: int, cell_km: int) -> Iterable[dict]:
    latitude, longitude = centre
    angular_radius = radius_km / 6371.0
    latitude_delta = math.degrees(angular_radius)
    south, north = max(-90.0, latitude - latitude_delta), min(90.0, latitude + latitude_delta)
    longitude_delta = 180.0 if south == -90 or north == 90 else math.degrees(math.asin(min(1.0, math.sin(angular_radius) / math.cos(math.radians(latitude)))))
    side_count = max(1, math.ceil(2 * radius_km / cell_km))
    for row in range(side_count):
        for column in range(side_count):
            yield {
                "low": {
                    "latitude": south + (north - south) * row / side_count,
                    "longitude": (longitude - longitude_delta + 2 * longitude_delta * column / side_count + 180) % 360 - 180,
                },
                "high": {
                    "latitude": south + (north - south) * (row + 1) / side_count,
                    "longitude": (longitude - longitude_delta + 2 * longitude_delta * (column + 1) / side_count + 180) % 360 - 180,
                },
            }


def provider_for(settings: Settings, env: Mapping[str, str] | None = None) -> PlaceProvider:
    environment = os.environ if env is None else env
    if settings.provider == "fixtures":
        return FixtureProvider()
    api_key = environment.get("GOOGLE_MAPS_API_KEY")
    if not api_key:
        raise ProviderError("GOOGLE_MAPS_API_KEY is required for the Google provider")
    return GooglePlacesProvider(api_key, search_cell_km=settings.search_cell_km)
