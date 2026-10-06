# itr-wala engine service

A stateless HTTP service around the upstream itr-wala tax engine, plus a
builder that turns its computation into the JSON the income-tax e-filing
portal accepts. Stores nothing.

```
skills/itr-wala/scripts/    upstream engine - byte-identical to karanb192/itr-wala (CI enforces)
service/
  engine.py                 the only module that touches upstream code
  schemas.py                request/response models -> OpenAPI -> Zod in itr-assist
  core.py                   all behaviour, framework-free
  app.py                    FastAPI shell: /health /compute /build-json
  schema_store.py           vendored dept schemas: sha256 integrity + validation
  json_builder/
    ay_registry.py          AY -> dates, schema folder, builders
    itr1_builder.py         ITR-1: eligibility, return section, assembly
    codes.py                every portal enum code in one place
    schedules/              personal.py, income.py, tax.py
  schema/AY2026-27/         dept schemas, verbatim, + sources.json/SOURCES.md
  tests/                    goldens, rejections, schema conformance, HTTP contract
scripts/fetch_schemas.py    vendors the dept schemas with provenance
docs/golden-review.md       hand working for every golden figure (CA review pack)
docs/offline-utility-check.md   manual testing layer 3 + open questions
```

## Run

```bash
pip install -e ".[dev]"
python scripts/fetch_schemas.py          # once, from a machine that can reach incometax.gov.in
uvicorn service.app:app --reload --port 8000
python -m pytest                          # or: python -m unittest discover -s service/tests -t .
```

## Endpoints

| | |
|---|---|
| `GET /health` | engine version, AY, supported AYs |
| `POST /compute` `{income}` | upstream computation, both regimes + recommendation. No identity data. |
| `POST /build-json?form=ITR1&ay=2026-27` `{income, filer, regime}` | `{itr_json, form, ay, schema_version, schema_validated, warnings[], summary}` |
| `POST /parse/form16`, `POST /parse/ais` (multipart `file`, optional `password`) | `{recognised, fields[{key, value, label, confidence, source{document, page, text}}], warnings[]}` - proposals only; the app shows each one for the user to confirm |

**Errors.** `422` = the input must change: `{errors: [{code, severity, message, field}]}`, all
problems at once. `500` = our bug (schema violation, tampered schema file) - never shown to the
user as their mistake.

**Warnings** carry a severity: `info`, `review` (show the user), `blocking` (the JSON must not be
uploaded until resolved). Today every response carries at least `SOFTWARE_ID_UNREGISTERED`. The AY 2026-27
ITR-1 and ITR-4 schemas (file V1.1, `SchemaVer` Ver1.0) are vendored, so ITR-1 output is validated
against the department's schema on every build.

## Design rules

- **The builder does no tax law.** Every figure is copied from the engine, or is a filer-supplied
  breakdown (exemption lines, TDS rows, challans) that must reconcile *exactly* to an engine total.
  Mismatch -> 422, never a silent pick.
- **Unsupported means refused, not approximated.** v1 ITR-1 refuses: any capital gains (incl. the
  112A carve-out), 80D/80G/other Chapter VI-A in the old regime, TCS, multiple house properties,
  updated returns (ITR-U). Each has its own error code.
- **Belated/revised logic is the builder's job.** It picks ReturnFileSec from the dates, blocks the
  old regime on belated returns (s.115BAC(6)), and runs revised-return interest as of the original
  filing date.
- **Schemas are vendored, never edited.** A schema revision lands as a fetch + failing tests + a
  deliberate builder change.

## ITR-4

Registered in `ay_registry.py` but not implemented (`422 FORM_NOT_IMPLEMENTED`). Upstream takes
presumptive income as one pre-computed figure, so ITR-4 first needs a small layer that derives it
from gross receipts under 44AD (6%/8%), 44ADA (50%) and 44AE (per vehicle) - and it must be
upstreamable or clearly separate from the vendored engine.
