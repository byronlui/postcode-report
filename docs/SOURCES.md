# Sources, access, licensing and fallback

Reviewed 2026-09-19; Ofcom/EPC access updated 2026-09-20. Source metadata is also exposed through `/api/catalog` and each report panel. Government origin does not automatically mean every field is unrestricted.

## Postcodes.io / ONS / Ordnance Survey

- Documentation: https://postcodes.io/docs/
- Coverage: UK
- Access: No key
- Licence: Mixed underlying ONS/OS licences; see Postcodes.io licences
- Fallback: Self-host Postcodes.io with ONSPD; local postcode snapshot

## Police.uk

- Documentation: https://data.police.uk/docs/
- Coverage: England, Wales, Northern Ireland; Scotland BTP only
- Access: No key
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: Police.uk monthly CSV downloads

## Environment Agency

- Documentation: https://environment.data.gov.uk/flood-monitoring/doc/reference
- Coverage: England
- Access: No key
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: EA flood warning API cache; long-term risk checker

## MHCLG Planning Data

- Documentation: https://www.planning.data.gov.uk/docs
- Coverage: England; participating datasets only
- Access: No key
- Licence: Dataset-specific licence, commonly OGL; consult source record
- Fallback: Dataset CSV/GeoJSON and local council register

## HM Land Registry

- Documentation: https://www.gov.uk/government/statistical-data-sets/price-paid-data-downloads
- Coverage: England and Wales
- Access: No key
- Licence: OGL v3.0; contains HM Land Registry data © Crown copyright and database right
- Fallback: Monthly/yearly Price Paid CSV importer

## ONS / Nomis Census 2021

- Documentation: https://www.nomisweb.co.uk/api/v01/help
- Coverage: England and Wales; 2021 geography
- Access: No key within public quotas
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: Nomis topic summary CSV exports

## DfE Get Information about Schools

- Documentation: https://www.get-information-schools.service.gov.uk/Downloads
- Coverage: England
- Access: Public CSV, no key
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: Daily establishment CSV importer; named-school postcode approximation

## DfT NaPTAN

- Documentation: https://naptan.api.dft.gov.uk/swagger/index.html
- Coverage: Great Britain
- Access: No key
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: NaPTAN CSV importer, national or selected ATCO areas

## Transport for London

- Documentation: https://api.tfl.gov.uk/
- Coverage: TfL journey planner service area
- Access: Optional TFL_APP_KEY / service quotas
- Licence: TfL transport data terms
- Fallback: Official TfL and National Rail journey planners

## Food Standards Agency

- Documentation: https://api.ratings.food.gov.uk/help
- Coverage: UK participating food hygiene schemes
- Access: No key; API version header
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: FSA downloadable authority data; optional OpenStreetMap

## Ordnance Survey OS Open Greenspace

- Documentation: https://www.ordnancesurvey.co.uk/products/os-open-greenspace
- Coverage: Great Britain
- Access: No key for OS OpenData downloads
- Licence: OGL v3.0; contains OS data © Crown copyright and database right 2026
- Fallback: OS Downloads API GeoPackage; normalized entrance-point CSV

## OpenStreetMap contributors

- Documentation: https://www.openstreetmap.org/copyright
- Coverage: UK; community completeness varies
- Access: No key; opt-in ENABLE_OSM
- Licence: ODbL 1.0; © OpenStreetMap contributors
- Fallback: Local licensed OSM extract; not a government dataset

## MHCLG Energy Performance Data

- Documentation: https://get-energy-performance-data.communities.gov.uk/api-technical-documentation
- Coverage: England and Wales
- Access: GOV.UK One Login → website session input (memory only, no .env token)
- Licence: Non-address fields OGL v3.0; address/postcode fields have OS/Royal Mail restrictions
- Fallback: Authorised CSV export importer; official certificate register

## Ofcom Connected Nations

- Documentation: https://api.ofcom.org.uk/
- Coverage: UK
- Access: no key for January 2026 public downloads; optional live subscriptions require keys
- Licence: January 2026 fixed/mobile public downloads explicitly OGL v3.0; API subscription terms separate
- Import: scripts/import_ofcom.py --download. Fixed postcode r2 snapshot and mobile local-authority snapshot; official checker for per-address/operator predictions.

## Defra strategic noise mapping round 4

- Documentation: https://www.gov.uk/government/publications/strategic-noise-mapping-2022
- Coverage: England; modelled road/rail noise
- Access: No key for published datasets
- Licence: Check linked dataset licence; OGL where specified
- Fallback: Import WGS84 GeoJSON contours; model year must be supplied

## Defra UK-AIR

- Documentation: https://uk-air.defra.gov.uk/data/
- Coverage: Dataset-specific UK coverage
- Access: Public downloads; service terms vary
- Licence: Check dataset licence / Crown copyright attribution
- Fallback: Import published air-quality point CSV with pollutant, unit, year

## Valuation Office / local council

- Documentation: https://www.gov.uk/council-tax-bands
- Coverage: England/Wales; Scotland SAA; NI domestic rates
- Access: Official lookup; no unrestricted address-level API assumed
- Licence: Council publication / VOA terms; no automated address scraping
- Fallback: Import council band charges by council + parish + financial year

## ONS Census / official deprivation releases

- Documentation: https://www.gov.uk/government/collections/english-indices-of-deprivation
- Coverage: Nation-specific; not directly comparable
- Access: No key for open releases
- Licence: Open Government Licence v3.0 (check dataset-specific exceptions)
- Fallback: Import current nation-specific IMD/household-income table with geography and vintage

## Required attribution and limits

- OGL data: contains public sector information licensed under the Open Government Licence v3.0. [Licence](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
- EA: this uses Environment Agency flood and river level data from the real-time data API (Beta).
- HMLR: contains HM Land Registry data © Crown copyright and database right 2026. See the official PPD reuse conditions and exclusions.
- ONS/Nomis: source ONS, Census 2021, supplied through Nomis; Crown copyright. Census disclosure-control perturbation means some totals differ.
- OS Open Greenspace: contains OS data © Crown copyright and database right 2026. Government open dataset under OGL. Distances use access points, not polygon centroids.
- Defra noise: © Department for Environment, Food & Rural Affairs copyright and/or database right 2023. OGL. Round 4 models 2021; Lden and Lnight are separate metrics.
- Postcodes.io is a third-party open service over official geographic datasets, not a government-operated API. Retain [underlying licences](https://postcodes.io/docs/licences/), including ONS and OS acknowledgements. Use the Scottish/NI restrictions described there when redistributing bulk postcode data.
- OSM map / optional Overpass: © OpenStreetMap contributors, ODbL 1.0. The embedded map loads directly from OSM; it is not government data. Do not remove attribution. No bulk tile downloading.
- EPC: [non-address fields OGL; address/postcode restrictions](https://get-energy-performance-data.communities.gov.uk/guidance/licensing-restrictions). This app displays energy-only fields. Public redistribution of address data requires the publisher's exact notice and an allowed purpose; no such address export is implemented.
- Ofcom public January 2026 downloads: OGL v3.0, confirmed in the linked “About this data” documents on the Spring 2026 release page. Contains Ofcom data; retain snapshot date and geography. No per-postcode full-fibre percentage is published. Mobile download is local-authority scale. Live API subscriptions remain separate and untested with real credentials.
- Planning Data: licence and completeness depend on individual datasets; retain source entity links. Absence of intersection does not establish absence of a legal constraint.
- Schools/admissions websites: linked for the current admissions documents; their text and PDFs are not copied into the app. No guarantee of catchment, eligibility or allocation.
- Council tax: band, parish, financial year, discount and exemption all matter; the sample is a cited published table. NI domestic rates are treated separately.

## Current endpoint details

- Location: `GET https://api.postcodes.io/postcodes/{postcode}`.
- Crime: discover latest `crimes-street-dates`, then `crimes-street/all-crime` with lat/lng/date.
- Flood alerts: EA `id/floods` with lat/long/dist=5/min-severity=3. No property-level long-term risk probability is computed.
- Census: discover Nomis TS001 / TS007A / TS054 / TS061 metadata, then query the dataset using the explicit `lsoa21` code. Counts include publisher totals/subtotals; no naive summing.
- HMLR: public SPARQL query for exact normalized full postcode, ordered transactionDate, capped at 501 to detect display truncation at 500.
- NaPTAN: public national CSV; daily download or ATCO-area CSV selection, indexed locally.
- GIAS: normal public Downloads form for establishment fields; no login. If the form changes, manual official CSV import remains supported.
- OS Greenspace: discover product/version and download URL via `https://api.os.uk/downloads/v1/products/OpenGreenspace`, import the national GeoPackage.
- Noise: public WMS GetFeatureInfo, version 1.1.1 / EPSG:27700, 101×101 query centered on postcode; one layer per response to prevent metric-order ambiguity. Road endpoint `spatialdata/road-noise-all-metrics-england-round-4/wms`; rail endpoint `spatialdata/noise-data/wms`; layer `Road_Noise_Lden_England_Round_4_All` and corresponding Road/Rail Lnight/Lden names.
- Planning: repeated dataset filters and point intersection; a separate polygon window for planning applications. Beta / partial national coverage.
- FSA: Establishments, API version 2 header, maxDistanceLimit=2 miles, pageSize=100. Counts are capped samples, not exhaustive amenities coverage.
- UK-AIR: SOS station inventory with `near` filter, not fabricated pollution values. A failing station inventory remains unavailable with an official latest-readings link.
- EPC: `https://api.get-energy-performance-data.communities.gov.uk/api/domestic/search`, bearer auth, page size 5000, pagination flag retained. Old portal intentionally not used.
- Ofcom broadband: public documented gateway requires subscription key. Mobile URL is configurable from the new authorised service, raw-response display; no untested assumed common schema.

Full UK geography lookup is supported where Postcodes.io provides coordinates. England has the broadest integrated coverage; England/Wales, GB, Scotland and Northern Ireland have different datasets. Country-specific coverage gaps are explicit. This starter does not promise equal complete data coverage for every UK postcode.

## No-key network release

Source: https://www.ofcom.org.uk/phones-and-broadband/coverage-and-speeds/connected-nations-update-spring-2026

Downloaded corrected fixed ZIP (`202601_fixed_broadband_coverage_and_full_fibre_take-up-r1.zip`, containing postcode r2 files) and `202601_mobile_coverage_r1.zip`. The official methodology describes both downloads as OGL. Import stores 1,741,096 all-premises postcode rows and 362 mobile CSV area rows. Blank percentages remain missing; mobile at-least-one coverage is computed only where the zero-operator percentage is supplied. No operator-specific postcode inference.


Additional sources (23 September 2026):
- Nomis QS201EW / NM_522_1: 2011 ethnicity. OGL, no key; only rural_urban=0 and total/broad ethnic groups. Compare with TS021 only when the LSOA code matches, with census-method and boundary caveats.
- OSRM public route service: https://project-osrm.org/docs/v26.4.0/http ; road-network travel time, no live traffic. OSRM BSD-2-Clause; OSM data ODbL. No key, demo availability not guaranteed; Google Maps URL fallback.
- Google Maps URLs: https://developers.google.com/maps/documentation/urls/get-started ; external planner links, no API key. No Google route data scraped or republished.
- EPC schema samples: https://github.com/communitiesuk/epb-data-warehouse/tree/main/spec/fixtures/json_samples . Code information: https://get-energy-performance-data.communities.gov.uk/api-technical-documentation/codes-info . Token and all authenticated responses remain in memory; no shared disk cache.

## Geology and radon (2026-10-10)

GeoSure: https://www.bgs.ac.uk/datasets/bgs-geosure-5-km-hex-grid/
Official OGL GeoPackage download is revalidated on each geology query using conditional HTTP headers when offered. Validated replacement is atomic; failures retain the last valid copy visibly marked stale. Data stored in data/geosure.gpkg with HTTP metadata in geosure-meta.json. No API key. Six national overview layers, hexagon side 5 km and area about 65 km². **Not suitable for local or site-specific analysis.** Preserve localised significant-rating advisories even where the overall class is Low. Detailed GeoSure reports are separately licensed.

Radon: https://www.bgs.ac.uk/technologies/web-map-services-wms/radon-data-wms/
Official public BGS map service layer 0, spatial query by postcode centre, no API key. OGL; Contains British Geological Survey materials © UKRI 2026. Great Britain only. CLASS_MAX is the maximum potential category within a 1 km square, not a specific property's probability or measured concentration. Service version is displayed. Uses existing daily response cache and session source revalidation; old fallback is marked stale. UKradon address reports/measurements are separate.

Live validation RG10 9RZ: six GeoSure v8 rows, ShrinkSwell Significant with localised advisory; Radon tile SU7775, CLASS_MAX 3 (3–<5%), Indicative Atlas GB v3. This is coarse context, not a property risk assessment. Tests: 75 passed.
