# Official KOSIS API Index

Use this file when the task is to understand which KOSIS OpenAPI service group applies.

Official sources checked on 2026-04-29:

- KOSIS OpenAPI service introduction: https://kosis.kr/openapi/introduce/introduce_01List.do
- KOSIS statistics data guide: https://kosis.kr/openapi/devGuide/devGuide_0203List.do
- KOSIS OpenAPI PDF manual: https://kosis.kr/openapi/file/openApi_manual_v1.0.pdf

## Service Groups

KOSIS documents 7 OpenAPI service groups:

| Group | Purpose | Common formats | Repo area |
|---|---|---|---|
| Statistics list | Hierarchical statistics service list | SDMX, JSON | `list_categories.py`, `search.py` |
| Statistics data | Numeric table data and metadata | SDMX, JSON | `data.py`, `table_meta.py` |
| Large statistics data | Large table data | SDMX, XLS | `big_data.py` |
| Statistics explanation | Survey/statistics explanatory metadata | XML, JSON | `stats_explanation.py` |
| Table explanation | Table name, period, classifications, items, units | XML, JSON | `table_meta.py` |
| KOSIS integrated search | KOSIS search results | JSON | `search.py`, `metadata_fetcher.py` |
| Key indicators | Major statistical indicators | XML, JSON | `key_indicators.py` |

## Limits

Official introduction documents:

- Rate limit: 1,000 calls per minute.
- Ordinary statistics data: 40,000 cells per request.
- Large statistics data: 40,000 cells for SDMX and 200,000 cells for XLS.

## Usage Rule

For an unknown user question, route through:

1. Statistics list or integrated search to find candidate tables.
2. Table explanation / metadata to understand classifications, items, units, and period.
3. Statistics data to fetch numeric records.
4. Large statistics data only when ordinary calls exceed limits or require registered large-data flow.
