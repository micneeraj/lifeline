"""Build data/lifeline.db from the raw downloads in data/raw (see data/SOURCES.md).

Run once:  python scripts/build_data.py [path/to/event.json]
Every input and output path comes from the event manifest (default: data/events/helene-nc-2024/event.json,
see docs/ADD_AN_EVENT.md). Everything the app needs at request time is in the manifest's SQLite file
("db") and display flood GeoJSON ("flood_extent_file").
"""
import csv, json, math, re, sqlite3, sys
from pathlib import Path
from shapely.geometry import shape, mapping, box
from shapely import wkb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from lifeline import config  # noqa: E402
from lifeline.config import RELIEF_NTEE  # noqa: E402

csv.field_size_limit(10**8)


def norm_place(name):
    return re.sub(r"\s+(city|town|village|CDP|municipality|borough)$", "", name.strip(), flags=re.I)


def main(manifest=None):
    m = config.load_manifest(manifest or config.DEFAULT_EVENT)
    src = lambda k: config.event_path(m, m["build"][k])
    DB = config.event_path(m, "db")
    if DB.exists():
        DB.unlink()
    con = sqlite3.connect(DB)
    c = con.cursor()
    counts = {}

    # ---- places (Census Gazetteer, national, for ambiguity) ----
    c.execute("create table places(name text, name_l text, state text, lat real, lon real, aland real, geoid text)")
    rows = []
    with open(src("places"), encoding="latin-1") as f:
        r = csv.reader(f, delimiter="\t"); next(r)
        for x in r:
            x = [v.strip() for v in x]
            n = norm_place(x[3])
            rows.append((n, n.lower(), x[0], float(x[10]), float(x[11]), float(x[6]), x[1]))
    c.executemany("insert into places values(?,?,?,?,?,?,?)", rows)
    c.execute("create index ix_pl on places(name_l)")
    counts["places"] = len(rows)

    # ---- counties gazetteer (fallback county lookup) ----
    c.execute("create table counties(name text, state text, geoid text, lat real, lon real)")
    rows = []
    with open(src("counties"), encoding="latin-1") as f:
        r = csv.reader(f, delimiter="\t"); next(r)
        for x in r:
            x = [v.strip() for v in x]
            rows.append((x[3], x[0], x[1], float(x[8]), float(x[9])))
    c.executemany("insert into counties values(?,?,?,?,?)", rows)
    counts["counties"] = len(rows)

    # ---- ZIP centroids ----
    zips = {}
    with open(src("zcta"), encoding="latin-1") as f:
        r = csv.reader(f, delimiter="\t"); next(r)
        for x in r:
            x = [v.strip() for v in x]
            zips[x[0]] = (float(x[5]), float(x[6]))
    counts["zcta"] = len(zips)

    # ---- FEMA declaration (manifest fema_decl) ----
    fema = json.load(open(src("fema_raw"), encoding="utf-8"))["DisasterDeclarationsSummaries"]
    c.execute("create table fema(area text, county text, fips text, decl text, begin text, end_ text, title text, hash text)")
    for d in fema:
        county = d["designatedArea"].replace(" (County)", "")
        c.execute("insert into fema values(?,?,?,?,?,?,?,?)", (d["designatedArea"], county,
                  d["fipsStateCode"] + d["fipsCountyCode"], d["femaDeclarationString"],
                  d["incidentBeginDate"][:10], d["incidentEndDate"][:10], d["declarationTitle"], d["hash"]))
    counts["fema_areas"] = len(fema)

    # ---- flood extent (ICEYE / Sentinel observed) ----
    fc = json.load(open(src("flood_raw"), encoding="utf-8"))
    clip = box(*m["bbox"])
    c.execute("create table flood(aoi_id text, city text, sources text, start_ms int, end_ms int, sq_mi real, geom blob)")
    out = []
    for feat in fc["features"]:
        g = shape(feat["geometry"]).buffer(0).intersection(clip)
        if g.is_empty:
            continue
        p = feat["properties"]
        gs = g.simplify(0.00005, preserve_topology=True)
        c.execute("insert into flood values(?,?,?,?,?,?,?)", (str(p["aoi_id"]), p["flooded_cities"], p["data_inputs"],
                  p["start_time"], p["end_time"], p["flooded_area_sq_mi"], wkb.dumps(gs)))
        out.append({"type": "Feature", "properties": {"aoi_id": p["aoi_id"], "city": p["flooded_cities"],
                    "sources": p["data_inputs"]},
                    "geometry": mapping(g.simplify(0.0004, preserve_topology=True))})
    json.dump({"type": "FeatureCollection", "features": out}, open(config.event_path(m, "flood_extent_file"), "w"),
              separators=(",", ":"))
    counts["flood_aois"] = len(out)

    # ---- IRS eligibility sets ----
    pub78 = set()
    with open(src("pub78"), encoding="utf-8", errors="replace") as f:
        for line in f:
            e = line.split("|", 1)[0].strip()
            if e.isdigit():
                pub78.add(e.zfill(9))
    counts["pub78"] = len(pub78)
    revoked = {}
    with open(src("revocation"), encoding="utf-8", errors="replace") as f:
        for line in f:
            x = line.rstrip("\n").split("|")
            if len(x) >= 12 and x[0].strip().isdigit():
                if not x[11].strip():  # no reinstatement date -> still revoked
                    revoked[x[0].strip().zfill(9)] = x[9].strip()
    counts["revoked_active"] = len(revoked)

    # ---- OFAC SDN names ----
    sdn = []
    with open(src("sdn"), encoding="latin-1") as f:
        for x in csv.reader(f):
            if len(x) > 1 and x[1].strip() and x[1] != "-0-":
                sdn.append(x[1].strip().upper())
    c.execute("create table sdn(name text)")
    c.executemany("insert into sdn values(?)", [(n,) for n in sdn])
    counts["sdn"] = len(sdn)
    sdn_set = set(sdn)

    # ---- IRS EO BMF, the event state's slice ----
    c.execute("""create table charities(ein text primary key, name text, city text, zip text, ntee text, ruling text,
                 revenue int, subsection text, deductibility text, status text, lat real, lon real,
                 in_pub78 int, revoked_date text, ofac_hit int, raw text)""")
    total = kept = 0
    with open(config.event_path(m, "irs_slice_file"), encoding="latin-1") as f:
        r = csv.DictReader(f)
        for x in r:
            total += 1
            ntee = (x["NTEE_CD"] or "").strip().upper()
            if ntee[:3] not in RELIEF_NTEE:
                continue
            z = (x["ZIP"] or "")[:5]
            if z not in zips:
                continue
            ein = x["EIN"].zfill(9)
            lat, lon = zips[z]
            c.execute("insert or replace into charities values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
                ein, x["NAME"].strip(), x["CITY"].strip(), z, ntee, x["RULING"], int(x["REVENUE_AMT"] or 0),
                x["SUBSECTION"], x["DEDUCTIBILITY"], x["STATUS"], lat, lon, int(ein in pub78),
                revoked.get(ein), int(x["NAME"].strip().upper() in sdn_set),
                json.dumps({k: x[k] for k in ("EIN", "NAME", "CITY", "STATE", "ZIP", "SUBSECTION", "RULING",
                                              "DEDUCTIBILITY", "STATUS", "NTEE_CD", "REVENUE_AMT")})))
            kept += 1
    counts["eo_nc_rows"] = total
    counts["relief_charities_nc"] = kept
    c.execute("create table geocache(key text primary key, value text)")
    c.execute("create table meta(k text primary key, v text)")
    c.execute("insert into meta values('counts', ?)", (json.dumps(counts),))
    con.commit()
    print(json.dumps(counts, indent=1))
    print("eligible relief charities:", c.execute(
        "select count(*) from charities where in_pub78=1 and revoked_date is null and ofac_hit=0").fetchone()[0])


if __name__ == "__main__":
    main(*sys.argv[1:])
