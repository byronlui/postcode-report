# Normalized dataset schemas

`python scripts/import_data.py KIND PATH --source OFFICIAL_URL --vintage PERIOD --license LICENSE`

UTF-8 CSV with headers. Metadata fields travel with the dataset, not with an invented default year. You must have the rights to use the source. Data outside the loaded file's scope is unavailable, not zero.

## Native formats

- `transport`: unmodified NaPTAN CSV, active records; fields ATCOCode, CommonName, Latitude, Longitude, StopType, Indicator, LocalityName, ModificationDateTime, Status.
- `schools`: GIAS establishment fields CSV or a ZIP containing exactly one CSV. Open establishments with Easting/Northing; EPSG:27700 → WGS84 with pyproj. Includes educational establishments beyond mainstream schools. Does not use school postcode coordinates when a national index coordinate is available.
- `prices`: native 16-column HMLR PPD CSV, no header. ID upsert supports A/C/D. Full snapshot/years first, then monthly deltas. Not a bedroom dataset.
- `noise`: RFC 7946 WGS84 GeoJSON FeatureCollection. Polygon/MultiPolygon properties should include source, model_year, metric, db_min/db_max. Imported polygons take precedence over live Defra WMS. Convert official EPSG:27700 data to EPSG:4326 before import. No numeric inference from missing polygons.
- OS Open Greenspace: `scripts/import_greenspace.py file.gpkg --vintage YYYY-MM`. Reads current official GeoPackage access_point + greenspace_site. Expected CRS is EPSG:27700; arbitrary ZIP paths are never extracted by bootstrap.

## Normalized CSV headers

These are *adapter formats*, not a claim that official publishers use identical column names. Map an authorized export to these fields before importing. No artificial example observations are included.

| Kind | Required / useful headers | Lookup |
|---|---|---|
| greenspace | id,name,lat,lon,type,access_type,site_id | nearby WGS84; sites deduplicated by nearest access point |
| air | id,name,lat,lon,pollutant,value,unit,year,period | 20 km nearby; supply correct averaging period |
| epc | id,postcode,certificate,uprn,band,date,potential_band | full postcode; latest date per UPRN |
| broadband | id,postcode,field,value,unit,year | full postcode; preserve Ofcom metric labels and definitions |
| tax | id,area,parish,band,annual_gbp,financial_year | council GSS code + exact parish; postcode never determines band |
| affluence | id,area,indicator,value,unit,year,nation,geography_version | 2021 LSOA code; align vintages explicitly |

`area` for tax means council GSS code (e.g. E06000041); for affluence it means LSOA21. Do not join IMD 2019 LSOA11 data to changed LSOA21 boundaries without an official lookup. National deprivation ranks are not UK-wide comparable. The app intentionally does not present Postcodes.io's unversioned IMD field as a current affluence score.

EPC importer discards address columns. It stores the postcode as an internal lookup key, plus certificate/UPRN/energy fields. Do not repurpose restricted EPC addresses into a general property/address directory. The live API cache may still contain original responses; keep it local and protected.

Except PPD, an import replaces the entire selected kind in a transaction. Merge multiple files first if you need combined coverage. An invalid or empty input rolls back; it does not remove the existing dataset. For monthly PPD deletions, transaction deletion instructions are applied by ID; the import log describes the most recent input, not historical coverage.

The supplied `datasets/charvil-tax-2026.csv` is a real 8-band table transcribed from the [Wokingham 2026/27 official total-charge table](https://www.wokingham.gov.uk/sites/wokingham/files/2026-03/Council%20Tax%20by%20Band%20and%20Parish%20Charges%202026%20to%202027.pdf). It is scoped only to Charvil; the app does not show those amounts for other parishes. They are undiscounted annual charges, not a statement of the selected property's band.

## Direct official imports (2026-09-20)

`python scripts/import_ofcom.py --download` downloads and imports fixed postcode + mobile council-level January 2026 open releases without a key. Offline: `--fixed data/ofcom-fixed-202601.zip --mobile data/ofcom-mobile-202601.zip`. This importer preserves empty percentages as missing and atomically replaces each dataset.

EPC now accepts official domestic CSV headers: CERTIFICATE_NUMBER, POSTCODE, CURRENT_ENERGY_RATING, POTENTIAL_ENERGY_RATING, LODGEMENT_DATE, UPRN. Legacy LMK_KEY / hyphenated headings and normalized fields are accepted. Address columns are discarded. Official downloads still require GOV.UK One Login.
