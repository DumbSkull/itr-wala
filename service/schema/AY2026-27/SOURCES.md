# Vendored department files - AY2026-27

**Not vendored yet.** Run `python scripts/fetch_schemas.py` from a machine that can
reach incometax.gov.in (or download by hand and use `--from-dir`). The script writes
the schemas here, records url / sha256 / retrieval time in `sources.json`, and
regenerates this file.

Until then `/build-json` returns `schema_validated: false` with a blocking
`SCHEMA_NOT_VENDORED` warning, and the schema-conformance tests skip.
