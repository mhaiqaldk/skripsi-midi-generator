import csv
import io
import zipfile

import pandas as pd
import streamlit as st

from harmonic_engine import parse_progression
from main import SEED_MAX, new_seed, run_generator
from ui import result_card

st.title("Batch Mode")
st.write(
    "Generate every combination of tempo and complexity for one chord "
    "progression, then download them all as a single ZIP with a metadata "
    "CSV. All files share one seed, so differences come only from tempo "
    "and complexity, which suits controlled comparisons."
)

chord_text = st.text_input("Chord progression", "C G Am F", key="batch_chords")
items, errors = parse_progression(chord_text)
for message in errors:
    st.error(message, icon=":material/error:")

bpm_values = st.multiselect(
    "Tempo values (BPM)",
    options=[60, 70, 80, 90, 100, 110, 120, 130, 140],
    default=[60, 80, 100, 120, 140],
)
complexity_levels = st.multiselect(
    "Complexity levels", options=[1, 2, 3], default=[1, 2, 3]
)

col1, col2 = st.columns(2)
seed = col1.number_input(
    "Seed (shared by all files)", 1, SEED_MAX,
    value=st.session_state.get("batch_seed_default", new_seed()),
)
st.session_state.batch_seed_default = seed
smooth = col2.toggle("Smooth voice leading", value=True)

total = len(bpm_values) * len(complexity_levels)
st.caption(f"{total} files will be generated.")

if st.button(
    "Run batch generation",
    type="primary",
    icon=":material/play_arrow:",
    disabled=bool(errors) or total == 0,
):
    progress = st.progress(0.0)
    results = []
    for i, bpm in enumerate(sorted(bpm_values)):
        for complexity in sorted(complexity_levels):
            results.append(run_generator(
                items, bpm=bpm, complexity_level=complexity,
                preset_name="Batch", seed=int(seed), smooth_voicing=smooth,
            ))
            progress.progress(len(results) / total)
    progress.empty()

    meta = io.StringIO()
    writer = csv.writer(meta)
    writer.writerow([
        "filename", "bpm", "complexity", "progression", "bars",
        "duration_s", "events", "seed", "voice_leading",
    ])
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for r in results:
            zf.writestr(r["filename"], r["midi_bytes"])
            writer.writerow([
                r["filename"], r["bpm"], r["complexity"], r["progression"],
                r["bars"], round(r["duration"], 2), r["event_count"],
                r["seed"], "smooth" if r["smooth_voicing"] else "root",
            ])
        zf.writestr("metadata.csv", meta.getvalue())

    st.session_state.batch = {
        "results": results,
        "zip": zip_buffer.getvalue(),
        "zip_name": f"rgmbi_batch_seed{int(seed)}.zip",
    }

batch = st.session_state.get("batch")
if batch:
    results = batch["results"]
    st.success(f"Generated {len(results)} MIDI files.", icon=":material/check:")
    st.download_button(
        "Download all (ZIP + metadata.csv)",
        data=batch["zip"],
        file_name=batch["zip_name"],
        mime="application/zip",
        type="primary",
        icon=":material/folder_zip:",
        width="stretch",
    )
    st.dataframe(
        pd.DataFrame([
            {
                "File": r["filename"],
                "BPM": r["bpm"],
                "Complexity": r["complexity"],
                "Bars": r["bars"],
                "Length (s)": round(r["duration"], 1),
                "Events": r["event_count"],
            }
            for r in results
        ]),
        hide_index=True,
        width="stretch",
    )

    st.subheader("Preview a file")
    labels = [f"{r['bpm']} BPM · complexity {r['complexity']}" for r in results]
    choice = st.selectbox("File", range(len(results)), format_func=labels.__getitem__)
    result_card(results[choice], key="batch_preview")
