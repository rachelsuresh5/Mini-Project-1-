"""Shared paths and constants for the TMDB analysis pipeline."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
DB_PATH = ROOT / "db" / "tmdb.db"
SQL_DIR = ROOT / "sql"
REPORTS_DIR = ROOT / "reports"
FIGURES_DIR = REPORTS_DIR / "figures"
QUERY_RESULTS_DIR = REPORTS_DIR / "query_results"

# --- Cleaning thresholds (see reports/data_cleaning_log.md for the reasoning) ---
# Reported revenue below this is treated as a data-entry error, not a real box office.
MIN_PLAUSIBLE_REVENUE = 10_000
# Financial ratios (ROI, profit) only use films with at least this budget, so a
# micro-budget outlier like Primer ($7k) does not dominate every ROI ranking.
MIN_BUDGET_FOR_ROI = 1_000_000
# Ratings from fewer votes than this are excluded from "best rated" rankings.
MIN_VOTES_FOR_RATING = 1_000

# Chart palette (validated reference palette from the dataviz skill)
PALETTE = {
    "series": ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
               "#e87ba4", "#008300", "#6250d6", "#e34948"],
    "seq": ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
            "#256abf", "#184f95", "#0d366b"],
    "neg": "#e34948",
    "neutral": "#c3c2b7",
    "surface": "#fcfcfb",
    "ink": "#0b0b0b",
    "ink2": "#52514e",
    "muted": "#898781",
    "grid": "#e1e0d9",
    "axis": "#c3c2b7",
}
