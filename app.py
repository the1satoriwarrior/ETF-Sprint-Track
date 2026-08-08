import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from streamlit_autorefresh import st_autorefresh
from datetime import datetime
import pytz

# ---------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------
st.set_page_config(page_title="Live ETF 100m Dash", layout="wide")
st.title("🏃 Live ETF Intraday 100m Dash")

TICKERS = ['GSEW', 'EUSA', 'VV', 'VTI', 'AVLV', 'RSP',
           'EQWL', 'EQAL', 'SCHB', 'BKLC', 'VONV', 'VOOV']

REFRESH_SECONDS = 15          # how often the page reruns
CACHE_TTL = 10                # how often new data is actually fetched
FINISH_LINE_PCT = 1.0         # % gain that reaches the finish line (100m mark)
LANE_HEIGHT = 1               # vertical spacing between lanes
TRACK_LENGTH = 100             # in "meters" for display purposes

EASTERN = pytz.timezone("US/Eastern")


def market_is_open() -> bool:
    now = datetime.now(EASTERN)
    if now.weekday() >= 5:
        return False
    open_t = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_t = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return open_t <= now <= close_t


# ---------------------------------------------------------------
# AUTO-REFRESH
# ---------------------------------------------------------------
st_autorefresh(interval=REFRESH_SECONDS * 1000, key="datarefresh")


# ---------------------------------------------------------------
# DATA
# ---------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL)
def get_live_data(tickers):
    """Return % change from today's open for each ticker."""
    df = yf.download(tickers, period="1d", interval="1m", progress=False)["Close"]

    if isinstance(df, pd.Series):
        df = df.to_frame(name=tickers[0])

    df = df.dropna(how="all")
    if df.empty:
        return pd.Series({t: 0.0 for t in tickers})

    first_valid = df.apply(lambda col: col.dropna().iloc[0] if col.dropna().size else np.nan)
    last_valid = df.apply(lambda col: col.dropna().iloc[-1] if col.dropna().size else np.nan)

    pct_change = ((last_valid - first_valid) / first_valid) * 100
    return pct_change.reindex(tickers)


try:
    pct_gains = get_live_data(TICKERS)
except Exception as e:
    st.error(f"Data fetch failed: {e}")
    st.stop()

status = "🟢 Market Open" if market_is_open() else "🔴 Market Closed (showing last available data)"
st.caption(f"{status} · Last refreshed: {datetime.now(EASTERN).strftime('%I:%M:%S %p %Z')}")


# ---------------------------------------------------------------
# BUILD THE SPRINT TRACK
# ---------------------------------------------------------------
fig = go.Figure()

ranked = pct_gains.sort_values(ascending=False)
n = len(ranked)

colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
          "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
          "#393b79", "#843c39"]

# Draw lane dividers (horizontal lines)
for lane in range(n + 1):
    y = lane * LANE_HEIGHT
    fig.add_trace(go.Scatter(
        x=[0, TRACK_LENGTH], y=[y, y],
        mode="lines", line=dict(color="white", width=2),
        showlegend=False, hoverinfo="skip",
    ))

# Shade the track background
fig.add_shape(
    type="rect", x0=0, x1=TRACK_LENGTH, y0=0, y1=n * LANE_HEIGHT,
    fillcolor="#c96a3c", opacity=0.5, line=dict(width=0), layer="below",
)

# Start line
fig.add_shape(
    type="line", x0=0, x1=0, y0=0, y1=n * LANE_HEIGHT,
    line=dict(color="white", width=4),
)

# Finish line (checkered look using dashed white line)
fig.add_shape(
    type="line", x0=TRACK_LENGTH, x1=TRACK_LENGTH, y0=0, y1=n * LANE_HEIGHT,
    line=dict(color="black", width=6, dash="dot"),
)
fig.add_annotation(
    x=TRACK_LENGTH, y=n * LANE_HEIGHT + 0.3, text="🏁 FINISH", showarrow=False,
    font=dict(size=14, color="black"),
)

# Place each runner in their own lane, position = progress toward finish line
for i, (ticker, gain) in enumerate(ranked.items()):
    gain_val = 0.0 if pd.isna(gain) else float(gain)

    # Clamp progress between 0 and the finish line (100m), based on % gain vs FINISH_LINE_PCT
    progress_fraction = np.clip(gain_val / FINISH_LINE_PCT, -0.05, 1.0)
    x = progress_fraction * TRACK_LENGTH

    lane_y = (n - i - 0.5) * LANE_HEIGHT  # leader in top lane

    # Runner emoji as the marker itself
    fig.add_trace(go.Scatter(
        x=[x], y=[lane_y],
        mode="text",
        text=["🏃"],
        textfont=dict(size=28),
        hovertext=[f"{ticker}: {gain_val:+.2f}%"],
        hoverinfo="text",
        showlegend=False,
    ))

    # Ticker label to the left of the lane (fixed position, doesn't move)
    fig.add_annotation(
        x=-3, y=lane_y, text=f"<b>{ticker}</b>", showarrow=False,
        font=dict(size=12, color=colors[i % len(colors)]), xanchor="right",
    )

    # % gain label near the runner
    fig.add_annotation(
        x=x, y=lane_y + 0.3, text=f"{gain_val:+.2f}%", showarrow=False,
        font=dict(size=10, color="black"),
    )

fig.update_layout(
    xaxis=dict(visible=False, range=[-15, TRACK_LENGTH + 10]),
    yaxis=dict(visible=False, range=[-0.5, n * LANE_HEIGHT + 1]),
    height=max(500, n * 55),
    margin=dict(l=80, r=20, t=20, b=20),
    plot_bgcolor="white",
)

st.plotly_chart(fig, use_container_width=True)

# Leaderboard table underneath
st.subheader("Leaderboard")
board = ranked.reset_index()
board.columns = ["Ticker", "% Change Today"]
board.index = board.index + 1
st.dataframe(board.style.format({"% Change Today": "{:+.2f}%"}), use_container_width=True)

st.caption(
    f"Finish line = {FINISH_LINE_PCT:+.1f}% gain. Runners past the line have exceeded that threshold; "
    "this is a visualization, not a literal race."
)
