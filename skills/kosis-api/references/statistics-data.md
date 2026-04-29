# Statistics Data API

Use this file when fetching actual KOSIS numeric data.

## Primary Endpoint

```text
GET https://kosis.kr/openapi/Param/statisticsParameterData.do
```

Typical required parameters:

| Parameter | Meaning |
|---|---|
| `method=getList` | Request method |
| `apiKey` | KOSIS OpenAPI key |
| `format=json` | Response format |
| `orgId` | Organization id |
| `tblId` | Table id |
| `itmId` | Item id, often `ALL` |
| `objL1` | Classification level 1, often `ALL` or a code |
| `objL2` ... `objL8` | Additional classification levels when needed |
| `prdSe` | Period type |
| `startPrdDe` | Start period |
| `endPrdDe` | End period |

## Period Handling

Use metadata before assuming a period format.

| `prdSe` | Meaning | Period example |
|---|---|---|
| `M` | Monthly | `202401` |
| `Q` | Quarterly | `202401` for Q1 style in existing repo logic |
| `S` | Half-year | `202401` for first half style in existing repo logic |
| `Y` | Annual | `2024` |
| `F` | Multi-year | `2024` |
| `IR` | Irregular | table-specific |

## Response Notes

Common fields:

| Field | Meaning |
|---|---|
| `ORG_ID` | Organization id |
| `TBL_ID` | Table id |
| `TBL_NM` | Table name |
| `PRD_SE` | Period type |
| `PRD_DE` | Period |
| `ITM_ID`, `ITM_NM` | Item id/name |
| `UNIT_NM` | Unit |
| `DT` | Data value as a string |
| `C1`, `C1_NM` ... `C8`, `C8_NM` | Classification code/name |

`DT` is a string and can contain non-numeric markers. Normalize before arithmetic.

## KOSIS Quirks

- KOSIS JSON may be nonstandard. Prefer `src/kosis_tools/base.py` parsing utilities.
- Many tables require classification parameters beyond `objL1`.
- Some tables need fallback strategies for `objL` parameters.
- The 40,000-cell limit requires chunking by period, classification, or item.
- Fetch a narrow slice first before requesting `ALL` across many dimensions.

## Recommended Repository Path

Use `src/kosis_tools/data.py` for live data retrieval and `src/kosis_tools/transform.py` for normalization.
