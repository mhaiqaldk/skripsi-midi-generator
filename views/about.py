import pandas as pd
import streamlit as st

from config import APP_NAME, PRESET_CONFIG

st.title(f"About {APP_NAME}")

st.write(f"""
{APP_NAME} is a rule-based therapeutic MIDI generation system that creates symbolic accompaniment
patterns for music-based intervention research.

It focuses on controllable generation through explicit musical rules for
harmonic structure, rhythmic complexity, and tempo-based dynamics.
""")

st.subheader("Rule-based generation")
st.write("""
Instead of a machine-learning model, every note comes from a rule you can
inspect:

- **Harmony:** chord symbols map to fixed interval sets. With smooth voice
  leading on, each chord takes the inversion that moves the fewest
  semitones from the previous chord.
- **Rhythm:** complexity sets how often the bass plays and how dense the
  hi-hat is. Kick and snare follow a fixed backbeat with small, fixed
  timing offsets for groove.
- **Dynamics:** tempo picks a base loudness band, and each instrument
  gets a fixed offset from it plus a small, seeded random variation.

Because the only randomness is seeded, the same settings and seed always
reproduce the same file, which supports explainability, reproducibility
and controllability.
""")

st.subheader("Therapeutic preset mapping")
st.table(pd.DataFrame(
    [
        {
            "Preset": name,
            "Purpose": p["purpose"],
            "Tempo range": p["range"],
            "Default tempo": f"{p['bpm']} BPM",
            "Complexity": p["complexity"],
        }
        for name, p in PRESET_CONFIG.items()
    ]
).set_index("Preset"))

st.subheader("Credits")
st.markdown("""
- **Author:** Muhammad Haiqal Dwikusuma
- **Supervisor:** Dr. Lukman Heryawan
- **Institution:** International Undergraduate Program in Computer Science,
  Universitas Gadjah Mada
""")
