"""Shared data loading, filters and chart styling for the Streamlit dashboard."""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from config import DB_PATH, MIN_BUDGET_FOR_ROI, PALETTE as P  # noqa: E402

BLUE = P["series"][0]
GREY = P["neutral"]

# ---------- Plotly theme: thin marks, hairline grid, one palette ----------
pio.templates["tmdb"] = go.layout.Template(
    layout=dict(
        font=dict(family="system-ui, -apple-system, Segoe UI, sans-serif", color=P["ink2"], size=13),
        title=dict(font=dict(color=P["ink"], size=16), x=0, xanchor="left"),
        colorway=P["series"],
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor=P["grid"], linecolor=P["axis"], zeroline=False, ticks=""),
        yaxis=dict(gridcolor=P["grid"], linecolor=P["axis"], zeroline=False, ticks=""),
        hoverlabel=dict(bgcolor="#ffffff", font_color=P["ink"], bordercolor=P["grid"]),
        margin=dict(l=10, r=10, t=50, b=10),
        bargap=0.25,
        legend=dict(orientation="h", y=1.08, x=0),
    )
)
pio.templates.default = "plotly+tmdb"


def connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        st.error("Database not found. Run `python run_pipeline.py` from the project root first.")
        st.stop()
    return sqlite3.connect(DB_PATH, check_same_thread=False)


@st.cache_data
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params)


@st.cache_data
def load_movies() -> pd.DataFrame:
    # v_movie_summary already treats unknown money (0, or revenue < $10k) as NULL - the same
    # rule as src/financials.py, decided in notebooks/01_eda.ipynb section 2.
    m = query("SELECT * FROM v_movie_summary")
    extra = query("SELECT movie_id, release_date, overview FROM movies")
    m = m.merge(extra, on="movie_id")
    m["release_date"] = pd.to_datetime(m["release_date"])
    m["genres"] = m["genres"].fillna("")
    m["directors"] = m["directors"].fillna("Unknown")
    return m


@st.cache_data
def load_movie_genres() -> pd.DataFrame:
    return query("""SELECT mg.movie_id, g.genre_name
                    FROM movie_genres mg JOIN genres g USING (genre_id)""")


@st.cache_data
def load_genre_names() -> list[str]:
    return query("SELECT genre_name FROM genres ORDER BY genre_name")["genre_name"].tolist()


def sidebar_filters() -> pd.DataFrame:
    """One set of filters, shared by every page via session_state. Returns filtered movies."""
    movies = load_movies()
    lo, hi = int(movies.release_year.min()), int(movies.release_year.max())
    st.sidebar.header("Filters")
    ss = st.session_state
    # Widget state is dropped when you switch pages, so keep a persistent copy
    # (f_*) and seed each widget (_*) from it on every page.
    defaults = {"years": (1970, hi), "genres": [], "min_votes": 0}
    for k, v in defaults.items():
        ss.setdefault(f"f_{k}", v)
        ss[f"_{k}"] = ss[f"f_{k}"]

    def keep(k):
        return lambda: ss.update({f"f_{k}": ss[f"_{k}"]})

    years = st.sidebar.slider("Release year", lo, hi, key="_years", on_change=keep("years"))
    genres = st.sidebar.multiselect("Genres (any of)", load_genre_names(), key="_genres",
                                    on_change=keep("genres"))
    min_votes = st.sidebar.number_input("Minimum votes", 0, 40000, step=500, key="_min_votes",
                                        on_change=keep("min_votes"))
    if st.sidebar.button("Reset filters"):
        for k, v in defaults.items():
            ss[f"f_{k}"] = v
        st.rerun()
    f = movies[movies.release_year.between(*years) & (movies.vote_count >= min_votes)]
    if genres:
        ids = load_movie_genres().query("genre_name in @genres")["movie_id"]
        f = f[f.movie_id.isin(ids)]
    st.sidebar.caption(f"{len(f):,} of {len(movies):,} films match")
    st.sidebar.divider()
    st.sidebar.caption("Data: TMDB, ~2,500 popular films. Money in nominal US$ (not inflation-adjusted).")
    return f


def financial(df: pd.DataFrame) -> pd.DataFrame:
    """Films with a usable budget (>= $1M) and revenue, for ROI work."""
    return df[(df.budget >= MIN_BUDGET_FOR_ROI) & df.revenue.notna()]


def money(v: float) -> str:
    if pd.isna(v):
        return "–"
    for div, unit in [(1e9, "B"), (1e6, "M"), (1e3, "K")]:
        if abs(v) >= div:
            return f"${v / div:,.1f}{unit}"
    return f"${v:,.0f}"


def page_setup(title: str, icon: str = "🎬") -> None:
    st.set_page_config(page_title=f"{title} · TMDB analysis", page_icon=icon, layout="wide")
    st.markdown(
        """<style>
        [data-testid="stMetricValue"] {font-size: 1.8rem;}
        .block-container {padding-top: 2rem;}
        </style>""",
        unsafe_allow_html=True,
    )


def empty_guard(df: pd.DataFrame) -> None:
    if df.empty:
        st.warning("No films match the current filters. Widen the year range or clear genres.")
        st.stop()
