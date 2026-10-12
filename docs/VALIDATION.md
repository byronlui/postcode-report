# Validation record — 20 September 2026

## Automated checks

`python -m pytest -q`: **19 passed**, 2 dependency deprecation warnings (Starlette/httpx and AnyIO), no test failures. Tests use isolated temporary databases and mocked upstreams; they are not evidence of authenticated service availability. JavaScript syntax check (`node --check app/static/app.js`) passed.

## Real RG10 9RZ query

Run `python scripts/smoke.py`; full timestamped results in [rg109rz-live-report.json](rg109rz-live-report.json). Responses may use timestamped cache according to each source TTL.

- Postcode located in Charvil, Wokingham, England; LSOA 2021 Wokingham 002A.
- Land Registry: 52 registered transactions, 1998-05-15 to 2025-10-01. All-history sample median £210,500 is not a current valuation.
- Census 2021: 1,631 LSOA residents; age, tenure and qualification tables returned.
- Police.uk: July 2026 published data, 55 records including ASB, grouped into 10 categories, approximately 1 mile query radius.
- Schools: 165 open educational establishments within 10 km, nearest 100 listed. Reading School 3.65 miles and The Piggott School 1.17 miles straight-line from postcode centre, based on DfE establishment coordinates. No catchment determination.
- Transport: NaPTAN nearby indexed stops; Twyford Rail Station nearest rail point at 0.74 miles straight-line. Results capped at 300 displayed stops.
- OS Open Greenspace: nearby official site/access-point index returned, deduplicated sites, 80 displayed cap.
- Defra noise: road Lden 50.8 dB, road Lnight 37.5 dB, rail Lden 42.1 dB; rail Lnight NoData. These are round 4 / 2021 model values, not present measurements.
- EA alerts: request succeeded with no current alerts in the query area at test time. This is not a long-term flood-risk conclusion.
- Planning constraints: one centre-point flood-risk-zone entity; nearby applications query returned zero with incomplete-coverage warning.
- FSA: 100 returned food establishments, query cap; not a complete amenities inventory.
- Charvil 2026/27 Council Tax: 8 annual band charges from official published table.
- EPC and Ofcom: `key_required`; no credentials supplied. EPC transformation tested with mock responses. Authenticated EPC / Ofcom / configurable mobile endpoint have not been live verified.
- UK-AIR: `unavailable`, upstream timeout. No pollution reading invented.

## Other UK locations / journey

`python scripts/check_locations.py` (requires running local server) verified location for SW1A 1AA, CF10 1EP, EH1 1YZ and BT1 5GS, plus invalid postcode HTTP 422. Scottish crime and Northern Ireland HMLR prices correctly reported `coverage_gap`. This is a location/coverage check, not a full every-source audit for every nation.

RG10 9RZ to EC2M 7PY returned a partial journey result: 55.5 km straight-line and official planners, but no TfL itinerary. No commute duration inferred. Output: [coverage-live-check.json](coverage-live-check.json).

## Browser checks

Verified in the in-app browser against localhost:

- Overview renders postcode location, map, school distances, populated metrics and 15 navigation categories.
- Sold prices table renders; exact `detached` selector returns 8 detached transactions and excludes semi-detached. This filters table rows; overview median/trend remain the full postcode sample.
- Tax and noise tables display actual returned data and provenance.
- EPC displays registration requirement without invented values.
- Invalid input displays a clear validation message; reload restores a valid report.
- Responsive narrow-window layout visually inspected; no comprehensive device/browser compatibility audit claimed.

## Remaining boundaries

This is a locally runnable starter, not feature parity with a commercial paid report. Reviews are private local notes. Tax is seeded only for Charvil; other areas need published-charge imports. Income/IMD, energy and coverage bulk fallback importers require user-supplied appropriately licensed data. Scotland / Wales / Northern Ireland sources have differing coverage. National commute routing, authenticated APIs, every bootstrap download on a clean machine, print/export across browsers, and production hosting remain unverified. The national school, transport and greenspace source files were downloaded and imported successfully in this workspace.

## Follow-up: remove unnecessary network API-key requirement

20 September 2026: **22 tests passed**. Added official Ofcom import/rollback/missing-value/scope tests, raw EPC CSV privacy test and owner-only token-file test. Public fixed/mobile ZIPs downloaded and imported successfully. Browser verified populated broadband and mobile tables with explicit postcode/council scopes. Evidence: [ofcom-rg109rz-no-key.json](ofcom-rg109rz-no-key.json).

RG10 9RZ: January 2026 all-premises postcode gigabit-capable availability 100%. This is the published area proportion, not a speed promise. Mobile tables refer to Wokingham; blank source values remain missing. Prior `key_required` Ofcom status in the original smoke snapshot is superseded. EPC is still awaiting the user's mandatory GOV.UK One Login/token; its authenticated live integration remains unverified. No account or credentials were fabricated.

## Follow-up: user-defined search distance

25 tests passed, including radius bounds (NaN/infinite/negative/oversize rejection), local spatial results/empty green space, per-category export radius and FSA miles conversion. Browser tested RG10 9RZ: 1 mile school search yields 3 nearby establishments; 0.5 km green-space search yields 5 sites; 0.5 mile FSA search returns the requested nearby entries. Fixed favourite schools remain separate. Preferences survive reload; in-progress radius drafts survive other panel completions.

## 20 September 2026 school/crime update

32 automated tests passed, including strict all-cohort school filtering, suppression preservation, Ofsted framework/URN preservation, literal national school search, geometry bounds and crime failure handling. Live RG10 9RZ Police July 2026 event totals (including ASB): 1 mile 55, 1.5 miles 111, 2.2 miles 212. Reading School returned KS4 9 and KS5 20 indicator rows; Piggott returned KS2 42, KS4 9, KS5 20. Raw checks are in school-136449-live.json, school-136891-live.json and crime-radius-live.json. Published performance years extend to 2024/25 in these releases.

Browser verification: Reading School profile and versioned DfE results rendered; two-school comparison rendered; crime 2.2-mile query returned 212 and viewport rectangle returned 2,515 events. Fixed a Leaflet zoom-transition teardown error by disabling map animation on these frequently recreated panels.


## 22 September 2026 Python school sidebar update

36 tests passed. New tests cover custom-point spatial queries / invalid coordinates,
exact-URN and phase-preserving offers, total-cohort pupil filtering / suppressed
values, and Ofsted early-years judgements without an invented overall grade.
Live API checks: Sonning 147379 pupils 13 rows, admissions 7 school years,
workforce 54 indicators; KS2 benchmarks England 42 and Wokingham 42 rows.
Waingels 142166 KS4 destinations returned 30 category rows.
Browser checks verified right-click origin placement, an updated straight-line
measurement, school menu rendering, real admissions trend/table and aligned
KS2 comparisons. For Sonning 2024/25 combined reading/writing/maths expected
standard: school 93, England 62, Wokingham 71 percent from the DfE API.
No Locrating data was imported. Parent View, finance and catchment are official
entry points, not integrated datasets; primary destination-school names, SEN,
pupil absence and class sizes remain unconnected and explicitly labelled.


## On-use update / historic flood extension

42 tests passed; live and browser checks documented in [FRESHNESS.md](FRESHNESS.md). All-years RG10 9RZ 5 km returned 381 historical outline records; none in the last year. NaPTAN automatically refreshed to 356,647 records. Source connection failures remain visibly unconfirmed, not current.

## GIAS and demographics follow-up — 22 September 2026

47 tests pass, including direct daily GIAS download/304, invalid-download preservation,
ethnicity denominator/group separation, suppression and geography guards, and Ofsted
preview exclusion; CSV downloads explicitly request text/csv. Live API/browser outcomes: [DEMOGRAPHICS.md](DEMOGRAPHICS.md).
