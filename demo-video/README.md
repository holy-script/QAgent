# QAgent demo video (Remotion)

Re-render after any UI change: re-record footage, regenerate the track index, render.

```
# 1. footage (4K, element tracking, tours off). Needs QAGENT_EMAIL, QAGENT_PASSWORD, ECO_PASSWORD in the environment.
PYTHONPATH=scripts python3 scripts/cap_eco2.py        # ForecastIQ (EcoForecast)
PYTHONPATH=scripts python3 scripts/cap_qa_setup.py    # add an app, settings
PYTHONPATH=scripts python3 scripts/cap_qa_plan.py     # plan from the PRD
PYTHONPATH=scripts python3 scripts/cap_qa_quick.py    # notes to a one-journey plan (also starts a FULL run: about $1.50)
PYTHONPATH=scripts python3 scripts/cap_qa_quickrun.py # runs the one-journey plan
PYTHONPATH=scripts python3 scripts/cap_qa_results2.py # a finished run: problems and proof
PYTHONPATH=scripts python3 scripts/cap_qa_bugs.py     # bugs, requirements, Repeat exactly
cp footage/*.mp4 public/footage/ && python3 scripts/gen_tracks_index.py

# 2. voice (free, local; Orpheus 3B via mlx-audio, voice "tara"): edit scripts/script3.json, then
python scripts/tts_orpheus.py tara && python scripts/polish_audio.py tara     # in .venv-cb

# 3. video
npx remotion studio            # preview
npx remotion render Demo out/qagent-demo.mp4
```
Scenes and shot timings live in `src/scenes.ts` (keyed to the per-line voice timings). Callout boxes follow the real on-screen elements through `public/tracks/*.json`.
