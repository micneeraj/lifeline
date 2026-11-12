import os

# Every test runs offline: recorded LLM responses / deterministic extractor, stubbed PayPal.
# Set before any test module imports lifeline.config, whatever order pytest collects them in.
os.environ["LIFELINE_SAMPLE"] = "1"
os.environ.pop("LIFELINE_EVENT", None)
