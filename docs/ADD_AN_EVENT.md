# Adding another disaster

Lifeline's rules contain no event. Everything event-specific is loaded from an **event manifest**, one JSON
file per disaster. Helene in western North Carolina is the only real event loaded today:
[`data/events/helene-nc-2024/event.json`](../data/events/helene-nc-2024/event.json).

A second event needs four things: a FEMA declaration, an observed flood extent, the IRS register slice for its
state, and a manifest that points at them.

## 1. Collect the data

| What | Where to get it | Format the builder reads |
|---|---|---|
| FEMA declaration | OpenFEMA `DisasterDeclarationsSummaries`, filtered by `disasterNumber` | JSON with a `DisasterDeclarationsSummaries` list (as downloaded) |
| Observed flood extent | A satellite flood product for the event (ICEYE, Copernicus EMS / GFM, NASA, UNOSAT…) | GeoJSON polygons. Each feature needs `aoi_id`, `flooded_cities`, `data_inputs`, `start_time`, `end_time`, `flooded_area_sq_mi` (rename the product's own fields if needed) |
| IRS register slice | IRS EO BMF for the state, `https://www.irs.gov/pub/irs-soi/eo_<state>.csv` | CSV as published |
| Eligibility lists | IRS Pub 78, IRS auto-revocation list, OFAC SDN (national, reused across events) | as published |
| Places, counties, ZIPs | US Census Gazetteer (national, reused across events) | as published |

`scripts/download_data.sh` and [data/SOURCES.md](../data/SOURCES.md) show the exact URLs used for Helene.
Keep raw downloads in `data/raw/` (not committed).

## 2. Write the manifest

Create `data/events/<event-id>/event.json`. Every key below is required unless marked optional.

```json
{
 "id": "my-flood-2026",
 "name": "My River Flood (DR-9999-XX)",
 "short_name": "My River Flood",
 "fema_decl": "DR-9999-XX",
 "state": "XX",
 "state_name": "Full State Name",
 "region": "the river valley",
 "period_label": "May 2026",
 "begin": "2026-05-01",
 "end": "2026-05-20",
 "obs_begin": "2026-05-01",
 "obs_end": "2026-05-05",
 "declared_counties": ["County A", "County B"],
 "bbox": [-90.0, 40.0, -88.0, 41.5],
 "map": {"center": [-89.0, 40.7], "zoom": 8.4},
 "default_redirect_point": [40.7, -89.0],
 "flood_product": "Name of the satellite flood product",
 "flood_product_label": "Short label shown under the map",
 "db": "data/events/my-flood-2026/lifeline.db",
 "flood_extent_file": "data/events/my-flood-2026/flood.geojson",
 "fema_file": "data/raw/fema_my_flood.json",
 "irs_slice_file": "data/raw/eo_xx.csv",
 "charity_county_file": "data/events/my-flood-2026/charity_counties.json",
 "build": {
  "places": "data/raw/2023_Gaz_place_national.txt",
  "counties": "data/raw/2023_Gaz_counties_national.txt",
  "zcta": "data/raw/2023_Gaz_zcta_national.txt",
  "flood_raw": "data/raw/my_flood_extent.geojson",
  "fema_raw": "data/raw/fema_my_flood.json",
  "pub78": "data/raw/data-download-pub78.txt",
  "revocation": "data/raw/data-download-revocation.txt",
  "sdn": "data/raw/sdn.csv"
 },
 "sources": [{"what": "Satellite flood extent", "name": "…", "url": "…"}]
}
```

What each field drives:

- `name`, `fema_decl`, `begin`, `end`, `obs_begin`, `obs_end` go into every verdict hash (`verdict_sha256`).
- `state` is used by the FEMA declaration check (a place outside this state is `NO_DISASTER_DECLARATION`), by the
  same-name-town tie-break, and to look up charity counties.
- `begin` / `end` set the date window (`DATE_MISMATCH` outside it). `begin` also rules out charities whose IRS
  exemption ruling came after the event started.
- `declared_counties` is the FEMA list. It drives "Serves: [county] County (declared)" and the county-first
  ordering of charity cards. Copy it from the FEMA file's `designatedArea` values without " (County)".
- `bbox` clips the flood extent when the store is built. `map` sets the map view in the UI.
- `default_redirect_point` (lat, lon) is where Lifeline looks for a screened charity to suggest when a place
  can't be located.
- `flood_product` is stored with every flood check. `flood_product_label`, `short_name`, `region` and
  `period_label` are the text the UI shows. The page has no event text of its own.
- `db` and `flood_extent_file` are the build outputs the app reads at request time.
- `paths_relative_to` (optional): set it to `"manifest"` to resolve every path relative to the manifest's folder
  instead of the repo root. The test fixture does this.
- `charity_county_file` (optional): `{zip: county}` from `scripts/charity_counties.py`. Without it, a charity's
  county falls back to the nearest county centroid (approximate).

## 3. Build the store

```bash
python scripts/build_data.py data/events/my-flood-2026/event.json
python scripts/charity_counties.py data/events/my-flood-2026/event.json   # optional, uses the Census geocoder
```

`build_data.py` reads every input path from the manifest and writes the SQLite store (`db`) and the display
flood GeoJSON (`flood_extent_file`). Building the Helene manifest reproduces the committed `data/lifeline.db`
table for table.

## 4. Run it

```bash
LIFELINE_EVENT=data/events/my-flood-2026/event.json python run.py
```

Without `LIFELINE_EVENT`, the app loads Helene. A new event also needs its own labelled test appeals and a
locked answer key before anyone quotes accuracy for it: the 38 of 40 result is for Helene only.

## 5. Test it

`tests/test_events.py` shows the whole flow on a tiny synthetic event in `tests/fixtures/test-event` (one small
square flood polygon, a made-up town, two fake charities). It copies the fixture to a temp folder, builds it
with `build_data.py`, switches the pipeline with `agents.use_event(...)`, runs appeals through every step and
the payment stub, then switches back and checks that a Helene verdict hash is unchanged. The fixture is
test-only and is never loaded or shown by the app.

Before you ship a new event:

- [ ] `python -m pytest` passes
- [ ] `python verify.py` still passes for Helene
- [ ] a handful of known flooded and not-flooded places give the expected verdicts
- [ ] the README says which real events are loaded
