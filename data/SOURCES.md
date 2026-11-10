# Data sources

All downloaded **10–11 Nov 2026** (IST). `scripts/download_data.sh` fetches them again and `python scripts/build_data.py` rebuilds the store.
The raw files (about 340 MB) are not committed. What is committed: `data/lifeline.db` (the precomputed SQLite store, about 9.5 MB), `data/flood_wnc.geojson` (the simplified flood extent for the map) and `data/fema_dr4827_nc.json`.

| Dataset | URL | Rows used |
|---|---|---|
| **Satellite flood extent**: ICEYE Flood Solution FSD-2227, Hurricane Helene (ICEYE SAR + Sentinel-1/2 + open-source imagery + river gauges), observation window 2024-09-24 to 2024-10-05 | https://services5.arcgis.com/LsNj2OtQESAjac8r/arcgis/rest/services/ICEYE_FSD_2227_flood_extent_Helene_Juvare/FeatureServer/0 (ArcGIS item 178a04cc78744061b4f1c8c067f062d2) | 59 flood areas in the WNC bbox → 58 after clipping to `WNC_BBOX` |
| FEMA OpenFEMA DisasterDeclarationsSummaries, DR-4827-NC | https://www.fema.gov/api/open/v2/DisasterDeclarationsSummaries?$filter=disasterNumber%20eq%204827 | 40 designated areas (39 counties + Eastern Band of Cherokee Indians) |
| IRS Exempt Organizations Business Master File, NC | https://www.irs.gov/pub/irs-soi/eo_nc.csv | 59,803 orgs → 3,645 with relief NTEE codes |
| IRS Publication 78 data | https://apps.irs.gov/pub/epostcard/data-download-pub78.zip | 1,428,501 EINs |
| IRS automatic revocation list | https://apps.irs.gov/pub/epostcard/data-download-revocation.zip | 1,063,880 still revoked (no reinstatement date) |
| OFAC SDN list | https://www.treasury.gov/ofac/downloads/sdn.csv | 19,563 names |
| US Census 2023 Gazetteer, places | https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2023_Gazetteer/2023_Gaz_place_national.zip | 32,329 places (for detecting same-name towns) |
| US Census 2023 Gazetteer, ZCTAs | …/2023_Gaz_zcta_national.zip | 33,791 ZIP centroids (to locate charities) |
| US Census 2023 Gazetteer, counties | …/2023_Gaz_counties_national.zip | 3,222 (approximate county fallback) |
| US Census Geocoder (coordinates → county), cached in `geocache` | https://geocoding.geo.census.gov/geocoder/geographies/coordinates | 26 cached lookups |

**Where the flood polygon came from.** Copernicus EMS Rapid Mapping had no Helene activation: its public activations list for Sept 2024 shows only European, Asian and African events. The ICEYE product is a public, satellite-derived **observed** flood extent for this event, so the FEMA-counties fallback was not needed.

Eligible relief charities after all filters (in Pub 78, not auto-revoked, not an OFAC SDN name match): **3,503**.
