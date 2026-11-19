import streamlit as st

from config import (
    APP_NAME, APP_TAGLINE, MAX_BPM, MIN_BPM, PRESET_CONFIG, SESSION_LENGTHS,
)
from harmonic_engine import parse_progression
from main import SEED_MAX, new_seed, progression_label, run_generator
from state import add_to_history, init_defaults
from ui import COMPLEXITY_LABELS, fmt_duration, result_card

st.title(APP_NAME)
st.caption(APP_TAGLINE)
st.write(
    "Pick a therapeutic preset, enter a chord progression, and get a "
    "multi-track MIDI accompaniment (harmony, bass, drums) built from "
    "explicit, explainable musical rules — no machine learning."
)

with st.expander("How to use this generator"):
    st.markdown("""
1. **Choose a preset.** *Relaxation* for slow, calming stimuli, *Motor
   Synchronization* for steady rhythmic entrainment, or *Cognitive
   Stimulation* for higher-tempo engagement. It fills in tempo and
   complexity, which you can still change.
2. **Enter chords** separated by spaces, e.g. `C G Am F` or `Bb F Gm Eb`.
   Supported types: major, `m`, `7`, `maj7`, `m7`, `dim`, `aug`, `sus2`,
   `sus4`, `6`, `add9`, and more. Add `:N` to hold a chord for N bars,
   e.g. `C:2 G:2 Am F`.
3. **Set the session.** Play the progression once or loop it for 1–10
   minutes. Optionally ramp the tempo (e.g. 90 → 110 BPM for gait
   training, or 80 → 60 to wind down), add a one-bar count-in, and end on
   the first chord.
4. **Generate.** You get an interactive piano roll, an audio preview, and
   MIDI/WAV downloads for any DAW or media player.
5. **Reproduce a result** by keeping its seed (*Advanced* settings). The
   same settings and seed always give the identical file.
""")

# --- state ------------------------------------------------------------------

init_defaults()


def apply_preset():
    preset = PRESET_CONFIG[st.session_state.preset]
    st.session_state.tempo = preset["bpm"]
    st.session_state.tempo_end = preset["bpm"]
    st.session_state.complexity = preset["complexity"]


def start_ramp():
    if st.session_state.ramp:
        st.session_state.tempo_end = st.session_state.tempo


def lock_seed(seed):
    st.session_state.random_seed = False
    st.session_state.seed = seed


# --- controls -----------------------------------------------------------------

st.selectbox(
    "Therapeutic preset",
    list(PRESET_CONFIG),
    key="preset",
    on_change=apply_preset,
    format_func=lambda p: f"{p} — {PRESET_CONFIG[p]['purpose']}",
)

col1, col2 = st.columns([3, 2])
tempo = col1.slider("Tempo (BPM)", MIN_BPM, MAX_BPM, key="tempo")
complexity = col2.selectbox(
    "Rhythmic complexity",
    [1, 2, 3],
    key="complexity",
    format_func=lambda c: COMPLEXITY_LABELS[c].split(" — ")[0],
    help="\n\n".join(COMPLEXITY_LABELS.values()),
)

chord_text = st.text_input(
    "Chord progression",
    key="chords",
    placeholder="C G Am F",
    help="Space-separated chord symbols. Add :N to hold a chord for N bars.",
)
items, errors = parse_progression(chord_text)
for message in errors:
    st.error(message, icon=":material/error:")
if items and not errors:
    bars = sum(b for _, b in items)
    st.caption(f"{len(items)} chords · {bars} bars")

st.markdown("##### Session")
loop_seconds = (
    sum(b for _, b in items) * 4 * 60 / tempo if items and not errors else 0
)
s1, s2 = st.columns([3, 2])
session_minutes = s1.selectbox(
    "Session length",
    SESSION_LENGTHS,
    key="session_minutes",
    format_func=lambda m: (
        f"Play once ({fmt_duration(loop_seconds)})" if m == 0
        else f"{m} minute{'s' if m > 1 else ''} (progression loops)"
    ),
    help="Longer sessions repeat the progression until the length is reached.",
)
s2.toggle(
    "Tempo ramp",
    key="ramp",
    on_change=start_ramp,
    help="Change the tempo gradually, in equal steps per bar, from the "
         "start tempo to the end tempo.",
)
if st.session_state.ramp:
    tempo_end = st.slider(
        f"End tempo (BPM) — starts at {tempo}",
        MIN_BPM, MAX_BPM, key="tempo_end",
    )
else:
    tempo_end = tempo
t1, t2 = st.columns(2)
t1.toggle("Count-in bar", key="count_in",
          help="One bar of four side-stick clicks before the music starts.")
t2.toggle("Ending on the first chord", key="ending",
          help="Adds a final bar that holds the progression's first chord.")

with st.expander("Advanced"):
    st.toggle(
        "Smooth voice leading",
        key="smooth",
        help="On: each chord uses the inversion closest to the previous one, "
             "so the harmony moves smoothly. Off: every chord in root "
             "position (original thesis behaviour).",
    )
    st.toggle("New random seed each time", key="random_seed")
    st.number_input(
        "Seed",
        min_value=1,
        max_value=SEED_MAX,
        key="seed",
        disabled=st.session_state.random_seed,
        help="Controls the small velocity variations. Same seed + same "
             "settings = identical MIDI file.",
    )

if st.button(
    "Generate MIDI",
    type="primary",
    icon=":material/play_arrow:",
    disabled=bool(errors),
):
    seed = new_seed() if st.session_state.random_seed else int(st.session_state.seed)
    st.session_state.result = run_generator(
        items,
        bpm=tempo,
        complexity_level=complexity,
        preset_name=st.session_state.preset,
        seed=seed,
        smooth_voicing=st.session_state.smooth,
        bpm_end=tempo_end,
        session_minutes=session_minutes,
        count_in=st.session_state.count_in,
        ending=st.session_state.ending,
    )
    add_to_history(st.session_state.result)

# --- result -----------------------------------------------------------------

if "result" in st.session_state:
    result = st.session_state.result
    changed = (
        result["progression"] != progression_label(items)
        or result["bpm"] != tempo
        or result["complexity"] != complexity
        or result["smooth_voicing"] != st.session_state.smooth
        or result.get("bpm_end", result["bpm"]) != tempo_end
        or (result.get("session_minutes") or 0) != session_minutes
        or result.get("count_in", False) != st.session_state.count_in
        or result.get("ending", False) != st.session_state.ending
    )
    if changed:
        st.info(
            "Settings changed since this result. Click **Generate MIDI** "
            "to update it.",
            icon=":material/refresh:",
        )
    result_card(
        result,
        on_lock_seed=lock_seed if st.session_state.random_seed else None,
    )
