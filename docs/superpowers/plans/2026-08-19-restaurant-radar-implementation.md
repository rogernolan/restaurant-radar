# Restaurant Radar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fixture-first Python service that stores weekly restaurant observations in SQLite and publishes a simple HTML archive and RSS feed, with a Google Places provider ready for later activation.

**Architecture:** A small Python 3.11+ package separates configuration, domain classification, providers, SQLite persistence, feed rendering, and CLI/server orchestration. Fixture data is the default and is deterministic; the Google Places adapter implements the same provider protocol and uses `GOOGLE_MAPS_API_KEY` only when explicitly selected.

**Tech Stack:** Python 3.11+, standard library (`sqlite3`, `tomllib`, `urllib`, `http.server`, `xml.etree`), pytest for tests, TOML configuration, SQLite, RSS 2.0.

## Global Constraints

- Default centre is `TN26 2JY` and default radius is `50 km`.
- Weekly generation is Monday at `19:00` in the server's local timezone.
- Low-volume classification is `10 < review_count <= 99` and `rating >= 4.5`.
- Established/improving classification is `review_count >= 100` and rating delta `>= 0.3` against a snapshot at least 30 days earlier.
- Restaurants with 0–10 reviews or without a qualifying improvement are omitted.
- Fixture mode must work without network access or a Google API key.
- API/provider failure must not replace the previously published feed.
- The project remains MIT licensed and has no frontend framework, accounts, queue, or external database.

## File Map

- Create: `pyproject.toml` — package metadata, CLI entry point, and pytest configuration.
- Create: `config.example.toml` — documented experiment defaults.
- Create: `README.md` — local run, backfill, fixture mode, Google activation, and LXC/timer instructions.
- Create: `src/restaurant_radar/__init__.py` — package version.
- Create: `src/restaurant_radar/config.py` — validated TOML settings and environment selection.
- Create: `src/restaurant_radar/models.py` — place, observation, entry, and weekly run data types.
- Create: `src/restaurant_radar/classifier.py` — mutually exclusive classification rules and historical comparison.
- Create: `src/restaurant_radar/providers.py` — provider protocol, deterministic fixtures, and Google Places HTTP adapter.
- Create: `src/restaurant_radar/store.py` — SQLite schema and atomic weekly run persistence.
- Create: `src/restaurant_radar/rss.py` — escaped RSS 2.0 rendering.
- Create: `src/restaurant_radar/web.py` — HTML archive, RSS, and health handlers.
- Create: `src/restaurant_radar/cli.py` — `run`, `backfill`, and `serve` commands.
- Create: `tests/test_config.py`, `tests/test_classifier.py`, `tests/test_provider.py`, `tests/test_store.py`, `tests/test_rss.py`, `tests/test_web.py`, `tests/test_cli.py` — focused behavior tests.

---

### Task 1: Package scaffold and configuration

**Files:**
- Create: `pyproject.toml`
- Create: `config.example.toml`
- Create: `src/restaurant_radar/__init__.py`
- Create: `src/restaurant_radar/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces `Settings` with fields `centre`, `radius_km`, `run_time`, `timezone`, the five classification thresholds, `max_places_results`, `database_path`, and `provider`.
- Produces `load_settings(path: Path) -> Settings` and `Settings.validate() -> None`.

- [ ] **Step 1: Write the failing tests.**

```python
def test_load_settings_uses_experiment_defaults(tmp_path):
    settings = load_settings(tmp_path / "missing.toml")
    assert settings.centre == "TN26 2JY"
    assert settings.radius_km == 50
    assert settings.low_volume_min_reviews == 10
    assert settings.low_volume_max_reviews == 99
    assert settings.established_min_reviews == 100
    assert settings.improvement_window_days == 30

def test_load_settings_rejects_overlapping_review_bands(tmp_path):
    path = tmp_path / "config.toml"
    path.write_text("low_volume_max_reviews = 100\nestablished_min_reviews = 100\n")
    with pytest.raises(ValueError, match="review bands"):
        load_settings(path)
```

- [ ] **Step 2: Run `python -m pytest tests/test_config.py -q`; verify it fails because the package and loader do not exist.**
- [ ] **Step 3: Implement `Settings` defaults, TOML overrides, provider default `fixtures`, and validation for positive radius/results, rating range 0–5, strict low-volume lower bound, and `low_volume_max_reviews < established_min_reviews`.**
- [ ] **Step 4: Run `python -m pytest tests/test_config.py -q`; verify both tests pass.**
- [ ] **Step 5: Commit with `git add pyproject.toml config.example.toml src tests && git commit -m "feat: add validated experiment configuration"`.**

### Task 2: Domain models and classification

**Files:**
- Create: `src/restaurant_radar/models.py`
- Create: `src/restaurant_radar/classifier.py`
- Test: `tests/test_classifier.py`

**Interfaces:**
- `Place(place_id, name, address, rating, review_count, website_url, maps_url)`.
- `Observation(place, observed_on: date)`.
- `Entry(place, category, observed_on: date)`.
- `classify(place: Place, current_date: date, prior: list[Observation], settings: Settings) -> str | None`.

- [ ] **Step 1: Write failing tests for 11–99 inclusion, 10/100 boundaries, high-score threshold, and 30-day improvement.**

```python
def test_classify_low_volume_high_score():
    place = place_with(review_count=11, rating=4.5)
    assert classify(place, date(2026, 8, 17), [], settings()) == "low-volume"

def test_classify_established_improvement_uses_snapshot_at_least_30_days_old():
    place = place_with(review_count=100, rating=4.4)
    prior = [Observation(place_with(rating=4.0, review_count=120), date(2026, 7, 18))]
    assert classify(place, date(2026, 8, 17), prior, settings()) == "improving"

def test_classify_omits_boundaries_and_non_improvement():
    assert classify(place_with(review_count=10, rating=5), date(2026, 8, 17), [], settings()) is None
    assert classify(place_with(review_count=100, rating=4.2), date(2026, 8, 17), [], settings()) is None
```

- [ ] **Step 2: Run `python -m pytest tests/test_classifier.py -q`; verify the missing model/classifier causes expected import failures.**
- [ ] **Step 3: Implement pure classification with the closest prior observation whose date is no later than `current_date - improvement_window_days`; never allow a place to receive two categories.**
- [ ] **Step 4: Run `python -m pytest tests/test_classifier.py -q`; verify all classification tests pass.**
- [ ] **Step 5: Commit with `git add src/restaurant_radar/models.py src/restaurant_radar/classifier.py tests/test_classifier.py && git commit -m "feat: classify restaurant opportunities"`.**

### Task 3: Providers and deterministic fixture history

**Files:**
- Create: `src/restaurant_radar/providers.py`
- Test: `tests/test_provider.py`

**Interfaces:**
- `PlaceProvider.search(centre: str, radius_km: int, max_results: int) -> list[Place]`.
- `FixtureProvider.for_week(week_start: date) -> list[Place]`.
- `GooglePlacesProvider(api_key: str).search(...) -> list[Place]`.
- `provider_for(settings: Settings, env: Mapping[str, str]) -> PlaceProvider`.

- [ ] **Step 1: Write failing tests that fixture output is deterministic, contains low-volume and improving scenarios, and provider selection does not require an API key in fixture mode.**

```python
def test_fixture_provider_is_deterministic():
    first = FixtureProvider().for_week(date(2026, 8, 17))
    second = FixtureProvider().for_week(date(2026, 8, 17))
    assert first == second

def test_fixture_provider_changes_improving_rating_over_weeks():
    old = by_id(FixtureProvider().for_week(date(2026, 7, 13)), "improving-1")
    new = by_id(FixtureProvider().for_week(date(2026, 8, 17)), "improving-1")
    assert new.rating > old.rating
```

- [ ] **Step 2: Run `python -m pytest tests/test_provider.py -q`; verify it fails because provider classes do not exist.**
- [ ] **Step 3: Implement fixture records with stable IDs and date-based values, plus a Google adapter using `urllib.request` and explicit JSON field mapping.**
- [ ] **Step 4: Run `python -m pytest tests/test_provider.py -q`; verify deterministic fixtures pass.**
- [ ] **Step 5: Commit with `git add src/restaurant_radar/providers.py tests/test_provider.py && git commit -m "feat: add fixture and Google Places providers"`.**

### Task 4: SQLite storage and atomic weekly generation

**Files:**
- Create: `src/restaurant_radar/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- `Store(path: Path)` with `initialize()`, `observations_for(place_id)`, `save_week(run_date, observations, entries)`, `weeks()`, and `entries_for_week(run_date)`.
- `save_week` must be idempotent for a repeated `run_date` and commit observations plus entries in one transaction.

- [ ] **Step 1: Write failing tests for schema creation, observation retrieval, repeated-week replacement, and failed transactions leaving no partial published entries.**
- [ ] **Step 2: Run `python -m pytest tests/test_store.py -q`; verify expected missing-module failures.**
- [ ] **Step 3: Implement SQLite tables for `weekly_runs`, `observations`, and `entries`, using parameterized SQL, foreign keys, ISO dates, and rollback on exceptions.**
- [ ] **Step 4: Run `python -m pytest tests/test_store.py -q`; verify all storage tests pass.**
- [ ] **Step 5: Commit with `git add src/restaurant_radar/store.py tests/test_store.py && git commit -m "feat: persist weekly observations in SQLite"`.**

### Task 5: RSS and HTML rendering

**Files:**
- Create: `src/restaurant_radar/rss.py`
- Create: `src/restaurant_radar/web.py`
- Test: `tests/test_rss.py`
- Test: `tests/test_web.py`

**Interfaces:**
- `render_rss(weeks: list[tuple[date, list[Entry]]], base_url: str) -> str`.
- `render_index(weeks: list[tuple[date, list[Entry]]]) -> str`.
- `RadarHandler` serves `/`, `/feed.xml`, `/health`, and `404` for other paths.

- [ ] **Step 1: Write failing tests for RSS title/link/description, XML escaping, website-or-Maps fallback, HTML weekly grouping, and health response.**
- [ ] **Step 2: Run `python -m pytest tests/test_rss.py tests/test_web.py -q`; verify expected missing-module failures.**
- [ ] **Step 3: Implement RSS 2.0 with `xml.etree.ElementTree`, HTML escaping with `html.escape`, content type headers, and read-only store access in the handler.**
- [ ] **Step 4: Run the focused tests; verify all pass.**
- [ ] **Step 5: Commit with `git add src/restaurant_radar/rss.py src/restaurant_radar/web.py tests/test_rss.py tests/test_web.py && git commit -m "feat: publish HTML archive and RSS feed"`.**

### Task 6: CLI orchestration, backfill, and scheduler documentation

**Files:**
- Create: `src/restaurant_radar/cli.py`
- Modify: `pyproject.toml`
- Modify: `README.md`
- Test: `tests/test_cli.py`

**Interfaces:**
- `python -m restaurant_radar.cli run [--date YYYY-MM-DD] [--provider fixtures|google]`.
- `python -m restaurant_radar.cli backfill --weeks N`.
- `python -m restaurant_radar.cli serve [--host HOST] [--port PORT]`.

- [ ] **Step 1: Write failing tests for a fixture run saving entries, a multi-week backfill producing a 30-day comparison, repeated backfill idempotency, and provider failure preserving an earlier week.**
- [ ] **Step 2: Run `python -m pytest tests/test_cli.py -q`; verify expected missing CLI failures.**
- [ ] **Step 3: Implement orchestration: load settings, select provider, normalize Monday dates, read prior observations, classify, atomically save, and return non-zero on provider errors. Make backfill use Monday dates counting backward from the requested anchor date.**
- [ ] **Step 4: Add the console script `restaurant-radar = restaurant_radar.cli:main`, document fixture usage, Google activation, `serve`, writable `data/`, and a sample cron/systemd timer invocation.**
- [ ] **Step 5: Run `python -m pytest tests/test_cli.py -q`; verify all CLI tests pass.**
- [ ] **Step 6: Commit with `git add pyproject.toml README.md src/restaurant_radar/cli.py tests/test_cli.py && git commit -m "feat: add run backfill and serve commands"`.**

### Task 7: Full verification and handoff

**Files:**
- Modify: any implementation files required by verification failures.

- [ ] **Step 1: Run `python -m pytest -q`; expected result is zero failures.**
- [ ] **Step 2: Run `python -m restaurant_radar.cli backfill --weeks 12 --config config.example.toml`; verify the SQLite database contains 12 weekly runs and the feed includes entries from fixture scenarios.**
- [ ] **Step 3: Run `python -m restaurant_radar.cli serve --host 127.0.0.1 --port 8765` in a temporary process, request `/`, `/feed.xml`, and `/health`, then stop it; verify status 200 and correct content types.**
- [ ] **Step 4: Run `git diff --check` and `git status --short`; verify no whitespace errors and only intentional files are changed.**
- [ ] **Step 5: Commit any verification fixes with a focused message, then report the exact test command, fixture smoke-test command, and local paths for deployment.**
