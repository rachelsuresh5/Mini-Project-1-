import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from utils import BLUE, GREY, P, empty_guard, financial, money, page_setup, sidebar_filters

page_setup("Box office")
df = sidebar_filters()
empty_guard(df)
fin = financial(df)
empty_guard(fin)

st.title("Box office")
st.caption(f"Financial charts use the {len(fin):,} films in this selection with a budget of at least $1M "
           "and a reported revenue. Revenue is worldwide gross, before marketing costs and cinema share.")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Median revenue", money(fin.revenue.median()))
c2.metric("Median profit", money(fin.profit.median()))
c3.metric("Grossed less than budget", f"{(fin.revenue < fin.budget).mean():.0%}")
top20 = fin.revenue.sort_values(ascending=False)
c4.metric("Revenue share of top 20% of films",
          f"{top20.head(max(1, int(len(top20) * 0.2))).sum() / top20.sum():.0%}")

st.divider()
fig = px.scatter(fin, x="budget", y="revenue", log_x=True, log_y=True, height=520,
                 title="Budget vs worldwide revenue (log scales)",
                 labels={"budget": "Budget", "revenue": "Revenue"},
                 custom_data=["title", "release_year", "roi", "genres"])
fig.update_traces(marker=dict(color=BLUE, size=7, opacity=0.5, line=dict(color="#fcfcfb", width=1)),
                  hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>Budget %{x:$,.0f}"
                                "<br>Revenue %{y:$,.0f}<br>ROI %{customdata[2]:.1f}×<br>%{customdata[3]}<extra></extra>")
lo, hi = fin.budget.min(), fin.revenue.max()
fig.add_trace(go.Scatter(x=[lo, hi], y=[lo, hi], mode="lines", line=dict(color=P["ink2"], width=1),
                         name="Break-even", hoverinfo="skip"))
fig.update_xaxes(tickprefix="$", exponentformat="B")
fig.update_yaxes(tickprefix="$", exponentformat="B")
fig.update_layout(showlegend=False)
fig.add_annotation(x=np.log10(hi / 3), y=np.log10(hi / 3), text="break-even", showarrow=False,
                   yshift=-14, font=dict(color=P["ink2"], size=11))
st.plotly_chart(fig, width="stretch")
st.caption("Films below the line grossed less than they cost. Hover any point for details.")

left, right = st.columns(2)
with left:
    bins = [1e6, 20e6, 60e6, 120e6, np.inf]
    names = ["Under $20M", "$20M-$60M", "$60M-$120M", "$120M+"]
    t = fin.assign(tier=pd.cut(fin.budget, bins, labels=names, right=False))
    tiers = (t.groupby("tier", observed=False)
              .agg(films=("movie_id", "count"), median_roi=("roi", "median"),
                   pct_loss=("profit", lambda s: (s < 0).mean() * 100),
                   median_profit=("profit", "median"))
              .reset_index())
    fig = px.bar(tiers, x="tier", y="median_roi", title="Median ROI by budget tier",
                 labels={"tier": "Budget tier", "median_roi": "Median ROI"},
                 custom_data=["films", "pct_loss", "median_profit"])
    fig.update_traces(marker_color=[P["seq"][i] for i in (2, 3, 4, 5)],
                      hovertemplate="<b>%{x}</b><br>Median ROI %{y:.2f}×<br>Median profit %{customdata[2]:$,.0f}"
                                    "<br>%{customdata[1]:.0f}% grossed under budget<br>%{customdata[0]} films<extra></extra>")
    fig.update_yaxes(ticksuffix="×")
    st.plotly_chart(fig, width="stretch")
    st.caption("Smaller films return more per dollar; bigger films make more money in absolute terms.")

with right:
    labels = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    m = (df.dropna(subset=["revenue"]).groupby("release_month")
         .agg(median_revenue=("revenue", "median"), films=("movie_id", "count"))
         .reindex(range(1, 13)).reset_index())
    m["month"] = labels
    top3 = m.median_revenue.nlargest(3).index
    fig = px.bar(m, x="month", y="median_revenue", title="Median revenue by release month",
                 labels={"month": "", "median_revenue": "Median revenue"}, custom_data=["films"])
    fig.update_traces(marker_color=[BLUE if i in top3 else GREY for i in m.index],
                      hovertemplate="%{x}: %{y:$,.0f}<br>%{customdata[0]} films<extra></extra>")
    fig.update_yaxes(tickprefix="$", exponentformat="B")
    st.plotly_chart(fig, width="stretch")
    st.caption("Top three months highlighted.")

st.subheader("Biggest hits and misses")
tab1, tab2, tab3 = st.tabs(["Best ROI", "Biggest profit", "Biggest loss"])
cols = ["title", "release_year", "budget", "revenue", "profit", "roi", "genres"]
cfg = {"title": "Title", "release_year": st.column_config.NumberColumn("Year", format="%d"),
       "budget": st.column_config.NumberColumn("Budget", format="$%,.0f"),
       "revenue": st.column_config.NumberColumn("Revenue", format="$%,.0f"),
       "profit": st.column_config.NumberColumn("Profit", format="$%,.0f"),
       "roi": st.column_config.NumberColumn("ROI", format="%.1f×"), "genres": "Genres"}
tab1.dataframe(fin.nlargest(15, "roi")[cols], hide_index=True, width="stretch", column_config=cfg)
tab2.dataframe(fin.nlargest(15, "profit")[cols], hide_index=True, width="stretch", column_config=cfg)
tab3.dataframe(fin.nsmallest(15, "profit")[cols], hide_index=True, width="stretch", column_config=cfg)
