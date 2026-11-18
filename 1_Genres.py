import pandas as pd
import plotly.express as px
import streamlit as st

from utils import BLUE, GREY, empty_guard, financial, load_movie_genres, page_setup, sidebar_filters, P

page_setup("Genres")
df = sidebar_filters()
empty_guard(df)

st.title("Genres")
st.caption("Films carry 2-3 genres on average, so each film counts once in every genre it belongs to.")

g = load_movie_genres().merge(df, on="movie_id")
fin_ids = set(financial(df).movie_id)
stats = (g.groupby("genre_name")
          .agg(films=("movie_id", "nunique"),
               median_revenue=("revenue", "median"),
               avg_rating=("vote_average", "mean"),
               median_budget=("budget", "median"))
          .reset_index())
roi = g[g.movie_id.isin(fin_ids)].groupby("genre_name")["roi"].median().rename("median_roi")
stats = stats.merge(roi, on="genre_name", how="left")
min_films = st.slider("Only show genres with at least this many films", 1, 100, 10)
stats = stats[stats.films >= min_films]
empty_guard(stats)

metric = st.radio("Compare genres by", ["Median revenue", "Median ROI", "Average rating", "Number of films"],
                  horizontal=True)
col, fmt, axis = {
    "Median revenue": ("median_revenue", "%{x:$,.0f}", dict(tickprefix="$", exponentformat="B")),
    "Median ROI": ("median_roi", "%{x:.2f}×", dict(ticksuffix="×")),
    "Average rating": ("avg_rating", "%{x:.2f}", dict()),
    "Number of films": ("films", "%{x:,}", dict()),
}[metric]
s = stats.sort_values(col)
fig = px.bar(s, x=col, y="genre_name", orientation="h", title=f"{metric} by genre",
             labels={col: metric, "genre_name": ""}, height=max(380, 28 * len(s)),
             custom_data=["films"])
fig.update_traces(marker_color=BLUE, hovertemplate=f"<b>%{{y}}</b><br>{metric}: {fmt}<br>%{{customdata[0]}} films<extra></extra>")
fig.update_xaxes(**axis)
if col == "median_roi":
    fig.add_vline(1, line_color=P["ink2"], line_width=1, annotation_text="break-even")
if col == "avg_rating":
    fig.update_xaxes(range=[s.avg_rating.min() - 0.3, s.avg_rating.max() + 0.1])
st.plotly_chart(fig, width="stretch")

left, right = st.columns(2)
with left:
    fig = px.scatter(stats, x="median_budget", y="median_revenue", size="films", text=stats.genre_name.where(stats.films >= stats.films.nlargest(6).min(), ""),
                     title="Typical budget vs typical revenue", size_max=40,
                     labels={"median_budget": "Median budget", "median_revenue": "Median revenue"},
                     custom_data=["genre_name", "films", "median_roi"])
    fig.update_traces(marker=dict(color=BLUE, opacity=0.55, line=dict(color="#fcfcfb", width=2)),
                      textposition="top center", textfont_size=11,
                      hovertemplate="<b>%{customdata[0]}</b><br>Budget %{x:$,.0f}<br>Revenue %{y:$,.0f}"
                                    "<br>ROI %{customdata[2]:.2f}×<br>%{customdata[1]} films<extra></extra>")
    fig.update_xaxes(tickprefix="$", exponentformat="B")
    fig.update_yaxes(tickprefix="$", exponentformat="B")
    st.plotly_chart(fig, width="stretch")

with right:
    mix = g.groupby(["decade", "genre_name"]).size().rename("n").reset_index()
    totals = df.groupby("decade").size().rename("total")
    mix = mix.join(totals, on="decade")
    mix["share"] = mix.n / mix.total * 100
    keep = stats.nlargest(10, "films").genre_name
    pivot = mix[mix.genre_name.isin(keep)].pivot(index="genre_name", columns="decade", values="share").fillna(0)
    pivot = pivot.loc[stats.set_index("genre_name").loc[keep].sort_values("films", ascending=False).index]
    pivot.columns = [f"{c}s" for c in pivot.columns]
    fig = px.imshow(pivot, color_continuous_scale=P["seq"], aspect="auto", text_auto=".0f",
                    title="Share of each decade's films by genre (%)",
                    labels=dict(color="% of films", x="", y=""))
    fig.update_traces(hovertemplate="%{y}, %{x}: %{z:.1f}% of films<extra></extra>")
    st.plotly_chart(fig, width="stretch")

st.subheader("Genre table")
st.dataframe(stats.sort_values("films", ascending=False), hide_index=True, width="stretch",
             column_config={
                 "genre_name": "Genre", "films": "Films",
                 "median_revenue": st.column_config.NumberColumn("Median revenue", format="$%,.0f"),
                 "avg_rating": st.column_config.NumberColumn("Avg rating", format="%.2f"),
                 "median_budget": st.column_config.NumberColumn("Median budget", format="$%,.0f"),
                 "median_roi": st.column_config.NumberColumn("Median ROI", format="%.2f×"),
             })
