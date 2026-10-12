# School explorer and crime maps

## School explorer

Independent implementation of public school-search functionality, informed by the publicly visible feature descriptions at https://www.locrating.com/. No Locrating data, code, reviews or catchment predictions are used.

- Adjustable straight-line radius, map, name/phase/type/gender/admissions/religion filters, distance/name sort; maximum 1,000 nearby records, with total count and truncation notice.
- National England name search, 25 results per search; open GIAS establishments with coordinates only.
- Up to four locally saved schools can be compared. Comparison aligns stage, school year, subject and indicator; missing/suppressed values remain explicit.
- Reading School and The Piggott School quick links and official admissions sources. Distance is not catchment or an admission guarantee. Published capacity is not a count of available places.

### Sources, keys, refresh and fallback

GIAS: https://www.get-information-schools.service.gov.uk/Downloads — DfE, OGL v3.0, no API key. Existing `scripts/import_data.py` schools importer indexes open establishments and their coordinates in SQLite. Import a newer official download to refresh. If absent, the app reports setup required rather than inventing schools.

DfE Explore Education Statistics API: https://api.education.gov.uk/statistics/docs/ — public, no key. Official metadata, total-cohort school-level results queried by URN, pinned to the same dataset version; cached seven days. Datasets:

| Stage | Dataset ID |
|---|---|
| KS2 | 019afee4-e5d0-72f9-9a8f-d7a1a56eac1d |
| KS4 | 19e39901-a96c-be76-b9c2-6af54ae076d2 |
| KS5 | 019c2960-81e3-70c2-8d65-72c3718ae4fd |

Crown copyright / OGL v3.0, subject to each release's notices. The app requests selected indicators on demand for an individual school; it does not issue national batches on page load. All required Total filters are checked together locally. A-level cohort is used for KS5. School years differ by release; missing Progress 8 is never inferred. On source failure, cached data follow the shared cache policy, otherwise the affected stage is marked unavailable. Official performance links remain available. URN changes are not silently merged.

Ofsted: https://www.gov.uk/government/statistical-data-sets/monthly-management-information-ofsteds-school-inspections-outcomes — Crown copyright, OGL v3.0, no key. Import the official 31 August 2026 snapshot:

```sh
python scripts/import_ofsted.py --download
```

Or pass a local compatible CSV. The importer preserves renewed EIF, earlier EIF and ungraded inspection dates and original inspection URNs separately. This snapshot is not automatically refreshed; update the download URL and vintage together for future releases. No new overall grade is fabricated from older inspections. If no imported match exists, official Ofsted links remain available.

## Crime map

Police.uk public API, no key. Latest available month; circle radius 0.1–16.1 km (up to 10 miles), viewport rectangle or a rectangle selected by clicking two corners. Bounds are limited to 400 km² and within 25 km of the postcode centre. Precise geometric filtering follows the polygon query. Counts distinguish crime from antisocial behaviour, with category filters and grouped location markers. Published police locations are anonymised approximations, not exact incident addresses. Data absence/API failure is not zero crime. Large queries can be rejected by Police.uk; reduce the area. The visible table is capped at 200 events; counts/map/JSON retain the full fetched set.

Leaflet 1.9.4 is vendored with its BSD-2-Clause licence at `app/static/vendor/leaflet/LICENSE`. Map tiles come from OpenStreetMap with visible attribution, normal browser caching and no offline prefetch. Tile policy: https://operations.osmfoundation.org/policies/tiles/. Tile failure leaves the data table available.


## 22 September 2026: map origin and school sidebar

Python remains the active implementation; the older PHP export is not maintained.
Right-click the school map and choose the displayed action, or use the point-selection
button. The home marker is draggable. A selected school gets a measurement line and
miles/metres using Leaflet's spherical straight-line distance. The radius query follows
the selected point; resetting restores the postcode centre. A pin is a coordinate,
not a reverse-geocoded or validated postal address. Origin/label live only in page
memory; private school notes and the comparison list live in browser localStorage.
Map tiles necessarily disclose viewed map tiles to OpenStreetMap. Local spatial
queries do not send the selected coordinate to a geocoding service.

### Screenshot feature mapping

| Menu | Implemented data / limits |
|---|---|
| Details | GIAS headteacher, address, contact, trust/sponsor, ages, phase, religion, school website |
| Pupils | GIAS pupil/capacity and boys/girls; DfE school census total, FSM, language and school-stage categories. Sources have different dates. Capacity is not available admission places. No fabricated SEN, absence or class-size statistics. |
| Inspections | Official Ofsted snapshot and available inspection categories, including early years/sixth form; original URN retained. Not a complete inspection history. |
| Strengths / weaknesses | Explicit rule-based grouping of published category judgements, not an AI report summary, independent rating or Locrating content. |
| Results | DfE KS2/KS4/KS5 available years, year selector, suppressed values retained. |
| School / LA / England | Same-year KS2 subject/indicator comparisons against state-funded schools. No proprietary percentile rankings. |
| Parent reviews | Official Parent View entry point only; no copied happiness percentage. |
| School reviews | Private browser notes only; no third-party reviews. |
| Admissions | Official school-level National Offer Day applications/offers, preference breakdown, outside-LA counts, trend; phase selector. No admission probability or inferred oversubscription rate. |
| Catchment | Official admissions entry points and explanation; no invented polygons/last-offer distances. |
| Destinations | Official KS4 sustained education/employment categories. No primary feeder-school name list. |
| Workforce | Official school-level 2025 headcount/FTE, ratios, salary, vacancies and teacher absence where published. |
| Financials | Official Financial Benchmarking and Insights Tool link; account figures not imported and trust accounts are not attributed to an individual academy. |

### Additional public sources (no API keys)

All DfE datasets below: Crown copyright / Open Government Licence v3.0,
subject to the release's additional notices. API responses are version-pinned,
cached seven days and fetched only when the corresponding menu opens. Source
failure is unavailable, not zero. Incomplete paginated results are rejected.

| Data | EES dataset ID |
|---|---|
| School pupil census | 019e7403-4523-7749-b530-159f451dd83c |
| KS2 LA/England | 019afee5-4791-7467-a788-c163fd9b57de |
| KS4 destinations | 019d4f41-22d1-71b2-a1a7-f3b91026815b |

API documentation: https://api.education.gov.uk/statistics/docs/

Local snapshots are joined by exact URN; predecessor schools are not silently
merged. The supplied workspace contains 247,714 admissions records and 21,915
workforce records. A fresh starter archive excludes these large data files.
To reproduce them, download the following official files to `data/`:

- [Applications and offers 2026/27 release](https://explore-education-statistics.service.gov.uk/find-statistics/primary-and-secondary-school-applications-and-offers/2026-27/explore): [school-level CSV, about 67 MB](https://content.explore-education-statistics.service.gov.uk/api/releases/0bf4f9cf-721d-44e3-8473-266c87e17e00/files/42d0d4e4-9604-413a-8275-00b829ffbdcb), save as `offers2026.csv`. Available historical years 2014/15–2026/27 vary by URN.
- [School workforce 2025 release](https://explore-education-statistics.service.gov.uk/find-statistics/school-workforce-in-england/2025/explore): [school-level XLSX, about 8 MB](https://content.explore-education-statistics.service.gov.uk/api/releases/32476c77-5ff3-4efb-ad1e-a2173e74a4d4/files/29994f28-f11f-49ef-8560-76f845b8a0ba), save as `workforce2025.xlsx`. Census November 2025; teacher sickness covers 2024/25.

```sh
.venv/bin/python scripts/import_school_context.py --offers data/offers2026.csv --workforce data/workforce2025.xlsx
```

Fresh GIAS imports include the extended details. To enrich an existing school index
from the same GIAS snapshot without rebuilding coordinates:

```sh
.venv/bin/python scripts/import_school_context.py --gias data/gias.zip
```

The on-use updater now discovers these releases automatically; see FRESHNESS.md. For manual imports, importer
source URLs and vintage labels must be updated together for a new release.
Missing imports show no data plus the official source links. Detailed school data
here cover England; UK postcode search does not imply UK-wide DfE coverage.
