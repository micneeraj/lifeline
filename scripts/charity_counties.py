"""Precompute the county of every charity's IRS address ZIP (centroid) with the US Census geocoder.

  python scripts/charity_counties.py [path/to/event.json]

Writes the manifest's "charity_county_file" ({zip: county}). The app reads it offline; a ZIP missing
from the file falls back to the nearest county centroid (labelled approximate).
"""
import json, sqlite3, sys, time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lifeline import config  # noqa: E402


def main(manifest=None):
    m = config.use_event(manifest) if manifest else config.EVENT_MANIFEST
    out = config.event_path(m, "charity_county_file")
    done = json.loads(out.read_text(encoding="utf-8")) if out.exists() else {}
    con = sqlite3.connect(config.DB_PATH)
    zips = con.execute("select zip, avg(lat), avg(lon) from charities group by zip").fetchall()
    for i, (z, lat, lon) in enumerate(zips):
        if z in done:
            continue
        for attempt in range(3):
            try:
                r = httpx.get("https://geocoding.geo.census.gov/geocoder/geographies/coordinates",
                              params={"x": lon, "y": lat, "benchmark": "Public_AR_Current",
                                      "vintage": "Current_Current", "layers": "Counties", "format": "json"},
                              timeout=15)
                c = r.json()["result"]["geographies"]["Counties"]
                done[z] = c[0]["BASENAME"] if c else None
                break
            except Exception as e:  # noqa
                time.sleep(2)
        if i % 50 == 0:
            out.write_text(json.dumps(done, indent=0, sort_keys=True), encoding="utf-8")
            print(i, len(zips), flush=True)
    out.write_text(json.dumps(done, indent=0, sort_keys=True), encoding="utf-8")
    print("wrote", out, len(done))


if __name__ == "__main__":
    main(*sys.argv[1:])
