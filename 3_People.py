import plotly.express as px
import streamlit as st

from utils import BLUE, P, empty_guard, money, page_setup, query, sidebar_filters

page_setup("People")
df = sidebar_filters()
empty_guard(df)

st.title("Directors and actors")


@st.cache_data
def credits():
    directors = query("""SELECT c.movie_id, p.person_id, p.person_name
                         FROM crew_credits c JOIN jobs j USING (job_id) JOIN people p USING (person_id)
                         WHERE j.job = 'Director'""")
    cast = query("""SELECT c.movie_id, p.person_id, p.person_name, c.character_name, c.cast_order
                    FROM cast_credits c JOIN people p USING (person_id)""")
    return directors, cast


directors, cast = credits()
role = st.radio("Show", ["Directors", "Actors (top-billed)"], horizontal=True)
if role == "Directors":
    people = directors.merge(df, on="movie_id")
else:
    top_n = st.slider("Count an actor's role if billed in the top…", 1, 10, 5)
    people = cast[cast.cast_order < top_n].merge(df, on="movie_id")

stats = (people.groupby(["person_id", "person_name"])
               .agg(films=("movie_id", "nunique"), total_revenue=("revenue", "sum"),
                    avg_rating=("vote_average", "mean"))
               .reset_index())
min_films = st.slider("Minimum films", 1, 20, 3)
stats = stats[stats.films >= min_films]
empty_guard(stats)

left, right = st.columns(2)
with left:
    top = stats.nlargest(15, "total_revenue").sort_values("total_revenue")
    fig = px.bar(top, x="total_revenue", y="person_name", orientation="h", height=520,
                 title="Highest total box office", labels={"total_revenue": "Total revenue", "person_name": ""},
                 custom_data=["films", "avg_rating"])
    fig.update_traces(marker_color=BLUE,
                      hovertemplate="<b>%{y}</b><br>%{x:$,.0f} total<br>%{customdata[0]} films"
                                    "<br>Avg rating %{customdata[1]:.2f}<extra></extra>")
    fig.update_xaxes(tickprefix="$", exponentformat="B")
    st.plotly_chart(fig, width="stretch")
with right:
    top = stats.nlargest(15, "avg_rating").sort_values("avg_rating")
    fig = px.bar(top, x="avg_rating", y="person_name", orientation="h", height=520,
                 title="Highest average rating", labels={"avg_rating": "Average rating", "person_name": ""},
                 custom_data=["films", "total_revenue"])
    fig.update_traces(marker_color=BLUE,
                      hovertemplate="<b>%{y}</b><br>Avg rating %{x:.2f}<br>%{customdata[0]} films"
                                    "<br>%{customdata[1]:$,.0f} total<extra></extra>")
    fig.update_xaxes(range=[top.avg_rating.min() - 0.3, top.avg_rating.max() + 0.05])
    st.plotly_chart(fig, width="stretch")

fig = px.scatter(stats, x="films", y="avg_rating", size="total_revenue", size_max=35, height=480,
                 title="Volume vs acclaim (bubble size = total revenue)",
                 labels={"films": "Films in selection", "avg_rating": "Average rating"},
                 custom_data=["person_name", "total_revenue"])
fig.update_traces(marker=dict(color=BLUE, opacity=0.5, line=dict(color="#fcfcfb", width=2)),
                  hovertemplate="<b>%{customdata[0]}</b><br>%{x} films · avg %{y:.2f}"
                                "<br>%{customdata[1]:$,.0f} total<extra></extra>")
st.plotly_chart(fig, width="stretch")

st.divider()
st.subheader("Look up a person")
name = st.selectbox("Name", sorted(stats.person_name.unique()), index=None, placeholder="Start typing a name…")
if name:
    films = people[people.person_name == name].sort_values("release_year")
    s = stats[stats.person_name == name].iloc[0]
    c1, c2, c3 = st.columns(3)
    c1.metric("Films", int(s.films))
    c2.metric("Total box office", money(s.total_revenue))
    c3.metric("Average rating", f"{s.avg_rating:.2f}")
    fig = px.scatter(films, x="release_year", y="vote_average", size=films.revenue.fillna(0) + 1,
                     size_max=30, title=f"{name}: films over time (bubble size = revenue)",
                     labels={"release_year": "Year", "vote_average": "Rating"},
                     custom_data=["title", "revenue"])
    fig.update_traces(marker=dict(color=BLUE, opacity=0.6, line=dict(color="#fcfcfb", width=2)),
                      hovertemplate="<b>%{customdata[0]}</b> (%{x})<br>Rating %{y:.2f}"
                                    "<br>Revenue %{customdata[1]:$,.0f}<extra></extra>")
    st.plotly_chart(fig, width="stretch")
    cols = ["title", "release_year", "vote_average", "revenue", "genres"]
    if "character_name" in films:
        cols.insert(1, "character_name")
    st.dataframe(films[cols], hide_index=True, width="stretch",
                 column_config={"revenue": st.column_config.NumberColumn("Revenue", format="$%,.0f"),
                                "release_year": st.column_config.NumberColumn("Year", format="%d")})

st.divider()
st.subheader("Recurring actor-director partnerships")
pairs = query("""
    SELECT d.person_name AS director, a.person_name AS actor, COUNT(*) AS films_together,
           ROUND(AVG(m.vote_average), 2) AS avg_rating, SUM(m.revenue) AS total_revenue
    FROM crew_credits cr
    JOIN jobs j ON j.job_id = cr.job_id AND j.job = 'Director'
    JOIN cast_credits ca ON ca.movie_id = cr.movie_id AND ca.cast_order < 5
    JOIN people d ON d.person_id = cr.person_id
    JOIN people a ON a.person_id = ca.person_id
    JOIN movies m ON m.movie_id = cr.movie_id
    WHERE cr.person_id <> ca.person_id
    GROUP BY cr.person_id, ca.person_id
    HAVING COUNT(*) >= 3
    ORDER BY films_together DESC, avg_rating DESC""")
st.dataframe(pairs.head(30), hide_index=True, width="stretch",
             column_config={"director": "Director", "actor": "Actor", "films_together": "Films together",
                            "avg_rating": st.column_config.NumberColumn("Avg rating", format="%.2f"),
                            "total_revenue": st.column_config.NumberColumn("Total revenue", format="$%,.0f")})
st.caption("Across the full dataset (not filtered). Actor counted when billed in the top 5.")
