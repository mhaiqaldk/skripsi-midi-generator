import csv
import io
from datetime import datetime

import streamlit as st

from state import HISTORY_LIMIT, load_settings
from ui import chips, tempo_label

st.title("Generation History")
st.caption(
    f"Your last {HISTORY_LIMIT} generations from this browser session. "
    "Nothing is stored on the server: closing or refreshing the tab clears it."
)

history = st.session_state.get("history", [])

if not history:
    st.info(
        "No generations yet. Files you create on the Generate page show up "
        "here so you can download them again or reload their settings.",
        icon=":material/history:",
    )
    st.page_link("views/generate.py", label="Go to the generator",
                 icon=":material/music_note:")
    st.stop()


def history_csv(entries):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "created", "preset", "bpm", "bpm_end", "complexity", "progression", "bars",
        "duration_s", "session_minutes", "count_in", "ending", "events",
        "seed", "voice_leading", "filename",
    ])
    for r in entries:
        writer.writerow([
            r["created"], r["preset"], r["bpm"], r.get("bpm_end", r["bpm"]),
            r["complexity"], r["progression"], r["bars"],
            round(r["duration"], 2), r.get("session_minutes") or "",
            r.get("count_in", False), r.get("ending", False),
            r["event_count"], r["seed"],
            "smooth" if r["smooth_voicing"] else "root", r["filename"],
        ])
    return buffer.getvalue()


col1, col2 = st.columns(2)
col1.download_button(
    "Export history (CSV)",
    data=history_csv(history),
    file_name="rgmbi_history.csv",
    mime="text/csv",
    icon=":material/table_view:",
    width="stretch",
)
if col2.button("Clear history", icon=":material/delete:", width="stretch"):
    st.session_state.history = []
    st.rerun()

for i, result in enumerate(history):
    with st.container(border=True):
        created = datetime.fromisoformat(result["created"]).strftime("%H:%M:%S")
        st.markdown(f"**{result['progression']}**  ·  {created}")
        minutes, seconds = divmod(round(result["duration"]), 60)
        chips([
            ("Preset", result["preset"]),
            ("Tempo", tempo_label(result)),
            ("Complexity", result["complexity"]),
            ("Length", f"{minutes}:{seconds:02d}"),
            ("Seed", result["seed"]),
        ])
        b1, b2 = st.columns(2)
        if b1.button(
            "Open in generator",
            key=f"open_{i}",
            icon=":material/open_in_new:",
            width="stretch",
            help="Loads these settings (including the seed) and shows the result.",
        ):
            load_settings(result)
            st.switch_page("views/generate.py")
        b2.download_button(
            "Download MIDI",
            data=result["midi_bytes"],
            file_name=result["filename"],
            mime="audio/midi",
            key=f"dl_{i}",
            icon=":material/download:",
            width="stretch",
        )
