"""Isolated staging entrypoint. Public V5 app.py is never changed."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import streamlit as st
from v653.ui import render

st.set_page_config(page_title='STHO staging', layout='centered')
st.caption('STAGING · Research only · No broker orders')
render(st, {})
