"""Shared UI pieces: style, piano roll, audio preview, result card."""

import io
import wave

import altair as alt
import numpy as np
import pandas as pd
import pretty_midi
import streamlit as st

from config import BAR_BEATS
from explain_engine import explain, harmony_rows
from harmonic_engine import midi_to_name
from pattern_engine import HIHAT, KICK, SIDE_STICK, SNARE

SOUNDFONT_PATH = "soundfont.sf2"
SAMPLE_RATE = 44100

TRACK_COLORS = {
    "Harmony": "#4a9b8e",
    "Bass": "#c9824f",
    "Drums": "#1e2d3a",
}
DRUM_NAMES = {KICK: "Kick", SNARE: "Snare", HIHAT: "Hi-hat", SIDE_STICK: "Count-in"}

PREVIEW_BARS = 16        # piano roll shows at most this many bars
PREVIEW_SECONDS = 60     # audio preview length for long sessions
FULL_WAV_RATE = 22050    # full-length WAV export sample rate (keeps files small)

COMPLEXITY_LABELS = {
    1: "1 · Simple — bass on beat 1, no hi-hat",
    2: "2 · Moderate — bass on 1 & 3, 8th-note hi-hat",
    3: "3 · Complex — bass every beat, 16th-note hi-hat",
}

CSS = """
<style>
h1, h2, h3 { color: #1e2d3a; font-weight: 600; }

.stButton > button, .stDownloadButton > button {
    border-radius: 6px;
    font-weight: 500;
}
.stButton > button[kind="primary"] {
    background-color: #4a9b8e;
    border: none;
}
.stButton > button[kind="primary"]:hover { background-color: #3d8478; }

[data-testid="stExpander"] {
    border-radius: 8px;
    border: 1px solid #d4cfbc;
}

[data-testid="stMarkdownContainer"] code {
    background-color: #e8e2d0;
    color: #1e2d3a;
    padding: 0.1rem 0.35rem;
    border-radius: 4px;
}

.chips { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.25rem 0 0.75rem; }
.chip {
    background: #e8e2d0;
    color: #1e2d3a;
    border-radius: 999px;
    padding: 0.15rem 0.7rem;
    font-size: 0.85rem;
    white-space: nowrap;
}
.chip b { font-weight: 600; }
</style>
"""


def apply_style():
    st.markdown(CSS, unsafe_allow_html=True)


def chips(items):
    html = "".join(
        f'<span class="chip">{label} <b>{value}</b></span>'
        for label, value in items
    )
    st.markdown(f'<div class="chips">{html}</div>', unsafe_allow_html=True)


# --- Piano roll ------------------------------------------------------------

def _notes_frame(midi, max_bars):
    """One row per note, positioned in bars via the file's tempo map
    (so tempo ramps line up with the bar grid)."""
    def to_bars(seconds):
        return midi.time_to_tick(seconds) / midi.resolution / BAR_BEATS

    rows = []
    for instrument in midi.instruments:
        track = instrument.name or ("Drums" if instrument.is_drum else "Track")
        for note in instrument.notes:
            start = to_bars(note.start)
            if start >= max_bars:
                continue
            if instrument.is_drum:
                label = DRUM_NAMES.get(note.pitch, f"Drum {note.pitch}")
            elif track == "Bass":
                label = f"Bass {midi_to_name(note.pitch)}"
            else:
                label = midi_to_name(note.pitch)
            rows.append({
                "Track": track,
                "Lane": label,
                "pitch": note.pitch,
                "Start": start + 1,
                "End": min(to_bars(note.end), max_bars) + 1,
                "Position": (
                    f"bar {int(start) + 1}, "
                    f"beat {(start % 1) * BAR_BEATS + 1:.2f}"
                ),
                "Velocity": note.velocity,
            })
    return pd.DataFrame(rows)


def piano_roll(midi, total_bars=None):
    df = _notes_frame(midi, PREVIEW_BARS)
    if df.empty:
        st.info("No notes to show.")
        return
    if total_bars and total_bars > PREVIEW_BARS:
        st.caption(
            f"Piano roll shows the first {PREVIEW_BARS} of {total_bars} bars."
        )

    order = {"Harmony": 0, "Bass": 1, "Drums": 2}
    lanes = (
        df.assign(o=df["Track"].map(order))
        .sort_values(["o", "pitch"], ascending=[True, False])["Lane"]
        .drop_duplicates()
        .tolist()
    )
    bars = int(np.ceil(df["End"].max() - 1))

    chart = (
        alt.Chart(df)
        .mark_bar(cornerRadius=2, height={"band": 0.75})
        .encode(
            x=alt.X(
                "Start:Q", title="Bar",
                scale=alt.Scale(domain=[1, bars + 1], nice=False),
                axis=alt.Axis(tickMinStep=1, format="d", grid=True),
            ),
            x2="End:Q",
            y=alt.Y("Lane:N", sort=lanes, title=None),
            color=alt.Color(
                "Track:N",
                scale=alt.Scale(
                    domain=list(TRACK_COLORS), range=list(TRACK_COLORS.values())
                ),
                legend=alt.Legend(orient="top", title=None),
            ),
            opacity=alt.Opacity(
                "Velocity:Q", scale=alt.Scale(domain=[30, 127], range=[0.45, 1]),
                legend=None,
            ),
            tooltip=["Track", "Lane", "Position", "Velocity"],
        )
        .properties(height=alt.Step(20))
        .configure_view(strokeWidth=0)
        .configure(background="transparent")
    )
    st.altair_chart(chart, width="stretch")


# --- Audio -----------------------------------------------------------------

def _clip_midi(midi, max_seconds):
    """Copy of the MIDI with only the notes that start before max_seconds."""
    clipped = pretty_midi.PrettyMIDI()
    for inst in midi.instruments:
        new = pretty_midi.Instrument(inst.program, is_drum=inst.is_drum, name=inst.name)
        new.notes = [
            pretty_midi.Note(n.velocity, n.pitch, n.start, min(n.end, max_seconds))
            for n in inst.notes if n.start < max_seconds
        ]
        clipped.instruments.append(new)
    return clipped


@st.cache_data(show_spinner=False, max_entries=16)
def synth_wav(midi_bytes, max_seconds=None, sample_rate=SAMPLE_RATE):
    """Render MIDI bytes to 16-bit mono WAV bytes via FluidSynth."""
    midi = pretty_midi.PrettyMIDI(io.BytesIO(midi_bytes))
    if max_seconds:
        midi = _clip_midi(midi, max_seconds)
    audio = midi.fluidsynth(sf2_path=SOUNDFONT_PATH, fs=sample_rate)
    peak = np.max(np.abs(audio)) if audio.size else 0
    if peak > 0:
        audio = audio / peak * 0.9
    pcm = (audio * 32767).astype(np.int16)

    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(pcm.tobytes())
    return buffer.getvalue()


def try_synth(midi_bytes, message="Synthesizing audio…", **kwargs):
    """Return WAV bytes, or ``None`` with a warning if synthesis fails."""
    try:
        with st.spinner(message):
            return synth_wav(midi_bytes, **kwargs)
    except FileNotFoundError:
        st.warning("Audio preview unavailable: soundfont.sf2 not found.")
    except (ImportError, ModuleNotFoundError):
        st.warning("Audio preview unavailable: pyfluidsynth not installed.")
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Audio preview unavailable: {exc}")
    return None


def fmt_duration(seconds):
    minutes, secs = divmod(round(seconds), 60)
    return f"{minutes}:{secs:02d}"


def tempo_label(result):
    end = result.get("bpm_end", result["bpm"])
    if end == result["bpm"]:
        return f"{result['bpm']} BPM"
    return f"{result['bpm']} → {end} BPM"


# --- Result card -------------------------------------------------------------

def explain_panel(result):
    with st.expander("Why it sounds like this", icon=":material/lightbulb:"):
        st.caption(
            "Every note comes from an explicit rule. Here are the rules that "
            "shaped this file, with its actual values."
        )
        for title, lines in explain(result):
            st.markdown(f"**{title}**")
            st.markdown("\n\n".join(lines))
            if title == "Harmony":
                rows = harmony_rows(result)
                if rows:
                    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def result_card(result, key="result", on_lock_seed=None):
    long_session = result["duration"] > PREVIEW_SECONDS + 1

    with st.container(border=True):
        st.markdown(f"#### {result['progression']}")
        length = f"{result['bars']} bars · {fmt_duration(result['duration'])}"
        chips([
            ("Preset", result["preset"]),
            ("Tempo", tempo_label(result)),
            ("Complexity", result["complexity"]),
            ("Length", length),
            ("Seed", result["seed"]),
        ])

        piano_roll(result["midi"], result["bars"])

        if long_session:
            wav = try_synth(result["midi_bytes"], max_seconds=PREVIEW_SECONDS)
            if wav:
                st.caption(f"Audio preview: first {fmt_duration(PREVIEW_SECONDS)}")
        else:
            wav = try_synth(result["midi_bytes"])
        if wav:
            st.audio(wav, format="audio/wav")

        col1, col2 = st.columns(2)
        col1.download_button(
            "Download MIDI",
            data=result["midi_bytes"],
            file_name=result["filename"],
            mime="audio/midi",
            icon=":material/download:",
            width="stretch",
            key=f"{key}_mid",
        )
        wav_name = result["filename"].replace(".mid", ".wav")
        if wav and not long_session:
            col2.download_button(
                "Download WAV", data=wav, file_name=wav_name, mime="audio/wav",
                icon=":material/graphic_eq:", width="stretch", key=f"{key}_wav",
            )
        elif wav:
            ready_key = f"{key}_full_wav_for"
            if st.session_state.get(ready_key) == result["filename"]:
                full = try_synth(
                    result["midi_bytes"], sample_rate=FULL_WAV_RATE,
                    message=f"Rendering {fmt_duration(result['duration'])} of audio…",
                )
                if full:
                    col2.download_button(
                        "Download full WAV", data=full, file_name=wav_name,
                        mime="audio/wav", icon=":material/graphic_eq:",
                        width="stretch", key=f"{key}_wav",
                    )
            elif col2.button(
                f"Render full WAV ({fmt_duration(result['duration'])})",
                icon=":material/graphic_eq:", width="stretch", key=f"{key}_render",
                help="Long sessions are rendered on request, at 22 kHz to keep the file small.",
            ):
                st.session_state[ready_key] = result["filename"]
                st.rerun()

        voicing = "smooth voice leading" if result["smooth_voicing"] else "root position"
        st.caption(
            f"{result['event_count']} note events · {voicing}. "
            f"Same settings + seed {result['seed']} always produce this exact file."
        )
        explain_panel(result)
        if on_lock_seed is not None:
            st.button(
                f"Keep seed {result['seed']} for next runs",
                on_click=on_lock_seed,
                args=(result["seed"],),
                icon=":material/lock:",
                key=f"{key}_lock",
            )
