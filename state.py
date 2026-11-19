"""Session state shared across pages: generator settings and history."""

import streamlit as st

from config import PRESET_CONFIG

HISTORY_LIMIT = 20

# Generator widget keys and their starting values
DEFAULTS = {
    "preset": "Relaxation",
    "tempo": PRESET_CONFIG["Relaxation"]["bpm"],
    "complexity": PRESET_CONFIG["Relaxation"]["complexity"],
    "chords": "C G Am F",
    "smooth": True,
    "random_seed": True,
    "seed": 1,
    "session_minutes": 0,
    "ramp": False,
    "tempo_end": PRESET_CONFIG["Relaxation"]["bpm"],
    "count_in": False,
    "ending": True,
}


def init_defaults():
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)


def persist_settings():
    """Keep generator settings when the user visits another page.

    Streamlit deletes a widget's value when the widget isn't drawn in a run.
    Re-assigning the key on every run (from app.py, before any page draws)
    detaches it from that clean-up.
    """
    for key in DEFAULTS:
        if key in st.session_state:
            st.session_state[key] = st.session_state[key]


def add_to_history(result):
    history = st.session_state.setdefault("history", [])
    history.insert(0, result)
    del history[HISTORY_LIMIT:]


def load_settings(result):
    """Put a past result's settings back into the generator controls."""
    st.session_state.preset = result["preset"] if result["preset"] in PRESET_CONFIG \
        else st.session_state.get("preset", DEFAULTS["preset"])
    st.session_state.tempo = result["bpm"]
    st.session_state.complexity = result["complexity"]
    st.session_state.chords = result["progression"]
    st.session_state.smooth = result["smooth_voicing"]
    st.session_state.random_seed = False
    st.session_state.seed = result["seed"]
    st.session_state.session_minutes = result.get("session_minutes") or 0
    st.session_state.ramp = result.get("bpm_end", result["bpm"]) != result["bpm"]
    st.session_state.tempo_end = result.get("bpm_end", result["bpm"])
    st.session_state.count_in = result.get("count_in", False)
    st.session_state.ending = result.get("ending", False)
    st.session_state.result = result
