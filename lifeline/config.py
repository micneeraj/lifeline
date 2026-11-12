"""All tunable constants in one place. Locked before the eval was run (see eval/RESULTS.md)."""
import json, os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "lifeline.db"
TRACE_DIR = ROOT / "trace"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

# NTEE codes counted as relief work (prefix of 3 chars):
RELIEF_NTEE = {
    "M20": "Disaster Preparedness & Relief Services",
    "M23": "Search & Rescue Squads",
    "M24": "Fire Prevention / Volunteer fire",
    "M99": "Public Safety, Disaster Preparedness & Relief N.E.C.",
    "P60": "Emergency Assistance",
    "P20": "Human Service Organizations",
    "L41": "Homeless Shelters",
    "K30": "Food Programs",
    "K31": "Food Banks & Pantries",
    "K34": "Congregate Meals",
}

# ---------------------------------------------------------------- event manifest
# Everything event-specific (name, FEMA declaration, state, declared counties, date window, data files)
# is loaded from a manifest. See docs/ADD_AN_EVENT.md. Helene in western North Carolina is the only
# real event loaded today.
DEFAULT_EVENT = ROOT / "data" / "events" / "helene-nc-2024" / "event.json"
# Keys of the manifest that go into every verdict hash. Kept identical to the pre-manifest config so
# published verdict hashes still re-derive.
HASHED_EVENT_KEYS = ("name", "fema_decl", "begin", "end", "obs_begin", "obs_end")
REQUIRED_EVENT_KEYS = HASHED_EVENT_KEYS + ("id", "short_name", "state", "state_name", "region", "declared_counties",
                                           "bbox", "map", "default_redirect_point", "flood_product", "db",
                                           "flood_extent_file")
EVENT_GEN = 0  # bumped on every use_event() so per-thread DB connections and caches know to reload


def event_path(m, key_or_path):
    """Resolve a manifest path: relative to the repo root, or to the manifest folder if it says so."""
    p = m[key_or_path] if key_or_path in m else key_or_path
    base = m["_dir"] if m.get("paths_relative_to") == "manifest" else ROOT
    return (Path(base) / p).resolve()


def load_manifest(path):
    path = Path(path).resolve()
    m = json.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED_EVENT_KEYS if k not in m]
    if missing:
        raise ValueError(f"event manifest {path} is missing {missing}")
    m["_dir"] = str(path.parent)
    return m


def use_event(path):
    """Switch the whole pipeline to the event described by this manifest."""
    global EVENT_MANIFEST, EVENT, DB_PATH, FLOOD_GEOJSON, EVENT_BBOX, DECLARED_COUNTIES, EVENT_GEN
    m = load_manifest(path)
    EVENT_MANIFEST = m
    EVENT = {k: m[k] for k in HASHED_EVENT_KEYS}
    DB_PATH = event_path(m, "db")
    FLOOD_GEOJSON = event_path(m, "flood_extent_file")
    EVENT_BBOX = tuple(m["bbox"])
    DECLARED_COUNTIES = {c.lower() for c in m["declared_counties"]}
    EVENT_GEN += 1
    return m


def public_event():
    """The manifest fields the web UI may show (never file paths)."""
    m = EVENT_MANIFEST
    keys = ("id", "name", "short_name", "fema_decl", "state", "state_name", "region", "period_label", "begin", "end",
            "obs_begin", "obs_end", "declared_counties", "map", "flood_product", "flood_product_label", "sources")
    return {k: m.get(k) for k in keys}


use_event(os.getenv("LIFELINE_EVENT") or DEFAULT_EVENT)

# Partner allow/block lists by EIN (data/partners.json), applied after eligibility screening.
PARTNERS_PATH = ROOT / "data" / "partners.json"

# Flood geometry rules
PLACE_RADIUS_MAX_KM = 5.0      # a place is "flooded" if observed flood lies within its radius
PLACE_RADIUS_MIN_KM = 1.0
EDGE_FRACTION = 0.8            # flood only in outer 20% of the radius -> EDGE_OF_FLOOD
CHARITY_RADIUS_KM = 40.0
MAX_PAYEES = 3
LOOKALIKE_MIN, LOOKALIKE_EXACT = 85, 99

# Flood evidence label: DISPLAY ONLY, never read by the Judge. Distances are fractions of the place's own
# check radius (equivalent-circle radius of its Census land area, clamped 1-5 km). A distance past
# EDGE_FRACTION (0.8) of the radius is already EDGE_OF_FLOOD -> UNVERIFIABLE, so "Weak" marks VERIFIED
# results that are getting close to that edge, or that rest on a small flooded area.
EVIDENCE_BANDS = {
    "strong_max_dist_frac": 0.25,   # Strong: flood water within 25% of the radius ...
    "strong_min_km2": 0.5,          # ... and at least 0.5 km2 flooded inside the radius
    "weak_min_dist_frac": 0.6,      # Weak: nearest flood beyond 60% of the radius (edge starts at 80%) ...
    "weak_max_km2": 0.1,            # ... or under 0.1 km2 flooded inside the radius
}

# LLM — pinned model names
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "").lower()
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODELS = {
    "gemini": "gemini-3.5-flash-lite",
    "anthropic": "claude-sonnet-5-5",
    "openai": "gpt-4.1-mini",
    "nvidia": "meta/llama-3.3-70b-instruct",
}
LLM_TIMEOUT_S = 15
SAMPLE_MODE = os.getenv("LIFELINE_SAMPLE", "") == "1"

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE = "https://api-m.sandbox.paypal.com"
PAYPAL_RECEIVER_EMAIL = os.getenv("PAYPAL_RECEIVER_EMAIL", "")
