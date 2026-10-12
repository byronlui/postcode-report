# Population and ethnicity — verified 22 September 2026

Annual population/age/sex: ONS via Nomis NM_2014_1, 2021-boundary LSOAs,
England and Wales. Requests use date=latest, not a hard-coded year. Latest returned
year is 2024; metadata last updated 7 November 2025. Age groups are discovered
from metadata (18 non-overlapping five-year groups, with 85+ combined).
https://www.nomisweb.co.uk/datasets/pestoa2021

Ethnicity: Census 2021 TS021, Nomis NM_2041_1. Five broad groups and 19 detailed
groups shown separately; percentages use TS021's own total for the same LSOA.
No equivalent newer annual LSOA ethnicity dataset was found. New population
estimates cannot update the ethnic proportions. Census disclosure controls can
cause slightly different totals across tables (TS001 versus TS021).
https://www.ons.gov.uk/datasets/TS021/editions/2021/versions/1

No API key. OGL v3.0, subject to dataset-specific notices. Each new use revalidates
API data through the existing update lifecycle. On upstream failure, existing cache
is labelled stale; absence is not represented as zero. Scotland/NI explicitly
report a coverage gap for these new endpoints. Source/download links remain in UI.

RG10 9RZ: Wokingham 002A, E01016619. Live API and browser verified:
2024 estimated population 1,676 (832 male, 844 female); 18 age bands sum to 1,676.
2021 ethnicity denominator 1,634; five broad groups sum to 1,634; 19 details.
Chinese category 15, 0.92%. These are LSOA statistics, not postcode residents.

GIAS daily URL pattern is documented in DfE's own project:
https://github.com/DFE-Digital/gias-query-tool/blob/main/Makefile
The 20260922 CSV downloaded successfully and imported 26,536 open establishments
with coordinates. Windows-1252 decoding preserves official accented names.


23 September: added date=latestMINUS5-latest annual trend on the same NM_2014_1
2021-boundary geography. RG10 9RZ: 2019 1596; 2020 1612; 2021 1629; 2022 1669;
2023 1706; 2024 1676. Last annual change -30 (-1.76%). Missing adjacent years
are not treated as a one-year change.

2011 QS201EW NM_522_1 uses rural_urban=0, c_ethnicid=0,100,200,300,400,500.
Mapping to TS021: 100→1004 (White), 200→1003 (Mixed), 300→1001 (Asian),
400→1002 (Black), 500→1005 (Other). Each year uses its own census denominator.
Counts and percentage-point changes are distinct. Same LSOA code is required;
changed codes show a boundary-comparability gap. Same codes can still have minor
boundary/method changes; this caveat is displayed. This is a two-census comparison,
not an annual post-2021 ethnic trend.
