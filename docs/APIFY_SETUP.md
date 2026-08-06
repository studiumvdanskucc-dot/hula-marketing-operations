# Retired X connector

Pipeline 4.0 does not query X or start Apify Actors. No `APIFY_TOKEN` or X task
is needed for trend discovery, Google validation, catalogue matching or the
Wednesday blog.

The legacy connector remains in the source tree only so older snapshots and
offline regression fixtures can be read safely. It is not exposed in the
Build 2026.08.06.4 interface or weekly workflow.

Use [recent fashion-editorial sources](COMMERCIAL_SOURCES.md) for discovery and
[Google Trends](GOOGLE_TRENDS_SETUP.md) for measured validation.
