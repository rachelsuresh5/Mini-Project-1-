"""TMDB movie analysis dashboard - Overview page.

Run from the project root:  streamlit run dashboard/Home.py
"""
import plotly.express as px
import streamlit as st

from utils import BLUE, empty_guard, financial, money, page_setup, sidebar_filters

page_setup("Overview")
df = sidebar_filters()
empty_guard(df)

st.title("TMDB movie analysis")
st.caption("An end-to-end look at ~2,500 popular films: what they cost, what they earned, "
           "how they were rated and who made them. Use the sidebar to filter every page.")

fin = financial(df)
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Films", f"{len(df):,}")
c2.metric("Total box office", money(df.revenue.sum()))
c3.metric("Median budget", money(df.budget.median()))
c4.metric("Median ROI", f"{fin.roi.median():.1f}×" if len(fin) else "–",
          help="Revenue ÷ budget, films with budget ≥ $1M")
c5.metric("Average rating", f"{df.vote_average.mean():.2f} / 10")

st.divider()
left, right = st.columns([3, 2])

with left:
    by_year = (df.groupby("release_year")
                 .agg(films=("movie_id", "count"), revenue=("revenue", "sum"))
                 .reset_index())
    fig = px.bar(by_year, x="release_year", y="revenue",
                 title="Total box office by release year",
                 labels={"release_year": "Release year", "revenue": "Worldwide revenue"},
                 hover_data={"films": True})
    fig.update_traces(marker_color=BLUE, hovertemplate="%{x}: %{y:$,.0f}<br>%{customdata[0]} films<extra></extra>")
    fig.update_yaxes(tickprefix="$", exponentformat="B")
    st.plotly_chart(fig, width="stretch")

with right:
    fig = px.histogram(df, x="vote_average", nbins=30, title="Rating distribution",
                       labels={"vote_average": "Rating (0-10)"})
    fig.update_traces(marker_color=BLUE, marker_line_color="#fcfcfb", marker_line_width=1,
                      hovertemplate="Rating %{x}<br>%{y} films<extra></extra>")
    fig.update_yaxes(title="Films")
    fig.add_vline(df.vote_average.median(), line_color="#52514e", line_width=1,
                  annotation_text=f"median {df.vote_average.median():.2f}", annotation_position="top right")
    st.plotly_chart(fig, width="stretch")

st.subheader("Top films in this selection")
sort_by = st.radio("Rank by", ["Revenue", "Rating", "Profit", "Popularity"], horizontal=True)
col = {"Revenue": "revenue", "Rating": "vote_average", "Profit": "profit", "Popularity": "popularity"}[sort_by]
top = df.dropna(subset=[col]).nlargest(15, col)[
    ["title", "release_year", "genres", "directors", "budget", "revenue", "vote_average", "vote_count"]]
st.dataframe(
    top, hide_index=True, width="stretch",
    column_config={
        "title": "Title", "release_year": st.column_config.NumberColumn("Year", format="%d"),
        "genres": "Genres", "directors": "Director(s)",
        "budget": st.column_config.NumberColumn("Budget", format="$%,.0f"),
        "revenue": st.column_config.NumberColumn("Revenue", format="$%,.0f"),
        "vote_average": st.column_config.NumberColumn("Rating", format="%.1f"),
        "vote_count": st.column_config.NumberColumn("Votes", format="%,d"),
    })

with st.expander("Key findings from the full dataset"):
    st.markdown("""
- **Revenue follows reach, not quality.** Revenue correlates with budget (ρ ≈ 0.69) and vote count (ρ ≈ 0.54), but not with rating (ρ ≈ −0.05).
- **Animation earns the most per film** (median ≈ $311M) and also returns about 4.2× its budget.
- **Horror and Romance are cheap but efficient**: low revenue per film, but about 4× returns.
- **May to July is blockbuster season**, with November and December close behind; September is the weakest month.
- **A few hits dominate**: the top 20% of films take about 58% of all box office.
- **Selection bias**: every film has 475+ votes, so older decades include only well-remembered classics.
""")
