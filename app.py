import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import requests

st.set_page_config(
    page_title="미국 주식 분석",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .block-container { padding: 1rem 1rem 2rem; }
    .metric-card {
        background: #f8f9fa;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 8px;
    }
    h1 { font-size: 1.6rem !important; }
    .signal-buy { color: #2d8a4e; font-weight: 600; }
    .signal-sell { color: #c0392b; font-weight: 600; }
    .signal-neutral { color: #7f8c8d; font-weight: 600; }
    @media (max-width: 768px) {
        .block-container { padding: 0.5rem; }
    }
</style>
""", unsafe_allow_html=True)

POPULAR_STOCKS = {
    "🍎 Apple (AAPL)": "AAPL",
    "🚗 Tesla (TSLA)": "TSLA",
    "🖥️ NVIDIA (NVDA)": "NVDA",
    "💻 Microsoft (MSFT)": "MSFT",
    "📦 Amazon (AMZN)": "AMZN",
    "🔍 Alphabet (GOOGL)": "GOOGL",
    "📱 Meta (META)": "META",
    "💳 Berkshire (BRK-B)": "BRK-B",
}

NEWS_API_KEY = st.secrets.get("NEWS_API_KEY", "")

@st.cache_data(ttl=300)
def get_stock_data(ticker, period):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period=period)
        info = stock.info
        return hist, info
    except Exception as e:
        return None, {}

def compute_signals(hist):
    signals = {}
    close = hist["Close"]

    ma20 = close.rolling(20).mean()
    ma50 = close.rolling(50).mean()
    if len(close) >= 50:
        if ma20.iloc[-1] > ma50.iloc[-1]:
            signals["이동평균 (MA20/50)"] = ("매수", "🟢")
        else:
            signals["이동평균 (MA20/50)"] = ("매도", "🔴")

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    rsi_val = round(rsi.iloc[-1], 1)
    if rsi_val < 30:
        signals[f"RSI ({rsi_val})"] = ("과매도 — 매수 고려", "🟢")
    elif rsi_val > 70:
        signals[f"RSI ({rsi_val})"] = ("과매수 — 매도 고려", "🔴")
    else:
        signals[f"RSI ({rsi_val})"] = ("중립", "⚪")

    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    if macd.iloc[-1] > signal_line.iloc[-1]:
        signals["MACD"] = ("매수", "🟢")
    else:
        signals["MACD"] = ("매도", "🔴")

    ma20b = close.rolling(20).mean()
    std = close.rolling(20).std()
    upper = ma20b + 2 * std
    lower = ma20b - 2 * std
    curr = close.iloc[-1]
    if curr < lower.iloc[-1]:
        signals["볼린저 밴드"] = ("과매도 구간", "🟢")
    elif curr > upper.iloc[-1]:
        signals["볼린저 밴드"] = ("과매수 구간", "🔴")
    else:
        signals["볼린저 밴드"] = ("밴드 내 위치", "⚪")

    return signals

@st.cache_data(ttl=1800)
def get_news(query, api_key):
    if not api_key:
        return []
    try:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": query,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 5,
            "apiKey": api_key,
        }
        resp = requests.get(url, params=params, timeout=5)
        data = resp.json()
        return data.get("articles", [])
    except:
        return []

def sentiment_score(text):
    pos_words = ["surge", "growth", "record", "beat", "strong", "gain", "rally", "profit", "rise", "up"]
    neg_words = ["drop", "fall", "loss", "miss", "weak", "decline", "cut", "concern", "risk", "down"]
    text_lower = text.lower()
    pos = sum(1 for w in pos_words if w in text_lower)
    neg = sum(1 for w in neg_words if w in text_lower)
    if pos > neg:
        return "긍정 🟢", "#2d8a4e"
    elif neg > pos:
        return "부정 🔴", "#c0392b"
    return "중립 ⚪", "#7f8c8d"

st.title("📈 미국 주식 분석 대시보드")

col_sel, col_period = st.columns([3, 1])

with col_sel:
    selected_label = st.selectbox(
        "종목 선택",
        list(POPULAR_STOCKS.keys()),
        label_visibility="collapsed"
    )
    ticker = POPULAR_STOCKS[selected_label]

custom = st.text_input("또는 직접 입력 (예: AMZN, NFLX)", placeholder="티커 입력 후 Enter", label_visibility="collapsed")
if custom.strip():
    ticker = custom.strip().upper()

with col_period:
    period = st.selectbox("기간", ["1mo", "3mo", "6mo", "1y", "2y"], index=2, label_visibility="collapsed")

period_label = {"1mo": "1개월", "3mo": "3개월", "6mo": "6개월", "1y": "1년", "2y": "2년"}

with st.spinner(f"{ticker} 데이터 불러오는 중..."):
    hist, info = get_stock_data(ticker, period)

if hist is None or hist.empty:
    st.error("데이터를 불러올 수 없어요. 티커를 확인해 주세요.")
    st.stop()

curr_price = hist["Close"].iloc[-1]
prev_price = hist["Close"].iloc[-2]
change = curr_price - prev_price
change_pct = (change / prev_price) * 100
color = "normal" if change_pct >= 0 else "inverse"

c1, c2, c3, c4 = st.columns(4)
c1.metric("현재가", f"${curr_price:.2f}", f"{change_pct:+.2f}%", delta_color=color)
c2.metric("시가총액", f"${info.get('marketCap', 0)/1e9:.1f}B" if info.get('marketCap') else "N/A")
c3.metric("52주 최고", f"${info.get('fiftyTwoWeekHigh', 0):.2f}" if info.get('fiftyTwoWeekHigh') else "N/A")
c4.metric("52주 최저", f"${info.get('fiftyTwoWeekLow', 0):.2f}" if info.get('fiftyTwoWeekLow') else "N/A")

st.subheader(f"{ticker} 주가 ({period_label[period]})")
fig = go.Figure()
fig.add_trace(go.Candlestick(
    x=hist.index,
    open=hist["Open"],
    high=hist["High"],
    low=hist["Low"],
    close=hist["Close"],
    name=ticker,
    increasing_line_color="#2d8a4e",
    decreasing_line_color="#c0392b"
))
ma20 = hist["Close"].rolling(20).mean()
fig.add_trace(go.Scatter(x=hist.index, y=ma20, name="MA20", line=dict(color="#3498db", width=1.2)))
fig.update_layout(
    xaxis_rangeslider_visible=False,
    height=380,
    margin=dict(l=0, r=0, t=10, b=0),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    xaxis=dict(showgrid=False),
    yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
    legend=dict(orientation="h", y=1.02),
    font=dict(size=12)
)
st.plotly_chart(fig, use_container_width=True)

col_sig, col_news = st.columns(2)

with col_sig:
    st.subheader("매매 신호")
    if len(hist) >= 20:
        signals = compute_signals(hist)
        buy_count = sum(1 for v in signals.values() if v[0].startswith("매수") or "과매도" in v[0])
        sell_count = sum(1 for v in signals.values() if v[0].startswith("매도") or "과매수" in v[0])
        total = len(signals)
        if buy_count > sell_count:
            overall = f"🟢 종합: 매수 우세 ({buy_count}/{total})"
        elif sell_count > buy_count:
            overall = f"🔴 종합: 매도 우세 ({sell_count}/{total})"
        else:
            overall = f"⚪ 종합: 중립 ({total}개 지표)"
        st.info(overall)
        for name, (label, icon) in signals.items():
            st.write(f"{icon} **{name}** — {label}")
    else:
        st.write("데이터가 부족해 신호를 계산할 수 없어요.")

with col_news:
    st.subheader("뉴스 & 감성 분석")
    company_name = info.get("longName", ticker)
    articles = get_news(company_name, NEWS_API_KEY)
    if articles:
        pos_n = neu_n = neg_n = 0
        for a in articles:
            title = a.get("title", "")
            desc = a.get("description", "") or ""
            sent, color_hex = sentiment_score(title + " " + desc)
            if "긍정" in sent: pos_n += 1
            elif "부정" in sent: neg_n += 1
            else: neu_n += 1
            source = a.get("source", {}).get("name", "")
            st.markdown(f"**{title[:60]}...**  \n{sent} · {source}")
            st.divider()
        total_n = pos_n + neu_n + neg_n
        if total_n:
            st.progress(pos_n / total_n, text=f"긍정 {pos_n} / 중립 {neu_n} / 부정 {neg_n}")
    else:
        st.info("뉴스 API 키를 설정하면 실시간 뉴스가 표시돼요.\n\nsecrets.toml에 `NEWS_API_KEY`를 추가해 주세요.")
        st.markdown("""
**뉴스 없이도 분석 가능한 항목:**
- 주가 차트 (실시간)
- 기술적 지표 신호
- 재무 지표
        """)

with st.expander("재무 정보"):
    fin_data = {
        "PER (주가수익비율)": info.get("trailingPE"),
        "PBR (주가순자산비율)": info.get("priceToBook"),
        "배당수익률": f"{info.get('dividendYield', 0)*100:.2f}%" if info.get("dividendYield") else "N/A",
        "베타": info.get("beta"),
        "애널리스트 목표주가": f"${info.get('targetMeanPrice', 0):.2f}" if info.get("targetMeanPrice") else "N/A",
        "추천": info.get("recommendationKey", "N/A"),
    }
    for k, v in fin_data.items():
        if v:
            st.write(f"**{k}**: {round(v, 2) if isinstance(v, float) else v}")

st.caption(f"데이터 출처: Yahoo Finance · 마지막 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
