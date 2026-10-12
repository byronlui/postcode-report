# On-use freshness and historical flooding

## What “latest” means

On every page load or postcode search, the browser calls `POST /api/updates/check`.
It starts a single background source-check/import job (overlapping requests share
that job) and invalidates API responses from the previous use. All report sections
are fetched for the requested postcode; school detail APIs fetch their individual
URN on demand. During one use, source-specific TTLs still prevent repeated requests.
A live API response means freshly retrieved published data, not that a census,
inspection, crime month or coverage model describes today's conditions.

The expandable status panel shows each downloaded source's version, last check and
result. A successful changed import automatically reloads report sections. You can
also use “載入已更新資料”. An unsuccessful discovery/download/import retains the
previous valid database and is explicitly **not** marked current. API fallback
responses show `stale` with their original retrieval timestamp.

## Automated download sources

- GIAS: official daily public CSV, conditional HTTP and SHA-256 comparison.
  Uses the same daily URL pattern documented by DfE's gias-query-tool.
  If today's file is not yet published (404), checks the preceding two dates and
  preserves the actual file date. Validates the CSV before replacing the download.
  The previous generated File.xhtml export endpoint was resetting connections.
- NaPTAN: official CSV endpoint, conditional HTTP requests and content hash.
- OS Open Greenspace: official product/download catalogue version and checksum;
  download/convert/import only on change.
- Ofsted: official latest-inspections publication page, dated CSV discovery,
  conditional download and hash. Handles full and abbreviated month names.
- DfE admissions/workforce: publication redirects and official release metadata;
  discover latest release and supporting school file IDs. New compatible releases
  are downloaded and indexed; schema changes fail visibly rather than mis-map data.
- Ofcom: Connected Nations publication index (excluding planned deployments),
  latest actual-coverage report, fixed/mobile ZIP links; compatible postcode and
  LA CSV imports. Model methodology or schema changes may require adapter updates.

No API keys are needed for these public downloads. Data licensing remains as
recorded in `imports` and `docs/SOURCES.md`; automatic downloading does not expand
reuse rights. First-time setup may download hundreds of MB. Files use conditional
ETag/Last-Modified requests where supported; APIs/version manifests are preferred
where available. Download size cap: 600 MB per file. Snapshot imports are SQLite
transactions. Files, hashes and update state live in `data/`, outside the static
web root; no credentials are included in status or source archives.

Local council tax and other manually imported sources without an implemented
updater remain **manual**. EPC still needs the user's official login token. Finance,
Parent View, catchment and other official-link-only sections are not automatically
imported. No blanket “all data is current” claim is made. A successfully contacted
source can itself have an old publication. Run one Uvicorn worker for this personal
app; the filesystem lock prevents two importers writing simultaneously.

## Historic flooding

The Environment section now defaults to **EA Recorded Flood Outlines**, not active
warnings. Public OGC Features endpoint:

https://environment.data.gov.uk/spatialdata/recorded-flood-outlines/ogc/features/v1/collections/Recorded_Flood_Outlines/items

Metadata and OGL attribution:
https://www.data.gov.uk/dataset/16e32c53-35a6-4d54-a111-ca09031eaaaf/recorded-flood-outlines

The spatial response is filtered using British National Grid distance to the flood
polygon and event start/end dates. Choose last 1/3/5/10 years or all dates, and
0.1–20 km around the postcode centre. Events overlapping the chosen interval are
included; undated records are separately counted and excluded from bounded-year
counts. Leap-day cutoffs are handled. Maximum 5,000 fetched polygon records;
truncation is labelled. The display simplifies polygon geometry only for rendering;
spatial inclusion uses the original geometry.

Counts are **polygon records**, not distinct floods, warning issuances, affected
properties or proof of internal flooding. Several outlines may belong to one flood.
The map/table distinguish whether an outline covers the postcode centre. They do
not determine an individual property's risk. Quarterly publication and verification
lags mean no recent record is not proof of no flooding. The newest recorded event
end date in the local response is shown separately from retrieval time.

EA historic warning archive catalogue:
https://environment.data.gov.uk/dataset/88bed270-d465-11e4-8669-f0def148f590

On 22 September 2026 it described coverage through 30 June 2026, but the public
page showed **No data services or resources available**. No warning-history counts
are invented or inferred from current warnings/water levels. The catalogue and
current warning service remain separate links. This limitation does not prevent
querying the accessible Recorded Flood Outlines service.

## Validation (22 September 2026)

42 tests passed: revalidation on a new use; cached request coalescing; conditional
304 download; transactional failed-import preservation; flood interval overlap,
unknown dates, distance exclusion, leap years; invalid radius/year and cross-origin
update rejection; Ofsted month parsing; prior school/crime/provider regression tests.

Live RG10 9RZ, 5 km: the official spatial API returned 414 bounding-box candidates,
381 polygons after exact distance filtering across all years, zero in the last year.
The latest local event end date in that response was 28 February 2014. This is a
limitation of the returned recorded dataset, not a statement that no later flood
occurred. Browser verified 381 records and blue polygons, period controls, dates,
source notes and automatic update status. NaPTAN updated to 356,647 records.

Follow-up on 22 September: GIAS fixed using the official daily CSV; 26,536
open establishments with coordinates imported, vintage 2026-09-22. Also excluded
Ofsted HTML preview links from CSV discovery and explicitly requested text/csv. See DEMOGRAPHICS.md for population
and ethnicity verification. Local council-tax imports remain manual.

23 September: GIAS now retries native socket-reset errors as well as httpx transport
errors, at most three attempts. Filesystem/schema failures are not retried as network
failures. The latest successful daily import is 2026-09-23. EPC session requests
bypass disk cache entirely. Police selectable months come from crimes-street-dates;
annual population history uses latestMINUS5-latest; no synthetic ethnicity updates.
