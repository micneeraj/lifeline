"""All tunable constants in one place. Locked before the eval was run (see eval/RESULTS.md)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_PATH = ROOT / "data" / "lifeline.db"
TRACE_DIR = ROOT / "trace"

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except Exception:
    pass

# Western North Carolina clip box (lon_min, lat_min, lon_max, lat_max)
WNC_BBOX = (-84.33, 34.98, -80.80, 36.59)

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

EVENT = {
    "name": "Hurricane / Tropical Storm Helene (DR-4827-NC)",
    "fema_decl": "DR-4827-NC",
    # Window = FEMA incident begin .. incident end.
    "begin": "2024-09-25",
    "end": "2024-12-18",
    # Satellite observation window (ICEYE product start/end)
    "obs_begin": "2024-09-24",
    "obs_end": "2024-10-05",
}

# Flood geometry rules
PLACE_RADIUS_MAX_KM = 5.0      # a place is "flooded" if observed flood lies within its radius
PLACE_RADIUS_MIN_KM = 1.0
EDGE_FRACTION = 0.8            # flood only in outer 20% of the radius -> EDGE_OF_FLOOD
CHARITY_RADIUS_KM = 40.0
MAX_PAYEES = 3
LOOKALIKE_MIN, LOOKALIKE_EXACT = 85, 99

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
