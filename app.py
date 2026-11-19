"""Streamlit entry point: sets up the page and the sidebar navigation."""

import streamlit as st

from config import APP_NAME
from ui import apply_style

st.set_page_config(page_title=APP_NAME, page_icon="🎵", layout="centered")
apply_style()

page = st.navigation([
    st.Page("views/generate.py", title="Generate", icon=":material/music_note:",
            default=True),
    st.Page("views/batch.py", title="Batch Mode", icon=":material/library_music:",
            url_path="batch"),
    st.Page("views/history.py", title="History", icon=":material/history:",
            url_path="history"),
    st.Page("views/about.py", title="About", icon=":material/info:",
            url_path="about"),
])
page.run()
