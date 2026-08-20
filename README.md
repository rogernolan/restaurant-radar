# Restaurant Radar

A deliberately small experiment that records weekly restaurant observations and publishes an RSS feed for two signals:

- low-volume/high-score restaurants with 11–99 reviews and a rating of at least 4.5;
- established restaurants with at least 100 reviews whose rating has improved by at least 0.3 over a 30-day window.

## Local fixture mode

Python 3.11 or newer is required. The default provider is deterministic fixture data, so the experiment works without a Google API key or network access.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[test]'
.venv/bin/restaurant-radar --config config.example.toml backfill --weeks 12
.venv/bin/restaurant-radar --config config.example.toml serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/` for the archive or subscribe to `http://127.0.0.1:8765/feed.xml`.

Use `--date YYYY-MM-DD` with `run` or `backfill` to make historical runs deterministic:

```sh
.venv/bin/restaurant-radar --config config.example.toml backfill --weeks 12 --date 2026-08-17
```

The SQLite database is created at the configured `database_path`.

## Google Places mode

Set `provider = "google"` in a local config file and provide the key only through the environment:

```sh
export GOOGLE_MAPS_API_KEY='your-key'
.venv/bin/restaurant-radar --config config.google.toml run
```

The adapter uses Google Places API (New) Text Search with the configured centre/radius and stores the returned rating, review count, address, website, and Maps URL. The key is never read from the repository.

## Weekly timer on the home server

Run the command at 19:00 on Mondays in the server's local timezone. A cron entry can be as small as:

```cron
0 19 * * 1 cd /opt/restaurant-radar && .venv/bin/restaurant-radar --config config.toml run >> data/run.log 2>&1
```

Run `serve` as the long-lived process in the LXC and expose it through Tailscale. `/health` returns `ok` for a simple monitor.

## Tests

```sh
.venv/bin/pytest -q
```
