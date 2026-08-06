from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

st.set_page_config(
    page_title="HULA Marketing Operations",
    page_icon="◯",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.marketing_ops.ui import run_marketing_operations


run_marketing_operations(ROOT)
