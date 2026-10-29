# Restaurant discovery and repeat entries

The approved correction is broader geographic discovery, continued tracking of
discovered restaurants, and suppression of unchanged feed entries.

Google discovery will search a grid of rectangles, each roughly 20 km across,
covering the configured circle. Each rectangle gets the existing paginated
search limit (60 by default). Deduplicate by Google place ID and apply the
original distance filter. A saturated rectangle emits a warning: Google's
ranked search cannot guarantee a complete directory. A fixed grid is simpler
and gives a predictable request ceiling; increasing the global result limit
cannot overcome Google's limit, while recursive subdivision adds variable cost.

Use stored observations before the run date as the tracking registry. Fetch
Place Details for known IDs missing from discovery, once per ID, and apply the
same distance and permanent-closure checks. Missing or closed businesses are
omitted; other API failures fail the run before any snapshot is saved. Existing
SQLite observations supply the registry without a schema migration.

Keep the existing eligibility bands. Publish a qualifier when there is no earlier
entry or its category or star rating differs from the most recent earlier
published entry. Review count growth alone is not a new signal. Earlier published
entries, rather than the current week's entries, make reruns deterministic.
Continue storing observations even when publication is suppressed. Do not rewrite
historical weeks automatically.

Validation covers geographic coverage, pagination and result caps per rectangle,
deduplication, refresh of missing known IDs, unavailable and closed places,
API failures preserving existing snapshots, historical tracking, repeat
suppression, category/rating changes, reruns, and the existing feed endpoints.
Compute rating improvements using decimal star values so an exact 0.3-star
increase satisfies the existing threshold without binary rounding errors.
No dependencies are added. Live verification uses a temporary database before
the scheduled service is changed.
