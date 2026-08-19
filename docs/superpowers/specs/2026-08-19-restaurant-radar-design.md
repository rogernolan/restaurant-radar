# Restaurant Radar Design

## Goal

Build a deliberately small, fixture-first web service that publishes a weekly RSS feed of local restaurants showing either a high rating with 11–99 reviews or a meaningful upward rating change among restaurants with at least 100 reviews.

The service will eventually query Google Places API, but it must be useful and testable before Google billing is available.

## Product behavior

- One publication is generated for each monitoring week, on Monday evening using the server's local timezone.
- Each publication contains the qualifying restaurants found for that week.
- Each entry contains the restaurant name, address, rating and review count, classification, and a preferred link.
- The preferred link is the restaurant website when available; otherwise it is the Google Maps/review URL.
- The web UI is a simple readable archive of weekly entries.
- `/feed.xml` exposes the same weekly history as RSS.
- Historical generation is supported for testing. Fixture data is deterministic and can create several months of snapshots without claiming those snapshots came from Google historically.

## Classification

The two classifications are mutually exclusive:

1. **Low-volume / high-score**: `low_volume_min_reviews < review_count <= low_volume_max_reviews` and `rating >= low_volume_min_rating`. With the default values, this means 11–99 reviews and at least 4.5 stars.
2. **Established / improving**: `review_count >= established_min_reviews` and the current rating is at least `improvement_min_rating_delta` higher than the closest stored observation at least `improvement_window_days` earlier. With the defaults, this means at least 100 reviews and a rating improvement of at least 0.3 over 30 days.

Restaurants with 0–10 reviews, or established restaurants without the configured improvement, are omitted. A restaurant cannot qualify for both categories because the review-count bands do not overlap.

## Configuration

Configuration is stored in a checked-in example TOML file and loaded from a configurable path. The live secret is supplied through `GOOGLE_MAPS_API_KEY`, never committed.

Default settings:

```toml
centre = "TN26 2JY"
radius_km = 50
run_time = "19:00"
timezone = "server"

low_volume_min_reviews = 10
low_volume_max_reviews = 99
low_volume_min_rating = 4.5

established_min_reviews = 100
improvement_window_days = 30
improvement_min_rating_delta = 0.3

max_places_results = 60
database_path = "data/restaurant-radar.sqlite3"
```

Thresholds and the comparison window are intentionally configuration-driven so the experiment can be tuned and rerun for the last few months without code changes.

## Architecture and data flow

The application is a small Python package with no JavaScript build system, accounts, admin UI, maps, queue, or external database.

1. `restaurant_radar run` selects a provider, obtains candidate places, fetches the fields needed for each place, classifies candidates against stored observations, and saves the weekly observations and published entries in SQLite.
2. The default provider is deterministic fixture data. A Google Places provider implements the same interface and is used when explicitly enabled and `GOOGLE_MAPS_API_KEY` is available.
3. `restaurant_radar backfill` generates an explicit number or date range of historical fixture weeks. It must be deterministic and idempotent for a given database/configuration.
4. `restaurant_radar serve` serves the HTML archive at `/` and RSS at `/feed.xml`. It should also expose a minimal `/health` response for LXC/Tailscale monitoring.
5. A cron entry or systemd timer invokes the weekly run at the configured local server time.

Google Places integration will use Nearby/Text Search for candidates and Place Details for rating, review count, address, website, and Google Maps URL. The provider boundary keeps the rest of the application independent of billing availability and API response details.

## Persistence

SQLite stores:

- weekly runs, including the monitoring date and generation status;
- restaurant observations keyed by Google `place_id`, observation date, rating, review count, name, address, website, and Maps URL;
- published weekly entries with the selected classification and display fields.

The feed is only updated after a run has produced a valid result. A provider/API failure leaves the existing feed and history intact and returns a clear non-zero CLI status.

## Testing

Tests will cover:

- configuration defaults, overrides, and validation;
- the 11–99 low-volume boundary and high-score rule;
- the 100+ established boundary and 30-day rating comparison;
- exclusion of restaurants outside both categories;
- deterministic and idempotent fixture backfills;
- SQLite persistence and retrieval;
- RSS item content and stable links;
- HTML, RSS, and health endpoints;
- provider error behavior without replacing the previous feed.

The initial implementation should use the Python standard library wherever practical, with only small dependencies justified by the chosen TOML/runtime support. Tests must not require network access or a Google API key.

## Deployment boundary

The service will be deployable as a simple Python process in an LXC on the home server and reachable over Tailscale. Deployment automation and hardening are outside this initial experiment; the service must document its start command, required environment variable, writable data directory, and timer invocation.

## Explicit non-goals

- Scraping Google Maps pages.
- Inspecting every individual Google review or claiming that every review is high.
- User accounts, subscriptions, notifications, analytics, or a management dashboard.
- Real-time updates or intra-week alerts.
- A frontend framework or mobile app.
