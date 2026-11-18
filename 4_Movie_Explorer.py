import plotly.express as px
import streamlit as st

from utils import BLUE, GREY, P, empty_guard, money, page_setup, query, sidebar_filters

page_setup("Movie explorer")
df = sidebar_filters()
empty_guard(df)

st.title("Movie explorer")

c1, c2 = st.columns([2, 1])
search = c1.text_input("Search titles, overviews or keywords", placeholder="e.g. time travel, heist, Pixar…")
sort = c2.selectbox("Sort by", ["Popularity", "Rating", "Revenue", "Newest"])

view = df
if search:
    kw_ids = query("""SELECT DISTINCT mk.movie_id FROM movie_keywords mk JOIN keywords k USING (keyword_id)
                      WHERE k.keyword_name LIKE ?""", (f"%{search.lower()}%",))["movie_id"]
    mask = (df.title.str.contains(search, case=False, regex=False)
            | df.overview.fillna("").str.contains(search, case=False, regex=False)
            | df.movie_id.isin(kw_ids))
    view = df[mask]
key = {"Popularity": "popularity", "Rating": "vote_average", "Revenue": "revenue", "Newest": "release_date"}[sort]
view = view.sort_values(key, ascending=False, na_position="last")
st.caption(f"{len(view):,} films")
empty_guard(view)

st.dataframe(view[["title", "release_year", "genres", "directors", "vote_average", "revenue"]].head(200),
             hide_index=True, width="stretch", height=300,
             column_config={"title": "Title", "release_year": st.column_config.NumberColumn("Year", format="%d"),
                            "genres": "Genres", "directors": "Director(s)",
                            "vote_average": st.column_config.NumberColumn("Rating", format="%.1f"),
                            "revenue": st.column_config.NumberColumn("Revenue", format="$%,.0f")})

st.divider()
options = view.head(500)
label = options.title + " (" + options.release_year.astype(str) + ")"
pick = st.selectbox("Open a film", options.movie_id, format_func=dict(zip(options.movie_id, label)).get)
m = df[df.movie_id == pick].iloc[0]

st.header(f"{m.title} ({m.release_year})")
st.caption(f"{m.genres}  ·  {m.runtime} min  ·  Directed by {m.directors}  ·  Language: {m.original_language}")
c = st.columns(5)
c[0].metric("Rating", f"{m.vote_average:.1f}", help=f"{m.vote_count:,} votes")
c[1].metric("Budget", money(m.budget))
c[2].metric("Revenue", money(m.revenue))
c[3].metric("ROI", f"{m.roi:.1f}×" if m.roi == m.roi and m.roi is not None else "–")
pct = (df.vote_average < m.vote_average).mean() * 100
c[4].metric("Rated higher than", f"{pct:.0f}%", help="of films in the current selection")
st.write(m.overview)

left, right = st.columns([3, 2])
with left:
    cast = query("""SELECT p.person_name AS actor, c.character_name AS character, c.cast_order
                    FROM cast_credits c JOIN people p USING (person_id)
                    WHERE c.movie_id = ? ORDER BY c.cast_order""", (int(pick),))
    st.subheader("Cast")
    st.dataframe(cast[["actor", "character"]], hide_index=True, width="stretch",
                 column_config={"actor": "Actor", "character": "Character"})
with right:
    kws = query("""SELECT k.keyword_name FROM movie_keywords mk JOIN keywords k USING (keyword_id)
                   WHERE mk.movie_id = ? ORDER BY k.keyword_name""", (int(pick),))
    st.subheader("Keywords")
    st.write(" · ".join(kws.keyword_name) if len(kws) else "No keywords recorded.")

st.subheader("Similar films")
st.caption("Ranked by number of shared keywords and genres.")
sim = query("""
    WITH k AS (SELECT keyword_id FROM movie_keywords WHERE movie_id = :id),
         g AS (SELECT genre_id FROM movie_genres WHERE movie_id = :id)
    SELECT m.movie_id, m.title, m.release_year, m.vote_average,
           (SELECT COUNT(*) FROM movie_keywords mk WHERE mk.movie_id = m.movie_id
              AND mk.keyword_id IN (SELECT keyword_id FROM k)) AS shared_keywords,
           (SELECT COUNT(*) FROM movie_genres mg WHERE mg.movie_id = m.movie_id
              AND mg.genre_id IN (SELECT genre_id FROM g)) AS shared_genres
    FROM movies m WHERE m.movie_id <> :id
    ORDER BY shared_keywords * 2 + shared_genres DESC, m.vote_average DESC
    LIMIT 10""", {"id": int(pick)})
st.dataframe(sim.drop(columns="movie_id"), hide_index=True, width="stretch",
             column_config={"title": "Title", "release_year": st.column_config.NumberColumn("Year", format="%d"),
                            "vote_average": st.column_config.NumberColumn("Rating", format="%.1f"),
                            "shared_keywords": "Shared keywords", "shared_genres": "Shared genres"})
