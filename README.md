# TMDB movie analysis: an end-to-end data analyst project

An end-to-end analysis of **2,503 popular films** from The Movie Database (TMDB). The project
takes six raw relational CSV files through cleaning, a normalised SQLite database, SQL
analysis, exploratory analysis in Pandas, static visualisations and a multi-page Streamlit
dashboard.

**Questions answered**

1. What drives box office revenue: budget, genre, release timing or quality?
2. Which genres earn the most, rate the best and give the best return on investment?
3. Who are the most commercially successful and most acclaimed directors and actors?
4. How have budgets, ratings and the genre mix changed over the decades?

---

## Quick start

```bash
# 1. Create an environment and install dependencies (Python 3.10+)
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Rebuild everything from the raw CSVs (clean -> database -> SQL -> EDA)
python run_pipeline.py             # add --skip-eda to skip re-running the notebooks

# 3. Launch the dashboard
streamlit run dashboard/Home.py
```

The database (`db/tmdb.db`), processed data, query results and figures are already included,
so you can launch the dashboard straight away without step 2.

---

## How the project follows the brief's steps

| Brief step | Where it happens | What to look at |
|---|---|---|
| Load all six CSVs into DataFrames and inspect shape, dtypes and nulls | `notebooks/00_load_clean_and_sql.ipynb`, step 1 | overview table plus a per-column profile (dtype, nulls, null %, unique) for each file |
| Clean each table: fix types, remove exact duplicates, remove orphaned rows | `src/clean.py`, run in notebook 00 step 2 | `release_date` parsed to a date, all IDs enforced as integers, 59 exact duplicate rows removed, orphan check on every link table; [`reports/data_cleaning_log.md`](reports/data_cleaning_log.md) |
| Don't silently fix budget/revenue of 0 | Cleaning keeps them as 0; decided in `notebooks/01_eda.ipynb`, section 2 | the EDA shows the effect of zeros on the statistics, then treats them as unknown (NaN) with a written justification; rule in `src/financials.py` |
| Load all tables into SQL with sqlite3 / **SQLAlchemy** | `src/build_db.py` and notebook 00 step 3 | SQLAlchemy `create_engine` + `DataFrame.to_sql`, foreign keys enforced and checked |
| Run a test JOIN (movies, movie_genres, genres) before the analysis | `src/build_db.py` and notebook 00 step 4 | the result is saved in [`reports/db_load_check.md`](reports/db_load_check.md) |

---

## Project structure

```
tmdb-analysis/
├── data/
│   ├── raw/                  # the six original CSVs, untouched
│   └── processed/            # cleaned, normalised tables (one CSV per DB table)
├── db/
│   └── tmdb.db               # SQLite database (9 tables + 1 view)
├── sql/
│   ├── schema.sql            # DDL: tables, keys, constraints, indexes, view
│   └── analysis_queries.sql  # 17 named analysis queries
├── src/
│   ├── config.py             # paths, thresholds and chart palette
│   ├── clean.py              # step 1: load + clean, writes the cleaning log
│   ├── build_db.py           # step 2: load into SQLite with SQLAlchemy + checks + test JOIN
│   ├── financials.py         # the unknown budget/revenue rule, shared by EDA and dashboard
│   ├── run_queries.py        # step 3: run every SQL query, save results
│   └── viz_style.py          # shared matplotlib style
├── notebooks/
│   ├── 00_load_clean_and_sql.ipynb  # load + inspect CSVs, clean, load to SQL (SQLAlchemy), test JOIN
│   └── 01_eda.ipynb                 # Pandas EDA: zero-budget decision, charts, findings
├── reports/
│   ├── data_cleaning_log.md  # every cleaning rule with before/after counts
│   ├── db_load_check.md      # row counts, foreign-key check and the test JOIN result
│   ├── load_clean_report.html # notebook 00 exported as HTML
│   ├── sql_results.md        # every query, its SQL and its result table
│   ├── eda_report.html       # notebook 01 exported as HTML
│   ├── query_results/        # one CSV per SQL query
│   └── figures/              # 10 PNG charts used below
├── dashboard/
│   ├── Home.py               # overview page (entry point)
│   ├── utils.py              # shared data loading, filters and chart theme
│   └── pages/                # Genres, Box Office, People, Movie Explorer, SQL Explorer
├── run_pipeline.py           # runs steps 1-4 in order
└── requirements.txt
```

---

## 1. Data cleaning

The raw data is mostly well formed, but it contains several realistic problems. Every rule is
applied in `src/clean.py` and logged with counts in
[`reports/data_cleaning_log.md`](reports/data_cleaning_log.md).

| Issue found | Decision | Rows affected |
|---|---|---|
| Exact duplicate films (e.g. *Gladiator*, *Doom*) | Dropped, kept one copy | 6 |
| `release_date` stored as text | Parsed to a date; year, month and decade derived | all |
| ID columns | Enforced as integers (fails loudly if any are missing) | all tables |
| Budget or revenue = 0 | **Kept as 0** in the cleaned data and database (TMDB's code for "unknown"). Decided in the EDA: treated as unknown, never as $0 | 90 budgets, 102 revenues |
| Implausible revenue (e.g. *The Emoji Movie* listed at $216) | Flagged in cleaning; treated as unknown in the EDA | 6 |
| Orphaned rows (a `movie_id` not in the cleaned movies) | Removed (the check runs on every link table; none were found) | 0 |
| Exact duplicate rows in genre, keyword, cast and crew tables | Removed, kept one copy | 10 / 20 / 15 / 8 |
| Stray whitespace in keyword names | Trimmed | 34 |
| Missing character names in cast | Kept as NULL (the credit is still valid) | 11 |
| Micro-budget outliers (*Primer*, $7,000) | Kept, but ROI rankings require budget ≥ $1M | 1 |
| A few films with no genre, cast, keywords or director | Kept; they drop out of that analysis only | 4-7 each |

**Principles:** fix types, not values; keep rows (a film with no budget is still valid for
rating analysis); never invent values; and fail loudly on impossible data (range and referential
checks are asserted in code). Derived columns: `release_year`, `release_month`, `decade`.

**Unknown budget and revenue (the Pandas decision).** Section 2 of the EDA notebook counts the
zeros, shows how they would drag down the averages and break ROI, and decides to treat them, and the
6 implausible revenues, as unknown (NaN) rather than $0. Films are kept for all non-money analysis,
and nothing is imputed. Profit and ROI are only calculated when both values are known.

## 2. Relational database (SQLite, 3NF, loaded with SQLAlchemy)

The cleaned tables are loaded with SQLAlchemy (`create_engine` + `DataFrame.to_sql`) into tables
created by `sql/schema.sql`, parents before children so the foreign keys resolve. The load is then
checked with row counts, `PRAGMA foreign_key_check`, and a test JOIN across `movies`,
`movie_genres` and `genres`. The result is in [`reports/db_load_check.md`](reports/db_load_check.md).

All six original tables are in the database. `cast` and `crew` are stored as `cast_credits`
and `crew_credits`, and three small lookup tables (`people`, `keywords`, `jobs`) are added so
repeated names are stored once.

```
genres ──< movie_genres >── movies ──< movie_keywords >── keywords
                              │
                 ┌────────────┴────────────┐
            cast_credits              crew_credits ──> jobs
                 └──────> people <─────────┘
```

| Table | Rows | Key | Notes |
|---|---|---|---|
| `movies` | 2,503 | `movie_id` | one row per film; raw budget/revenue (0 = unknown) |
| `genres` | 19 | `genre_id` | lookup |
| `movie_genres` | 6,878 | (`movie_id`, `genre_id`) | many-to-many bridge |
| `keywords` | 10,288 | `keyword_id` | extracted from the keyword file |
| `movie_keywords` | 41,681 | (`movie_id`, `keyword_id`) | many-to-many bridge |
| `people` | 13,960 | `person_id` | actors and crew in one table (188 people are both) |
| `jobs` | 3 | `job_id` | job → department |
| `cast_credits` | 24,902 | `cast_id` | FK to movies and people; billing order |
| `crew_credits` | 7,289 | `crew_id` | FK to movies, people and jobs |

**Normalisation decisions.** In the raw files, person names were repeated on every credit,
keyword names on every movie-keyword row, and department was repeated next to every job. Each of
these is moved into its own lookup table (`people`, `keywords`, `jobs`) so every fact is stored
once. Foreign keys are enforced, `CHECK` constraints guard value ranges, and indexes cover the
join columns. A view, `v_movie_summary`, applies the unknown-money rule (0 → NULL), derives profit
and ROI, and flattens each film's genres and directors. The money queries read from this view.

## 3. SQL analysis

`sql/analysis_queries.sql` holds 17 named queries; results are in
[`reports/sql_results.md`](reports/sql_results.md). They use multi-table joins, aggregation with
`HAVING`, CTEs, window functions (`ROW_NUMBER`, `RANK`, running `SUM() OVER`), self-joins and
`CASE` bucketing.

| # | Question |
|---|---|
| Q01 | Dataset overview and financial completeness |
| Q02 | Genre performance: revenue, rating and pooled ROI |
| Q03 | Top 15 highest-grossing films and their directors |
| Q04 | Best return on investment (budget ≥ $1M) |
| Q05 | Budget, revenue, runtime and rating trends by decade |
| Q06 | Directors with the highest total box office |
| Q07 | Highest-rated directors (5+ films) and their consistency |
| Q08 | Actors with the most top-billed roles |
| Q09 | Recurring actor-director partnerships (self-join) |
| Q10 | Most common keywords and their dominant genre (window function) |
| Q11 | Keywords associated with the highest revenue |
| Q12 | Budget tiers: ROI, share losing money, rating |
| Q13 | Revenue by release month |
| Q14 | Best-rated film each year since 2000 (`RANK()`) |
| Q15 | Most common genre pairings (self-join) |
| Q16 | Revenue concentration: share earned by the top N% of films |
| Q17 | Non-English-language films compared |

## 4. Exploratory analysis and key findings

The notebook [`notebooks/01_eda.ipynb`](notebooks/01_eda.ipynb) (also exported to
[`reports/eda_report.html`](reports/eda_report.html)) starts with the unknown budget/revenue
decision, then covers distributions, correlations, genre, timing, people and change over time.

**1. Revenue follows reach, not quality.** Revenue correlates strongly with budget (Spearman
ρ = 0.69) and with vote count (ρ = 0.54), but not with rating (ρ = −0.05).

![Budget vs revenue](reports/figures/02_budget_vs_revenue.png)

**2. Genre sets the ceiling.** Animation earns the most per film (median ≈ $311M) and also
returns about 4.2× its budget. Horror and Romance earn little per film but return about 4×
because they are cheap to make. Westerns and History have the weakest returns.

![Genre revenue and ROI](reports/figures/04_genre_revenue_roi.png)

**3. Timing matters.** May, June and July releases have the highest median revenue, followed by
November and December. September is the weakest month.

![Release month](reports/figures/05_release_month.png)

**4. Box office is concentrated.** The top 20% of films earn about 58% of all revenue; the top 1%
alone earn 7.5%.

![Revenue concentration](reports/figures/10_revenue_concentration.png)

**5. Smaller budgets, bigger multiples.** Films under $20M have the highest ROI; only about 8% of
films grossed less than their budget (box office alone, before marketing and cinema share).

**6. Beware selection bias.** Every film has at least 475 votes, so older decades include only
well-remembered classics. That is why average ratings fall over time: it reflects what survives,
not films getting worse.

Other figures in `reports/figures/`: distributions, correlation heatmap, trends by decade, genre
mix by decade, top directors, and directors' volume vs rating.

## 5. Streamlit dashboard

`streamlit run dashboard/Home.py` opens a six-page dashboard. Sidebar filters (release years,
genres, minimum votes) apply to every page and are remembered as you move between pages.

| Page | What it shows |
|---|---|
| **Home** | KPI tiles, box office by year, rating distribution, top films ranked by revenue / rating / profit / popularity |
| **Genres** | Compare genres by revenue, ROI, rating or count; budget vs revenue by genre; genre share by decade heatmap |
| **Box Office** | Interactive budget vs revenue scatter with break-even line, ROI by budget tier, revenue by month, biggest hits and flops |
| **People** | Top directors or actors by box office and rating, volume vs acclaim, per-person lookup, recurring partnerships |
| **Movie Explorer** | Search titles, plots and keywords; film detail card with cast, keywords and "similar films" computed in SQL |
| **SQL Explorer** | Run any of the 17 analysis queries live, write your own read-only query, browse the schema |

## Limitations

- Money is in **nominal** US dollars, not adjusted for inflation.
- Revenue is worldwide **gross**; profit and ROI ignore marketing costs and the cinema's share.
- The sample is **popular films only** (475+ votes), so it is not representative of all releases.
- Older films' revenue may include re-releases, which inflates ROI for classics such as
  *Snow White* and *Gone with the Wind*.

## Tools

Python (pandas, NumPy), SQLite, SQLAlchemy, SQL, Jupyter, matplotlib, Plotly, Streamlit.
