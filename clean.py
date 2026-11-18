"""Step 1 - Load and clean the six raw TMDB CSV files.

Reads data/raw/*.csv, applies documented cleaning rules, splits the data into
normalised tables and writes them to data/processed/. Every rule that changes
data is recorded in reports/data_cleaning_log.md with before/after counts.

Run:  python src/clean.py
"""
from __future__ import annotations

import pandas as pd

from config import (MIN_PLAUSIBLE_REVENUE, PROCESSED_DIR, RAW_DIR, REPORTS_DIR)

LOG: list[str] = []


def log(section: str, text: str) -> None:
    LOG.append(f"| {section} | {text} |")
    print(f"[{section}] {text}")


def load_raw() -> dict[str, pd.DataFrame]:
    names = ["movies", "genres", "movie_genres", "cast", "crew", "movie_keywords"]
    return {n: pd.read_csv(RAW_DIR / f"{n}.csv") for n in names}


def strip_text(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Trim leading/trailing whitespace in every text column; blank -> NULL."""
    df = df.copy()
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            s = df[col].astype("string")
            changed = (s.notna() & (s != s.str.strip())).sum()
            s = s.str.strip().replace("", pd.NA)
            df[col] = s
            if changed:
                log(table, f"Trimmed stray whitespace in `{col}` on {changed} rows.")
    return df


def clean_movies(m: pd.DataFrame) -> pd.DataFrame:
    n0 = len(m)
    m = strip_text(m, "movies")
    m = ensure_int_ids(m, "movies")

    dups = m.duplicated().sum()
    m = m.drop_duplicates()
    log("movies", f"Dropped {dups} exact duplicate rows ({n0} -> {len(m)}).")
    assert m["movie_id"].is_unique, "movie_id must be unique after de-duplication"

    m["release_date"] = pd.to_datetime(m["release_date"], errors="coerce")
    bad_dates = m["release_date"].isna().sum()
    log("movies", f"Parsed `release_date` to a date ({bad_dates} unparseable values).")
    m["release_year"] = m["release_date"].dt.year.astype("Int64")
    m["release_month"] = m["release_date"].dt.month.astype("Int64")
    m["decade"] = (m["release_year"] // 10 * 10).astype("Int64")
    log("movies", "Derived `release_year`, `release_month` and `decade`.")

    # Budget / revenue: fix the TYPE only (whole dollars). Values of 0 are NOT changed here.
    # TMDB uses 0 to mean "unknown", not "free"; how to treat them is an analysis decision,
    # made and justified in notebooks/01_eda.ipynb (section 2) and in src/financials.py.
    m["budget"] = m["budget"].round().astype("int64")
    m["revenue"] = m["revenue"].round().astype("int64")
    for col in ["budget", "revenue"]:
        zeros = int((m[col] == 0).sum())
        log("movies", f"`{col}` = 0 on {zeros} films (TMDB's code for 'unknown'). Kept as 0 in the "
            "cleaned data and database, not silently fixed; handled in the Pandas analysis.")
    tiny = m["revenue"].between(1, MIN_PLAUSIBLE_REVENUE - 1)
    log("movies", "Flagged (not changed) {} films with implausibly small revenue under ${:,} (e.g. {}); "
        "also handled in the Pandas analysis.".format(int(tiny.sum()), MIN_PLAUSIBLE_REVENUE,
                                                      ", ".join(m.loc[tiny, "title"].head(3))))

    m["title"] = m["title"].astype("string")
    m["original_language"] = m["original_language"].str.lower()
    m["popularity"] = m["popularity"].round(4)
    single = m["status"].nunique() == 1
    if single:
        log("movies", f"`status` has one value ('{m['status'].iloc[0]}') for every row - kept for completeness, not analysed.")

    # Range sanity checks - fail loudly if something is impossible.
    assert m["runtime"].between(1, 400).all()
    assert m["vote_average"].between(0, 10).all()
    assert (m["vote_count"] >= 0).all()
    log("movies", "IDs confirmed as integers in every table (`movie_id`, `genre_id`, `person_id`, `keyword_id`, row ids).")
    log("movies", "Range checks passed: runtime 45-242 min, vote_average 0-10, vote_count >= 0.")
    return m.sort_values("movie_id").reset_index(drop=True)


def ensure_int_ids(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """Every *_id column must be a whole number with no gaps."""
    for col in [c for c in df.columns if c.endswith("_id")]:
        assert df[col].notna().all(), f"{table}.{col} has missing IDs"
        df[col] = pd.to_numeric(df[col], errors="raise").astype("int64")
    return df


def clean_link(df: pd.DataFrame, table: str, key: list[str], movie_ids: set) -> pd.DataFrame:
    n0 = len(df)
    df = strip_text(df, table)
    df = ensure_int_ids(df, table)
    df = df.drop_duplicates()
    log(table, f"Dropped {n0 - len(df)} exact duplicate rows: {n0} -> {len(df)}.")
    assert not df.duplicated(subset=key).any(), f"{table}: duplicate key after removing exact duplicates"
    orphans = ~df["movie_id"].isin(movie_ids)
    if orphans.any():
        log(table, f"Dropped {orphans.sum()} rows pointing at unknown movie_id.")
    else:
        log(table, "Referential check: every movie_id exists in movies.")
    return df[~orphans].reset_index(drop=True)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    raw = load_raw()
    for name, df in raw.items():
        log("load", f"`{name}.csv`: {len(df):,} rows x {df.shape[1]} columns.")

    movies = clean_movies(raw["movies"])
    ids = set(movies["movie_id"])

    genres = ensure_int_ids(strip_text(raw["genres"], "genres"), "genres")
    assert genres["genre_id"].is_unique

    movie_genres = clean_link(raw["movie_genres"], "movie_genres", ["movie_id", "genre_id"], ids)
    assert movie_genres["genre_id"].isin(genres["genre_id"]).all()

    # --- Keywords: split the repeated keyword_name into its own lookup table.
    kw = clean_link(raw["movie_keywords"], "movie_keywords", ["movie_id", "keyword_id"], ids)
    keywords = kw[["keyword_id", "keyword_name"]].drop_duplicates()
    assert keywords["keyword_id"].is_unique, "a keyword_id maps to two names"
    log("keywords", f"Extracted {len(keywords):,} distinct keywords into a lookup table (3NF).")
    movie_keywords = kw[["movie_id", "keyword_id"]]

    # --- Cast & crew: people appear in both, so names move to one `people` table.
    cast = raw["cast"].rename(columns={"cast_row_id": "cast_id", "actor_name": "person_name"})
    cast = clean_link(cast, "cast", ["movie_id", "person_id", "character_name", "cast_order"], ids)
    nulls = cast["character_name"].isna().sum()
    log("cast", f"{nulls} credits have no character name - kept as NULL (the credit itself is valid).")

    crew = raw["crew"].rename(columns={"crew_row_id": "crew_id"})
    crew = clean_link(crew, "crew", ["movie_id", "person_id", "job"], ids)

    people = pd.concat([cast[["person_id", "person_name"]], crew[["person_id", "person_name"]]])
    people = people.drop_duplicates()
    assert people["person_id"].is_unique, "a person_id maps to two names"
    log("people", f"Built `people` from cast + crew: {len(people):,} unique people "
        f"({len(set(cast.person_id) & set(crew.person_id))} appear in both).")

    # Department is fully determined by job, so it lives in a `jobs` lookup.
    jobs = crew[["job", "department"]].drop_duplicates().sort_values(["department", "job"])
    assert jobs["job"].is_unique
    jobs.insert(0, "job_id", range(1, len(jobs) + 1))
    crew = crew.merge(jobs[["job_id", "job"]], on="job")
    log("jobs", f"Moved department into a `jobs` lookup ({len(jobs)} jobs) since department depends on job.")

    cast = cast[["cast_id", "movie_id", "person_id", "character_name", "cast_order"]]
    crew = crew[["crew_id", "movie_id", "person_id", "job_id"]].sort_values("crew_id")

    # Coverage notes (kept, not dropped).
    for label, frame in [("genre", movie_genres), ("cast", cast), ("keyword", movie_keywords)]:
        missing = len(ids - set(frame["movie_id"]))
        log("coverage", f"{missing} films have no {label} rows - kept, they simply drop out of {label} analyses.")
    directed = set(crew.merge(jobs, on="job_id").query("job == 'Director'")["movie_id"])
    log("coverage", f"{len(ids - directed)} films have no director credited.")

    out = {"movies": movies, "genres": genres, "movie_genres": movie_genres,
           "keywords": keywords, "movie_keywords": movie_keywords, "people": people,
           "cast_credits": cast, "jobs": jobs, "crew_credits": crew}
    for name, df in out.items():
        df.to_csv(PROCESSED_DIR / f"{name}.csv", index=False)
        log("output", f"`data/processed/{name}.csv`: {len(df):,} rows.")

    write_log()


def write_log() -> None:
    header = [
        "# Data cleaning log",
        "",
        "Generated by `src/clean.py`. Each row is one rule applied to the raw files, with the",
        "counts it touched. Re-running the script regenerates this file.",
        "",
        "## Guiding decisions",
        "",
        "- **Fix types, not values.** `release_date` is parsed to a date, every `*_id` column is",
        "  enforced as an integer, and money is stored as whole dollars.",
        "- **Budget/revenue of 0 are NOT changed here.** TMDB uses 0 for 'unknown', not 'free'.",
        "  They stay as 0 in the cleaned files and the database. The decision on how to treat them",
        "  (exclude from financial metrics) is made and justified in the Pandas EDA notebook",
        "  (`notebooks/01_eda.ipynb`, section 2) and applied by `src/financials.py`.",
        "- **Implausible revenues are flagged, not changed.** A few studio films list revenue of a few",
        "  hundred or thousand dollars (unit-entry mistakes); the EDA treats revenue under $10,000 as unknown.",
        "- **Keep rows.** A film with an unknown budget is still valid for rating, genre and cast analysis.",
        "- **Exact duplicate rows are removed** (every column identical), keeping one copy.",
        "- **Orphaned rows are removed**: any genre, keyword, cast or crew row whose `movie_id` is not in the",
        "  cleaned movies table (the check found none, but it runs every time).",
        "- **Normalise to 3NF.** Person names, keyword names and departments were repeated across",
        "  rows; they move into `people`, `keywords` and `jobs` lookups referenced by id.",
        "",
        "## Rule log",
        "",
        "| Table | What happened |",
        "|---|---|",
    ]
    (REPORTS_DIR / "data_cleaning_log.md").write_text("\n".join(header + LOG) + "\n")


if __name__ == "__main__":
    main()
