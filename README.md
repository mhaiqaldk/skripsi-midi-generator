# RG-MBI Generator — Rule Based Adaptive MIDI Generator

Live app: https://adaptive-midi-generator.streamlit.app

This project is a rule based system that generates therapeutic MIDI music, built around the idea of personalized rhythmic and harmonic stimuli for music based interventions. It started as my undergraduate thesis at Universitas Gadjah Mada, and it grew into a working app rather than staying just a paper.

The core idea is that instead of using a black box machine learning model to generate music, the system relies on explicit rules to control harmony and rhythm. This makes the output predictable and explainable, which matters in a context like music based interventions where the goal is to understand and control exactly what the system produces and why.

## What it does

1. Pick a therapeutic preset: **Relaxation**, **Motor Synchronization**, or **Cognitive Stimulation**. Each preset fills in a tempo and rhythmic complexity that fit the use case. You can still change both.
2. Enter a chord progression, like `C G Am F` or `Bb F Gm Eb`. Sharps and flats both work, as do 7ths and other chord types (`7`, `maj7`, `m7`, `dim`, `aug`, `sus2`, `sus4`, `6`, `add9`, …). Add `:N` to hold a chord for N bars: `C:2 G:2 Am F`.
3. Set the session: play the progression once, or loop it for 1 to 10 minutes. Optionally add a **tempo ramp** (for example 90 → 110 BPM for gait training, or 80 → 60 to wind down), a one-bar **count-in**, and an **ending** bar on the first chord.
4. Click **Generate MIDI** to get a multi track MIDI file with separate harmony, bass and drum parts.

After generating you get an interactive piano roll, an audio preview synthesized with FluidSynth, and MIDI and WAV downloads. The result stays on screen while you tweak settings. For long sessions the piano roll shows the first 16 bars, the preview plays the first minute, and the full-length WAV is rendered on request.

**Why it sounds like this:** every result has a panel that explains, with the file's actual values, which rules produced it: preset, session and tempo ramp, rhythm, the voicing chosen for each chord, loudness bands, and the seed.

**Tempo ramps in any DAW:** the MIDI file stores a tempo for every bar, so a ramped file still lines up with the bar grid.

**History** keeps your last 20 generations for the browser session. You can download them again, reload their exact settings, or export the list as CSV. Nothing is stored on the server.

**Reproducible:** the only randomness (small velocity variations) is seeded. The same settings and seed always produce a byte-identical MIDI file. You can lock a seed under *Advanced*.

**Smooth voice leading:** by default each chord uses the inversion that moves the fewest semitones from the previous chord. Turn it off to get the original thesis behaviour (every chord in root position).

**Batch Mode** generates every tempo × complexity combination for one progression with a shared seed, and downloads them as one ZIP with a `metadata.csv`.

## How it's built

| File | Role |
| --- | --- |
| `harmonic_engine.py` | Parses chord symbols, maps them to intervals, applies voice leading |
| `pattern_engine.py` | Rhythm rules: bass, kick/snare and hi-hat patterns by complexity, count-in and ending bars |
| `midi_engine.py` | Seeded velocity rules, per-bar tempo map, MIDI assembly (in memory) |
| `main.py` | The pipeline (`run_generator`): session length, tempo ramp schedule. `save=True` also writes to `outputs/` and `run_log.csv` for local research runs |
| `explain_engine.py` | Builds the "Why it sounds like this" explanation from the same rule tables |
| `config.py` | App name, presets, session lengths, tempo bands and velocity rules |
| `state.py` | Session state: generator settings that persist across pages, history |
| `app.py` | Streamlit entry point and navigation |
| `views/` | Generate, Batch Mode, History, About pages |
| `ui.py` | Shared style, piano roll, audio preview, result card |
| `tests/` | pytest suite |

## Running it locally

```bash
git clone https://github.com/mhaiqaldk/skripsi-midi-generator.git
cd skripsi-midi-generator
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

Run the tests with:

```bash
pip install -r requirements-dev.txt
pytest
```

The audio preview needs FluidSynth (`brew install fluid-synth` on macOS; `packages.txt` installs it on Streamlit Cloud) and `soundfont.sf2`, which is included. Without them the app still generates MIDI and just skips the preview.

## Background

This was originally developed as my undergraduate thesis, "Design and Development of a Rule Based Adaptive MIDI Generator for Personalized Rhythmic and Harmonic Stimuli in Music Based Interventions", supervised by Dr. Lukman Heryawan at Universitas Gadjah Mada.

The thesis version's rhythm and tempo rules are unchanged. Chord support, voice leading, seeding and the interface have been extended since.
