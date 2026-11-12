# Demo video build

Source for the Lifeline demo video (https://youtu.be/0U7OnSGAwqM), built with
[HyperFrames](https://hyperframes.heygen.com) 0.9.33 (HTML + GSAP rendered to MP4).

| Path | What it is |
|---|---|
| `assets/v3/lines.json` | Narration text, one line per scene (`s01`–`s18`) |
| `assets/v3/words/*.json` | Word timings for each narration line (drive captions and cue points) |
| `tools/gen3.py` | Generator: builds `index.html`, every scene in `compositions/` and the captions from one timing table |
| `tools/timing3.json` | Scene start times and lengths written by `gen3.py` |
| `tools/record.py`, `tools/record3.py` | Playwright screen recorder for the live app (check, map, donate flow) |
| `assets/rec3/marks.json` | Element positions captured during recording (used to place rings, tags and zooms) |
| `compositions/*.html`, `index.html` | Generated HyperFrames scenes and caption track (committed so the video can be inspected without rebuilding) |

Not committed (see `.gitignore`): the rendered MP4, voice and music audio, screen recordings, footage and frame caches.

## Rebuild

Requires Node 20+, Python 3.11+, ffmpeg and Playwright (`pip install playwright && playwright install chromium`).

1. **Voice.** Generate one WAV per line of `assets/v3/lines.json` with Kokoro voice `af_heart`
   (`npx hyperframes@0.9.33 tts --voice af_heart "<line>" -o assets/v3/s01.wav`, and so on), then
   `npx hyperframes@0.9.33 transcribe` each one into `assets/v3/words/sNN.json` (already committed).
2. **Music.** Put a background track at `assets/bgm/track3.wav`.
3. **Footage.** Put the opening flood footage at `assets/footage/flow.mp4`.
4. **Screen recordings.** Run the app (`python run.py` in the repo root, with a sandbox `.env`), then
   `python tools/record3.py`. It writes `assets/rec3/*.mp4`, page stills and `marks.json`.
   PayPal sandbox buyer credentials are read from `../.env` only inside the PayPal popup step; the popup is
   never recorded and the credentials are never printed.
5. **Generate the scenes:** `python tools/gen3.py`
6. **Check and render** (stop any preview server first):
   ```bash
   npx hyperframes@0.9.33 check
   npx hyperframes@0.9.33 render --workers 1 -o renders/lifeline.mp4
   ```

The published cut also drops the PayPal logo scene (about 21.0–24.0 s of the render) with an ffmpeg
trim/concat at a frame boundary and an equal cut from the silence in the audio, so sound stays in sync.
