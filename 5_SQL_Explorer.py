import re
import sqlite3

import pandas as pd
import streamlit as st

from utils import DB_PATH, ROOT, page_setup, query

page_setup("SQL explorer")
st.title("SQL explorer")
st.caption("The analysis queries from `sql/analysis_queries.sql`, run live against the SQLite database. "
           "Pick one, or write your own read-only query.")

import sys  # noqa: E402
sys.path.insert(0, str(ROOT / "src"))
from run_queries import load_queries  # noqa: E402

qs = load_queries()
tab1, tab2, tab3 = st.tabs(["Analysis queries", "Write your own", "Schema"])

with tab1:
    labels = {q["name"]: f"{q['name'][:3].upper()} · {q['question']}" for q in qs}
    name = st.selectbox("Query", list(labels), format_func=labels.get)
    q = next(x for x in qs if x["name"] == name)
    st.markdown(f"**{q['question']}**")
    st.code(q["sql"], language="sql")
    res = query(q["sql"])
    st.dataframe(res, hide_index=True, width="stretch")
    st.download_button("Download CSV", res.to_csv(index=False), f"{name}.csv", "text/csv")

with tab2:
    default = ("SELECT g.genre_name, COUNT(*) AS films, ROUND(AVG(m.vote_average), 2) AS avg_rating\n"
               "FROM movie_genres mg\nJOIN genres g USING (genre_id)\nJOIN movies m USING (movie_id)\n"
               "GROUP BY g.genre_name\nORDER BY avg_rating DESC;")
    sql = st.text_area("SQL (SELECT / WITH only)", default, height=200)
    if st.button("Run query", type="primary"):
        if not re.match(r"^\s*(select|with)\b", sql, flags=re.I):
            st.error("Only SELECT or WITH queries are allowed here.")
        else:
            try:
                # Open read-only so nothing typed here can change the database.
                con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                out = pd.read_sql_query(sql, con)
                con.close()
                st.success(f"{len(out):,} rows")
                st.dataframe(out.head(1000), hide_index=True, width="stretch")
            except Exception as e:  # show SQL errors to the user
                st.error(str(e))

with tab3:
    st.markdown("Nine tables in third normal form. Arrows point from a foreign key to the table it references.")
    st.code("""
genres ──< movie_genres >── movies ──< movie_keywords >── keywords
                              │
                 ┌────────────┴────────────┐
            cast_credits              crew_credits ──> jobs
                 └──────> people <─────────┘
""", language="text")
    tables = query("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")["name"]
    for t in tables:
        cols = query(f"PRAGMA table_info({t})")
        n = query(f"SELECT COUNT(*) AS n FROM {t}")["n"].iloc[0]
        with st.expander(f"{t}  ·  {n:,} rows"):
            fks = query(f"PRAGMA foreign_key_list({t})")
            cols["foreign_key"] = cols["name"].map(
                {r["from"]: f"→ {r['table']}.{r['to']}" for _, r in fks.iterrows()}).fillna("")
            st.dataframe(cols[["name", "type", "notnull", "pk", "foreign_key"]],
                         hide_index=True, width="stretch")
