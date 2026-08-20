from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
import sys

from .classifier import classify
from .config import Settings, load_settings
from .models import Entry, Observation
from .providers import FixtureProvider, ProviderError, provider_for
from .store import Store
from .web import serve_http


def _week_start(value: date) -> date:
    return value - timedelta(days=value.weekday())


def _run_week(settings: Settings, run_date: date) -> int:
    store = Store(Path(settings.database_path))
    provider = provider_for(settings)
    if isinstance(provider, FixtureProvider):
        places = provider.for_week(run_date)
    else:
        places = provider.search(settings.centre, settings.radius_km, settings.max_places_results)
    observations = [Observation(place, run_date) for place in places]
    entries = []
    for observation in observations:
        category = classify(
            observation.place,
            run_date,
            store.observations_for(observation.place.place_id),
            settings,
        )
        if category:
            entries.append(Entry(observation.place, category, run_date))
    store.save_week(run_date, observations, entries)
    print(f"{run_date.isoformat()}: saved {len(entries)} qualifying restaurants")
    return 0


def _parse_date(value: str | None) -> date:
    return date.today() if value is None else date.fromisoformat(value)


def run_command(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="restaurant-radar")
    parser.add_argument("--config", type=Path, default=Path("config.toml"))
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("--date")
    run_parser.add_argument("--provider", choices=["fixtures", "google"])

    backfill_parser = subparsers.add_parser("backfill")
    backfill_parser.add_argument("--weeks", type=int, required=True)
    backfill_parser.add_argument("--date")

    serve_parser = subparsers.add_parser("serve")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--base-url")

    args = parser.parse_args(argv)
    settings = load_settings(args.config)
    if getattr(args, "provider", None):
        settings = replace(settings, provider=args.provider)
    try:
        if args.command == "run":
            return _run_week(settings, _week_start(_parse_date(args.date)))
        if args.command == "backfill":
            if args.weeks <= 0:
                parser.error("--weeks must be positive")
            anchor = _week_start(_parse_date(args.date))
            for offset in reversed(range(args.weeks)):
                _run_week(settings, anchor - timedelta(days=offset * 7))
            return 0
        if args.command == "serve":
            base_url = args.base_url or f"http://{args.host}:{args.port}"
            serve_http(Store(Path(settings.database_path)), args.host, args.port, base_url)
            return 0
    except ProviderError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 1


def main() -> None:
    raise SystemExit(run_command())


if __name__ == "__main__":
    main()
