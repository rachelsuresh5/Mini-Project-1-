"""How unknown budget/revenue values are handled in the analysis.

The cleaned data and the database keep TMDB's raw values, including 0 ("unknown").
This module holds the analysis decision, so the EDA notebook and the dashboard apply
exactly the same rule. The reasoning is shown step by step in notebooks/01_eda.ipynb
(section 2):

* budget == 0 or revenue == 0  -> unknown (NaN), never treated as $0
* 0 < revenue < $10,000          -> unknown (NaN); these are data-entry errors
* profit and ROI are only computed when both values are known
* ROI rankings use budget >= $1M so micro-budget films don't dominate
"""
import numpy as np
import pandas as pd

from config import MIN_BUDGET_FOR_ROI, MIN_PLAUSIBLE_REVENUE


def apply_unknown_financials(movies: pd.DataFrame) -> pd.DataFrame:
    m = movies.copy()
    m["budget"] = m["budget"].astype("float").replace(0, np.nan)
    m["revenue"] = m["revenue"].astype("float").replace(0, np.nan)
    m.loc[m["revenue"] < MIN_PLAUSIBLE_REVENUE, "revenue"] = np.nan
    m["profit"] = m["revenue"] - m["budget"]
    m["roi"] = (m["revenue"] / m["budget"]).round(3)
    m["has_financials"] = m["budget"].notna() & m["revenue"].notna()
    return m


def roi_sample(movies: pd.DataFrame) -> pd.DataFrame:
    """Films usable for ROI work: both values known and budget >= $1M."""
    return movies[(movies["budget"] >= MIN_BUDGET_FOR_ROI) & movies["revenue"].notna()]
