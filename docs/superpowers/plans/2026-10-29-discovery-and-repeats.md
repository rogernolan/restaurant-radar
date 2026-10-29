# Restaurant discovery and repeat entries implementation plan

**Goal:** Broaden discovery, retain observation history, and publish new signals.

**Architecture:** Keep the existing provider, SQLite store, classifier, CLI and
RSS renderer. Grid discovery and Place Details belong in the Google provider;
historical ID and publication lookups belong in the store; publication decisions
belong in the weekly run. Use Python standard library and the existing pytest suite.

## Constraints

- Preserve existing history and eligibility thresholds; no schema migration.
- Use 20 km search rectangles and the configured result limit per rectangle.
- Filter all results to the original radius and deduplicate by place ID.
- Abort before saving on API errors other than missing individual places.
- Do not republish routine review-count changes.
- Exclude the current and later weeks from historical decision lookups.
- Preserve unrelated working-tree deletions.

## Tasks

- [x] Add failing provider tests for multiple rectangles, per-cell pagination,
  duplicate IDs, tracking missing IDs, closure, missing places, and API failure.
- [x] Implement rectangle searches and missing-ID details in `providers.py`;
  pass the cell size through `config.py` and `config.example.toml`.
- [x] Add failing store/CLI tests for prior IDs, prior publication lookup,
  suppression, changed signals, reruns, tracking, and atomic failures.
- [x] Implement the two historical store lookups and wire the weekly CLI run.
- [x] Run focused tests after each change, then the complete suite.
- [x] Document behavior and Google request ceilings in `README.md`.
- [x] Review the full diff and verify with live Google data in a temporary DB.

Commands: `rtk proxy .venv/bin/pytest tests/test_provider.py -q`,
`rtk proxy .venv/bin/pytest tests/test_store.py tests/test_cli.py -q`,
and `rtk proxy .venv/bin/pytest -q`. Record red/green results before completion.

## Evidence

- Baseline: 22 tests passed.
- Provider regressions: 10 failed / 4 passed before implementation; all 14 passed
  afterward. The outside-radius test also exposed unbounded old pagination.
- Historical/store/CLI regressions: 4 failed / 13 passed before implementation.
- Exact 0.3-star improvements: 2 failed before the Decimal correction.
- Complete suite: 43 passed. Independent correctness review: no material findings.
- Live Google verification against a temporary clone of the production database:
  63 search requests, 42 details requests, one geocoding request; 997 restaurants
  observed and 55 new qualifying entries. Biryanis recorded at 4.8/262 reviews;
  Corner House suppressed. Same-week rerun produced identical entries.
- The production database was unchanged by that verification.
