# Acts registry (`config/acts/`)

Declarative Act registrations for the Bangladesh Legal RAG (FR-CM-4). Each `*.yaml` file
describes one Act and the bdlaws sources to ingest for it. The files are the source of truth;
the database is reconciled from them via the bootstrap command.

**bdlaws portal index:** http://bdlaws.minlaw.gov.bd/laws-of-bangladesh-alphabetical-index.html

The full portal index (1556 Acts) is cached at `config/bdlaws-acts-index.json` for reference
when adding new Acts to the corpus.

> Authoritative spec: `docs/01-SRS.md` (FR-CM-*, FR-IN-*) and `docs/02-Architecture.md` §2.2.
> Author: **Al Amin Ahamed**.

## File schema

```yaml
slug: labour-act-2006                         # required — unique registry key
short_name: Labour Act 2006                   # required — display name (short)
full_name_en: The Bangladesh Labour Act, 2006 # required
full_name_bn: বাংলাদেশ শ্রম আইন, ২০০৬        # required
act_number: XLII                              # required — Roman numeral act number
act_year: 2006                                # required
ministry: Ministry of Labour and Employment   # optional
status: in_force                              # in_force | partially_repealed | repealed

sources:
  - language: bn
    source_url: https://bdlaws.minlaw.gov.bd/act-952.html
  - language: en
    source_url: https://bdlaws.minlaw.gov.bd/act-952.html
```

Each source is one `(act, language)` Celery task. Both `bn` and `en` sources should be declared
for full bilingual coverage. A source without a matching page on bdlaws will fail its ingestion
task without affecting sibling tasks.

## v1.0 Acts

| File | Act |
|---|---|
| `companies-act-1994.yaml` | The Companies Act, 1994 (XVIII of 1994) |
| `income-tax-act-2023.yaml` | The Income Tax Act, 2023 (XII of 2023) |
| `vat-sd-act-2012.yaml` | The Value Added Tax and Supplementary Duty Act, 2012 |
| `labour-act-2006.yaml` | The Bangladesh Labour Act, 2006 (XLII of 2006) |
| `digital-security-act-2018.yaml` | The Digital Security Act, 2018 (XLVI of 2018) |

## Bootstrapping into the database

```bash
cd apps/api
BDRAG_DATABASE_DSN=postgresql+asyncpg://bdrag:bdrag@localhost:5432/bdrag \
  uv run python -m app.ingestion.registry bootstrap
```

The bootstrap command is idempotent: it upserts Acts and their sources. Re-running it picks up
new YAML files without touching existing database rows or their ingestion history.

After bootstrapping, trigger ingestion to populate the corpus:

```bash
# All Acts:
curl -X POST "$API/api/v1/admin/ingest" -H "Authorization: Bearer $TOKEN"

# One Act:
curl -X POST "$API/api/v1/admin/ingest/<slug>" -H "Authorization: Bearer $TOKEN"
```

## Adding a new Act

1. Create `config/acts/<slug>.yaml` following the schema above.
2. Run `python -m app.ingestion.registry bootstrap`.
3. Trigger ingestion for the new slug.
4. Add ≥ 8 golden records (4 BN + 4 EN) to `apps/api/eval/dataset/golden.jsonl`.
5. Run `python -m eval.harness` — thresholds must still hold.

Only Acts published at `bdlaws.minlaw.gov.bd` belong here — the corpus must remain grounded in
authoritative primary sources.
