import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import requests
import json
from datetime import datetime, timedelta

st.set_page_config(
    page_title="주식 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .block-container { padding: 1.2rem 1.5rem 2rem; }
    .metric-label { font-size: 12px !important; }
    .stTabs [data-baseweb="tab"] { font-size: 14px; padding: 8px 16px; }
    .signal-card {
        background: #f8f9fa; border-radius: 10px;
        padding: 10px 14px; margin-bottom: 6px;
        display: flex; justify-content: space-between; align-items: center;
    }
    .news-card {
        border-left: 3px solid #ddd; padding: 8px 12px; margin-bottom: 8px;
        border-radius: 0 8px 8px 0;
    }
    .news-pos { border-left-color: #2d8a4e; }
    .news-neg { border-left-color: #c0392b; }
    .news-neu { border-left-color: #888; }
</style>
""", unsafe_allow_html=True)

# ── API 키 로드 ──────────────────────────────────────────
NEWS_API_KEY      = st.secrets.get("NEWS_API_KEY", "")
KAKAO_TOKEN       = st.secrets.get("KAKAO_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

POPULAR_STOCKS = {
    "🍎 Apple (AAPL)": "AAPL",
    "🖥️ NVIDIA (NVDA)": "NVDA",
    "🚗 Tesla (TSLA)": "TSLA",
    "💻 Microsoft (MSFT)": "MSFT",
    "📦 Amazon (AMZN)": "AMZN",
    "🔍 Alphabet (GOOGL)": "GOOGL",
    "📱 Meta (META)": "META",
    "🎬 Netflix (NFLX)": "NFLX",
}

# ── 데이터 함수 ──────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stock(ticker, period):
    try:
        s = yf.Ticker(ticker)
        hist = s.history(period=period)
        info = s.info
        return hist, info
    except:
        return None, {}

@st.cache_data(ttl=1800)
def get_news(query, api_key):
    if not api_key:
        return []
    try:
        r = requests.get("https://newsapi.org/v2/everything", params={
            "q": query, "language": "en",
            "sortBy": "publishedAt", "pageSize": 6, "apiKey": api_key
        }, timeout=5)
        return r.json().get("articles", [])
    except:
        return []

def sentiment(text):
    pos = ["surge","growth","record","beat","strong","gain","rally","profit","rise","upgrade","bullish"]
    neg = ["drop","fall","loss","miss","weak","decline","cut","concern","risk","downgrade","bearish","recall"]
    t = text.lower()
    p = sum(1 for w in pos if w in t)
    n = sum(1 for w in neg if w in t)
    if p > n: return "긍정", "🟢", "news-pos", "#2d8a4e"
    if n > p: return "부정", "🔴", "news-neg", "#c0392b"
    return "중립", "⚪", "news-neu", "#888"

def compute_signals(hist):
    close = hist["Close"]
    signals = {}

    if len(close) >= 50:
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        if ma20.iloc[-1] > ma50.iloc[-1]:
            signals["이동평균 MA20/50"] = ("매수", "🟢", ma20.iloc[-1])
        else:
            signals["이동평균 MA20/50"] = ("매도", "🔴", ma20.iloc[-1])

        if len(close) >= 200:
            ma200 = close.rolling(200).mean()
            if ma20.iloc[-1] > ma200.iloc[-1]:
                signals["골든크로스 (MA20/200)"] = ("매수", "🟢", None)
            else:
                signals["데드크로스 (MA20/200)"] = ("매도", "🔴", None)

    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / loss))
    rsi_val = round(rsi.iloc[-1], 1)
    if rsi_val < 30:
        signals[f"RSI ({rsi_val})"] = ("과매도 — 매수 고려", "🟢", rsi_val)
    elif rsi_val > 70:
        signals[f"RSI ({rsi_val})"] = ("과매수 — 매도 고려", "🔴", rsi_val)
    else:
        signals[f"RSI ({rsi_val})"] = ("중립", "⚪", rsi_val)

    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    signal_line = macd.ewm(span=9).mean()
    if macd.iloc[-1] > signal_line.iloc[-1]:
        signals["MACD"] = ("매수", "🟢", round(macd.iloc[-1], 3))
    else:
        signals["MACD"] = ("매도", "🔴", round(macd.iloc[-1], 3))

    std = close.rolling(20).std()
    upper_bb = close.rolling(20).mean() + 2 * std
    lower_bb = close.rolling(20).mean() - 2 * std
    curr = close.iloc[-1]
    if curr < lower_bb.iloc[-1]:
        signals["볼린저밴드"] = ("하단 이탈 — 반등 기대", "🟢", None)
    elif curr > upper_bb.iloc[-1]:
        signals["볼린저밴드"] = ("상단 돌파 — 과열 주의", "🔴", None)
    else:
        signals["볼린저밴드"] = ("밴드 내 위치", "⚪", None)

    return signals, rsi_val

def compute_portfolio_stats(holdings):
    total_val = sum(h["shares"] * h["curr"] for h in holdings)
    total_cost = sum(h["shares"] * h["avg"] for h in holdings)
    total_gain = total_val - total_cost
    total_ret = (total_gain / total_cost * 100) if total_cost else 0
    return total_val, total_cost, total_gain, total_ret

# ── 카카오톡 알림 ─────────────────────────────────────────
def send_kakao(token, message):
    if not token:
        return False
    try:
        r = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {token}"},
            data={"template_object": json.dumps({
                "object_type": "text",
                "text": message,
                "link": {"web_url": "https://www.google.com/finance"}
            })},
            timeout=5
        )
        return r.status_code == 200
    except:
        return False

# ── Claude AI 포트폴리오 추천 ────────────────────────────
def ai_portfolio_recommend(risk, amount, sectors, api_key):
    if not api_key:
        return None
    prompt = f"""당신은 미국 주식 투자 전문가입니다.
투자자 정보:
- 투자 성향: {risk}
- 투자 금액: ${amount:,}
- 관심 섹터: {', '.join(sectors)}

위 조건에 맞는 미국 주식 포트폴리오를 추천해주세요.
반드시 JSON 형식으로만 답변하세요. 다른 텍스트는 절대 포함하지 마세요.
형식:
{{
  "summary": "포트폴리오 요약 한 줄",
  "stocks": [
    {{"ticker": "AAPL", "name": "Apple", "weight": 25, "reason": "추천 이유 한 문장"}},
    ...
  ],
  "strategy": "전체 전략 설명 2~3문장"
}}
5~7개 종목, weight 합계는 반드시 100이어야 합니다."""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            },
            json={
                "model": "claude-sonnet-4-20250514",
                "max_tokens": 1000,
                "messages": [{"role": "user", "content": prompt}]
            },
            timeout=30
        )
        text = r.json()["content"][0]["text"]
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except Exception as e:
        return None

# ── 주가 예측 (Prophet) ──────────────────────────────────
def run_prophet(hist, days):
    try:
        from prophet import Prophet
        df = hist[["Close"]].reset_index()
        df.columns = ["ds", "y"]
        df["ds"] = pd.to_datetime(df["ds"]).dt.tz_localize(None)
        m = Prophet(daily_seasonality=False, yearly_seasonality=True, changepoint_prior_scale=0.05)
        m.fit(df)
        future = m.make_future_dataframe(periods=days)
        fc = m.predict(future)
        return df, fc
    except Exception as e:
        st.error(f"Prophet 오류: {e}")
        return None, None

# ────────────────────────────────────────────────────────
# 사이드바
# ────────────────────────────────────────────────────────
with st.sidebar:
    st.title("📈 주식 분석")
    selected_label = st.selectbox("종목 선택", list(POPULAR_STOCKS.keys()))
    ticker = POPULAR_STOCKS[selected_label]
    custom = st.text_input("직접 입력 (예: NFLX)", placeholder="티커 입력")
    if custom.strip():
        ticker = custom.strip().upper()
    period = st.selectbox("기간", ["1mo","3mo","6mo","1y","2y"], index=3,
                          format_func=lambda x: {"1mo":"1개월","3mo":"3개월","6mo":"6개월","1y":"1년","2y":"2년"}[x])

    st.divider()
    st.markdown("**가격 알림 설정**")
    alert_high = st.number_input("목표가 (상단)", min_value=0.0, value=0.0, step=1.0)
    alert_low  = st.number_input("하한가 (하단)", min_value=0.0, value=0.0, step=1.0)
    kakao_alert = st.toggle("카카오톡 알림 연동", value=False)

    st.divider()
    st.caption(f"최종 업데이트: {datetime.now().strftime('%H:%M:%S')}")

# ────────────────────────────────────────────────────────
# 데이터 로드
# ────────────────────────────────────────────────────────
with st.spinner(f"{ticker} 데이터 불러오는 중..."):
    hist, info = get_stock(ticker, period)

if hist is None or hist.empty:
    st.error("데이터를 불러올 수 없어요. 티커를 확인해 주세요.")
    st.stop()

curr_price = hist["Close"].iloc[-1]
prev_price = hist["Close"].iloc[-2]
change_pct = (curr_price - prev_price) / prev_price * 100

# 가격 알림 체크
if alert_high > 0 and curr_price >= alert_high:
    msg = f"[주식 알림] {ticker} 목표가 도달!\n현재가: ${curr_price:.2f} (목표: ${alert_high:.2f})"
    st.warning(msg)
    if kakao_alert and KAKAO_TOKEN:
        if send_kakao(KAKAO_TOKEN, msg):
            st.success("카카오톡 알림 전송 완료!")
        else:
            st.error("카카오톡 전송 실패 — 토큰을 확인하세요.")

if alert_low > 0 and curr_price <= alert_low and alert_low > 0:
    msg = f"[주식 알림] {ticker} 하한가 도달!\n현재가: ${curr_price:.2f} (하한: ${alert_low:.2f})"
    st.error(msg)
    if kakao_alert and KAKAO_TOKEN:
        send_kakao(KAKAO_TOKEN, msg)

# ────────────────────────────────────────────────────────
# 상단 지표 카드
# ────────────────────────────────────────────────────────
st.title(f"{info.get('longName', ticker)}  ({ticker})")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("현재가", f"${curr_price:.2f}", f"{change_pct:+.2f}%",
          delta_color="normal" if change_pct >= 0 else "inverse")
c2.metric("시가총액", f"${info.get('marketCap',0)/1e9:.1f}B" if info.get("marketCap") else "N/A")
c3.metric("52주 최고", f"${info.get('fiftyTwoWeekHigh',0):.2f}" if info.get("fiftyTwoWeekHigh") else "N/A")
c4.metric("52주 최저", f"${info.get('fiftyTwoWeekLow',0):.2f}" if info.get("fiftyTwoWeekLow") else "N/A")
c5.metric("배당수익률", f"{info.get('dividendYield',0)*100:.2f}%" if info.get("dividendYield") else "N/A")

# ────────────────────────────────────────────────────────
# 탭 구성
# ────────────────────────────────────────────────────────
tabs = st.tabs(["📊 차트 & 지표", "📋 재무 분석", "🔔 매매 신호", "📰 뉴스 & 감성",
                "💼 포트폴리오", "🔮 주가 예측", "🤖 AI 추천", "📱 카카오 알림"])

# ─── 탭 1: 차트 & 지표 ───────────────────────────────────
with tabs[0]:
    col_c, col_s = st.columns([3, 1])

    with col_c:
        fig = go.Figure()
        fig.add_trace(go.Candlestick(
            x=hist.index, open=hist["Open"], high=hist["High"],
            low=hist["Low"], close=hist["Close"], name=ticker,
            increasing_line_color="#2d8a4e", decreasing_line_color="#c0392b"
        ))
        ma20 = hist["Close"].rolling(20).mean()
        ma50 = hist["Close"].rolling(50).mean()
        fig.add_trace(go.Scatter(x=hist.index, y=ma20, name="MA20",
                                 line=dict(color="#3498db", width=1.2)))
        fig.add_trace(go.Scatter(x=hist.index, y=ma50, name="MA50",
                                 line=dict(color="#e67e22", width=1.2, dash="dot")))

        # 볼린저밴드
        std = hist["Close"].rolling(20).std()
        upper_bb = ma20 + 2 * std
        lower_bb = ma20 - 2 * std
        fig.add_trace(go.Scatter(x=hist.index, y=upper_bb, name="BB상단",
                                 line=dict(color="gray", width=0.8, dash="dash")))
        fig.add_trace(go.Scatter(x=hist.index, y=lower_bb, name="BB하단",
                                 line=dict(color="gray", width=0.8, dash="dash"),
                                 fill="tonexty", fillcolor="rgba(128,128,128,0.05)"))

        fig.update_layout(xaxis_rangeslider_visible=False, height=420,
                          margin=dict(l=0,r=0,t=10,b=0),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          xaxis=dict(showgrid=False),
                          yaxis=dict(showgrid=True, gridcolor="#f0f0f0"),
                          legend=dict(orientation="h", y=1.05))
        st.plotly_chart(fig, use_container_width=True)

        # 거래량
        vol_colors = ["#2d8a4e" if c >= o else "#c0392b"
                      for c, o in zip(hist["Close"], hist["Open"])]
        fig_vol = go.Figure(go.Bar(x=hist.index, y=hist["Volume"],
                                   marker_color=vol_colors, name="거래량"))
        fig_vol.update_layout(height=120, margin=dict(l=0,r=0,t=0,b=0),
                               paper_bgcolor="rgba(0,0,0,0)",
                               plot_bgcolor="rgba(0,0,0,0)",
                               xaxis=dict(showgrid=False),
                               yaxis=dict(showgrid=False, showticklabels=False))
        st.plotly_chart(fig_vol, use_container_width=True)

    with col_s:
        st.subheader("멀티 종목 비교")
        compare_tickers = st.multiselect("비교 종목 추가", ["AAPL","NVDA","TSLA","MSFT","AMZN","GOOGL","META"],
                                         default=["AAPL","NVDA"])
        if compare_tickers:
            fig_cmp = go.Figure()
            for t in compare_tickers:
                h, _ = get_stock(t, period)
                if h is not None and not h.empty:
                    norm = h["Close"] / h["Close"].iloc[0] * 100
                    fig_cmp.add_trace(go.Scatter(x=h.index, y=norm, name=t, mode="lines"))
            fig_cmp.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)",
                                   yaxis_title="수익률 (기준 100)",
                                   xaxis=dict(showgrid=False),
                                   yaxis=dict(gridcolor="#f0f0f0"),
                                   legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_cmp, use_container_width=True)

        st.subheader("52주 위치")
        high52 = info.get("fiftyTwoWeekHigh", curr_price)
        low52  = info.get("fiftyTwoWeekLow", curr_price)
        if high52 > low52:
            pos_pct = (curr_price - low52) / (high52 - low52) * 100
            st.progress(int(pos_pct))
            st.caption(f"52주 범위 내 위치: {pos_pct:.1f}%\n최저 ${low52:.2f} ~ 최고 ${high52:.2f}")

# ─── 탭 2: 재무 분석 ────────────────────────────────────
with tabs[1]:
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        st.subheader("핵심 재무 지표")
        fin = {
            "PER (주가수익비율)": info.get("trailingPE"),
            "PBR (주가순자산비율)": info.get("priceToBook"),
            "PSR (주가매출비율)": info.get("priceToSalesTrailing12Months"),
            "EPS": info.get("trailingEps"),
            "베타": info.get("beta"),
            "부채비율": info.get("debtToEquity"),
            "ROE": info.get("returnOnEquity"),
            "ROA": info.get("returnOnAssets"),
            "영업이익률": info.get("operatingMargins"),
            "순이익률": info.get("profitMargins"),
        }
        for k, v in fin.items():
            if v is not None:
                fmt = f"{v*100:.2f}%" if k in ["ROE","ROA","영업이익률","순이익률"] else f"{v:.2f}"
                st.metric(k, fmt)

    with col_f2:
        st.subheader("애널리스트 의견")
        target = info.get("targetMeanPrice")
        rec    = info.get("recommendationKey", "N/A")
        if target:
            upside = (target - curr_price) / curr_price * 100
            st.metric("목표 주가", f"${target:.2f}", f"현재 대비 {upside:+.1f}%",
                      delta_color="normal" if upside > 0 else "inverse")
        rec_map = {"buy":"강력 매수","overperform":"매수","hold":"보유",
                   "underperform":"매도","sell":"강력 매도"}
        st.info(f"**추천**: {rec_map.get(rec, rec.upper())}")

        # 재무제표 간단 요약
        st.subheader("매출 & 이익 추이")
        try:
            s = yf.Ticker(ticker)
            fin_stmt = s.financials
            if fin_stmt is not None and not fin_stmt.empty:
                rev = fin_stmt.loc["Total Revenue"] if "Total Revenue" in fin_stmt.index else None
                net = fin_stmt.loc["Net Income"] if "Net Income" in fin_stmt.index else None
                if rev is not None:
                    fig_fin = go.Figure()
                    fig_fin.add_trace(go.Bar(x=[str(d.year) for d in rev.index],
                                             y=rev.values/1e9, name="매출(B)", marker_color="#3498db"))
                    if net is not None:
                        fig_fin.add_trace(go.Bar(x=[str(d.year) for d in net.index],
                                                 y=net.values/1e9, name="순이익(B)", marker_color="#2d8a4e"))
                    fig_fin.update_layout(height=260, barmode="group",
                                          margin=dict(l=0,r=0,t=10,b=0),
                                          paper_bgcolor="rgba(0,0,0,0)",
                                          plot_bgcolor="rgba(0,0,0,0)")
                    st.plotly_chart(fig_fin, use_container_width=True)
        except:
            st.caption("재무제표 데이터를 불러올 수 없어요.")

# ─── 탭 3: 매매 신호 ────────────────────────────────────
with tabs[2]:
    if len(hist) >= 20:
        signals, rsi_val = compute_signals(hist)
        buy_cnt  = sum(1 for v in signals.values() if "매수" in v[0] or "과매도" in v[0] or "반등" in v[0])
        sell_cnt = sum(1 for v in signals.values() if "매도" in v[0] or "과매수" in v[0] or "과열" in v[0])
        total    = len(signals)

        col_ov, col_rsi = st.columns([1, 1])
        with col_ov:
            if buy_cnt > sell_cnt:
                st.success(f"**종합 판단: 매수 우세** ({buy_cnt}/{total} 지표 매수)")
            elif sell_cnt > buy_cnt:
                st.error(f"**종합 판단: 매도 우세** ({sell_cnt}/{total} 지표 매도)")
            else:
                st.info(f"**종합 판단: 중립** ({total}개 지표 혼재)")

            for name, (label, icon, _) in signals.items():
                color = "#eafaf1" if "매수" in label or "과매도" in label or "반등" in label else \
                        "#fdedec" if "매도" in label or "과매수" in label or "과열" in label else "#f5f5f5"
                st.markdown(f"""<div class="signal-card" style="background:{color}">
                    <span style="font-size:13px">{icon} <b>{name}</b></span>
                    <span style="font-size:12px;color:#555">{label}</span>
                </div>""", unsafe_allow_html=True)

        with col_rsi:
            fig_rsi = go.Figure(go.Indicator(
                mode="gauge+number",
                value=rsi_val,
                title={"text": "RSI (14일)"},
                gauge={
                    "axis": {"range": [0, 100]},
                    "bar": {"color": "#3498db"},
                    "steps": [
                        {"range": [0, 30], "color": "#eafaf1"},
                        {"range": [30, 70], "color": "#fdfefe"},
                        {"range": [70, 100], "color": "#fdedec"},
                    ],
                    "threshold": {"line": {"color": "red", "width": 2}, "value": 70}
                }
            ))
            fig_rsi.update_layout(height=280, margin=dict(l=20,r=20,t=40,b=20))
            st.plotly_chart(fig_rsi, use_container_width=True)
            if rsi_val < 30:
                st.success("과매도 구간 — 반등 가능성")
            elif rsi_val > 70:
                st.error("과매수 구간 — 조정 주의")
            else:
                st.info("중립 구간")
    else:
        st.warning("데이터가 부족합니다.")

# ─── 탭 4: 뉴스 & 감성 ──────────────────────────────────
with tabs[3]:
    company_name = info.get("longName", ticker)
    articles = get_news(company_name, NEWS_API_KEY)

    if articles:
        pos_n = neg_n = neu_n = 0
        for a in articles:
            title = a.get("title", "") or ""
            desc  = a.get("description", "") or ""
            sent_label, sent_icon, sent_cls, sent_col = sentiment(title + " " + desc)
            if "긍정" in sent_label: pos_n += 1
            elif "부정" in sent_label: neg_n += 1
            else: neu_n += 1
            src  = a.get("source", {}).get("name", "")
            url  = a.get("url", "#")
            pub  = a.get("publishedAt", "")[:10]
            st.markdown(f"""<div class="news-card {sent_cls}">
                <div style="font-size:13px;font-weight:500;margin-bottom:3px">{title[:80]}</div>
                <div style="font-size:11px;color:#888">{sent_icon} {sent_label} &nbsp;·&nbsp; {src} &nbsp;·&nbsp; {pub}</div>
            </div>""", unsafe_allow_html=True)
            st.markdown(f"[기사 보기 →]({url})", unsafe_allow_html=False)

        st.divider()
        total_n = pos_n + neg_n + neu_n
        col_s1, col_s2, col_s3 = st.columns(3)
        col_s1.metric("긍정", f"{pos_n}건", f"{pos_n/total_n*100:.0f}%")
        col_s2.metric("중립", f"{neu_n}건", f"{neu_n/total_n*100:.0f}%")
        col_s3.metric("부정", f"{neg_n}건", f"{neg_n/total_n*100:.0f}%")

        fig_sent = go.Figure(go.Pie(
            labels=["긍정", "중립", "부정"],
            values=[pos_n, neu_n, neg_n],
            marker_colors=["#2d8a4e", "#888", "#c0392b"],
            hole=0.5
        ))
        fig_sent.update_layout(height=220, margin=dict(l=0,r=0,t=10,b=0),
                                showlegend=True)
        st.plotly_chart(fig_sent, use_container_width=True)

        # 카카오 알림 (부정 뉴스 급증 시)
        if neg_n >= 3 and kakao_alert and KAKAO_TOKEN:
            msg = f"[뉴스 알림] {ticker} 부정 뉴스 {neg_n}건 감지!\n확인이 필요합니다."
            if send_kakao(KAKAO_TOKEN, msg):
                st.warning(f"카카오톡: 부정 뉴스 급증 알림 전송!")
    else:
        st.info("뉴스 API 키를 설정하면 실시간 뉴스가 표시돼요.\n(사이드바 Secrets → NEWS_API_KEY)")

# ─── 탭 5: 포트폴리오 ────────────────────────────────────
with tabs[4]:
    st.subheader("내 포트폴리오")

    if "portfolio" not in st.session_state:
        st.session_state.portfolio = []

    with st.expander("+ 종목 추가"):
        col_p1, col_p2, col_p3 = st.columns(3)
        p_ticker = col_p1.text_input("티커", placeholder="AAPL")
        p_shares = col_p2.number_input("보유 수량", min_value=0.0, step=0.1)
        p_avg    = col_p3.number_input("평균 매수가 ($)", min_value=0.0, step=0.1)
        if st.button("추가"):
            if p_ticker and p_shares > 0 and p_avg > 0:
                h2, _ = get_stock(p_ticker.upper(), "1d")
                curr2 = h2["Close"].iloc[-1] if h2 is not None and not h2.empty else p_avg
                st.session_state.portfolio.append({
                    "ticker": p_ticker.upper(), "shares": p_shares,
                    "avg": p_avg, "curr": curr2
                })
                st.success(f"{p_ticker.upper()} 추가 완료!")
                st.rerun()

    if st.session_state.portfolio:
        total_val, total_cost, total_gain, total_ret = compute_portfolio_stats(st.session_state.portfolio)
        delta_color = "normal" if total_ret >= 0 else "inverse"

        col_pt1, col_pt2, col_pt3 = st.columns(3)
        col_pt1.metric("총 평가금액", f"${total_val:,.0f}")
        col_pt2.metric("총 투자금액", f"${total_cost:,.0f}")
        col_pt3.metric("총 손익", f"${total_gain:,.0f}", f"{total_ret:+.2f}%", delta_color=delta_color)

        # 종목별 카드
        for i, h in enumerate(st.session_state.portfolio):
            val  = h["shares"] * h["curr"]
            ret  = (h["curr"] - h["avg"]) / h["avg"] * 100
            gain = (h["curr"] - h["avg"]) * h["shares"]
            col_a, col_b, col_c, col_d = st.columns([2, 1, 1, 1])
            col_a.write(f"**{h['ticker']}**")
            col_b.metric("현재가", f"${h['curr']:.2f}")
            col_c.metric("평가금액", f"${val:,.0f}", f"{ret:+.1f}%",
                         delta_color="normal" if ret >= 0 else "inverse")
            if col_d.button("삭제", key=f"del_{i}"):
                st.session_state.portfolio.pop(i)
                st.rerun()

        # 자산 배분 파이차트
        labels = [h["ticker"] for h in st.session_state.portfolio]
        values = [h["shares"] * h["curr"] for h in st.session_state.portfolio]
        col_pie, col_ret = st.columns(2)
        with col_pie:
            fig_pie = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
            fig_pie.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_ret:
            # 종목별 수익률 바차트
            rets = [(h["ticker"], (h["curr"]-h["avg"])/h["avg"]*100) for h in st.session_state.portfolio]
            rets.sort(key=lambda x: x[1])
            fig_bar = go.Figure(go.Bar(
                x=[r[1] for r in rets],
                y=[r[0] for r in rets],
                orientation="h",
                marker_color=["#2d8a4e" if r[1] >= 0 else "#c0392b" for r in rets]
            ))
            fig_bar.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                                   xaxis_title="수익률 (%)",
                                   paper_bgcolor="rgba(0,0,0,0)",
                                   plot_bgcolor="rgba(0,0,0,0)")
            st.plotly_chart(fig_bar, use_container_width=True)

        # 리밸런싱 계산기
        st.subheader("리밸런싱 계산기")
        st.caption("목표 비중을 입력하면 매수/매도 수량을 자동 계산해드려요.")
        rebal_cols = st.columns(len(st.session_state.portfolio))
        targets = []
        for i, (h, col) in enumerate(zip(st.session_state.portfolio, rebal_cols)):
            t = col.number_input(f"{h['ticker']} (%)", 0, 100,
                                 int(100 / len(st.session_state.portfolio)), key=f"rb_{i}")
            targets.append(t)

        if sum(targets) == 100:
            st.success("**리밸런싱 제안:**")
            for h, tgt in zip(st.session_state.portfolio, targets):
                curr_w = (h["shares"] * h["curr"]) / total_val * 100
                diff   = tgt - curr_w
                action = "매수" if diff > 0 else "매도"
                amt    = abs(diff / 100 * total_val)
                shares_needed = amt / h["curr"]
                col_r1, col_r2 = st.columns(2)
                col_r1.write(f"**{h['ticker']}**: 현재 {curr_w:.1f}% → 목표 {tgt}%")
                col_r2.write(f"→ {action} {shares_needed:.2f}주 (${amt:,.0f})")
        elif sum(targets) != 0:
            st.warning(f"비중 합계가 {sum(targets)}%예요. 100%로 맞춰주세요.")
    else:
        st.info("종목을 추가해서 포트폴리오를 관리해보세요!")

# ─── 탭 6: 주가 예측 ────────────────────────────────────
with tabs[5]:
    st.subheader("주가 예측 (Prophet)")
    st.caption("Facebook이 만든 시계열 예측 모델로 추세를 예측해요.")

    pred_days = st.slider("예측 기간 (일)", 7, 90, 30)

    if st.button("예측 시작", type="primary"):
        with st.spinner("모델 학습 중... (약 10~20초)"):
            df_p, fc = run_prophet(hist, pred_days)

        if fc is not None:
            pred_price  = fc["yhat"].iloc[-1]
            pred_upper  = fc["yhat_upper"].iloc[-1]
            pred_lower  = fc["yhat_lower"].iloc[-1]
            upside      = (pred_price - curr_price) / curr_price * 100

            col_pr1, col_pr2, col_pr3 = st.columns(3)
            col_pr1.metric(f"{pred_days}일 후 예측가", f"${pred_price:.2f}", f"{upside:+.1f}%",
                           delta_color="normal" if upside > 0 else "inverse")
            col_pr2.metric("예측 상단", f"${pred_upper:.2f}")
            col_pr3.metric("예측 하단", f"${pred_lower:.2f}")

            fig_pred = go.Figure()
            fig_pred.add_trace(go.Scatter(
                x=df_p["ds"], y=df_p["y"], name="실제 주가",
                line=dict(color="#3498db", width=1.5)
            ))
            fig_pred.add_trace(go.Scatter(
                x=fc["ds"], y=fc["yhat"], name="예측",
                line=dict(color="#e74c3c", width=1.5, dash="dash")
            ))
            # 신뢰구간 음영
            fig_pred.add_trace(go.Scatter(
                x=pd.concat([fc["ds"], fc["ds"][::-1]]),
                y=pd.concat([fc["yhat_upper"], fc["yhat_lower"][::-1]]),
                fill="toself", fillcolor="rgba(231,76,60,0.1)",
                line=dict(color="rgba(0,0,0,0)"), name="신뢰구간"
            ))
            fig_pred.update_layout(
                height=400, margin=dict(l=0,r=0,t=10,b=0),
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#f0f0f0"),
                legend=dict(orientation="h", y=1.05)
            )
            st.plotly_chart(fig_pred, use_container_width=True)

            # 카카오 알림 옵션
            if kakao_alert and KAKAO_TOKEN:
                msg = (f"[예측 알림] {ticker}\n"
                       f"{pred_days}일 후 예측가: ${pred_price:.2f} ({upside:+.1f}%)\n"
                       f"범위: ${pred_lower:.2f} ~ ${pred_upper:.2f}")
                if send_kakao(KAKAO_TOKEN, msg):
                    st.success("예측 결과를 카카오톡으로 전송했어요!")

            st.warning("⚠ 이 예측은 과거 데이터 기반의 참고용입니다. 실제 투자 결과와 다를 수 있어요.")

# ─── 탭 7: AI 포트폴리오 추천 ───────────────────────────
with tabs[6]:
    st.subheader("AI 포트폴리오 추천")
    st.caption("투자 성향을 입력하면 Claude AI가 맞춤 포트폴리오를 추천해드려요.")

    if not ANTHROPIC_API_KEY:
        st.warning("Claude API 키가 설정되지 않았어요. Secrets에 ANTHROPIC_API_KEY를 추가해주세요.")
        st.code('ANTHROPIC_API_KEY = "sk-ant-..."', language="toml")

    col_ai1, col_ai2 = st.columns(2)
    with col_ai1:
        risk = st.selectbox("투자 성향", ["안정형 (저위험)", "중립형 (중위험)", "공격형 (고위험)"])
        amount = st.number_input("투자 금액 ($)", min_value=1000, value=10000, step=1000)
    with col_ai2:
        sectors = st.multiselect(
            "관심 섹터",
            ["기술 (Tech)", "반도체", "AI/클라우드", "전기차/에너지", "헬스케어",
             "금융", "소비재", "배당주", "ETF"],
            default=["기술 (Tech)", "AI/클라우드"]
        )

    if st.button("AI 추천 받기", type="primary", disabled=not ANTHROPIC_API_KEY):
        with st.spinner("Claude AI가 포트폴리오를 분석 중... (약 10~15초)"):
            result = ai_portfolio_recommend(risk, amount, sectors, ANTHROPIC_API_KEY)

        if result:
            st.success(f"**{result.get('summary', '')}**")
            st.markdown(f"_{result.get('strategy', '')}_")
            st.divider()

            stocks = result.get("stocks", [])
            for s in stocks:
                w = s.get("weight", 0)
                alloc = amount * w / 100
                shares_est = alloc / curr_price

                col_s1, col_s2, col_s3 = st.columns([2, 1, 2])
                col_s1.markdown(f"**{s.get('ticker')}** — {s.get('name')}")
                col_s2.metric("비중", f"{w}%", f"${alloc:,.0f}")
                col_s3.caption(s.get("reason", ""))
                st.progress(w)

            # 파이차트
            fig_ai = go.Figure(go.Pie(
                labels=[s["ticker"] for s in stocks],
                values=[s["weight"] for s in stocks],
                hole=0.4,
                textinfo="label+percent"
            ))
            fig_ai.update_layout(height=320, margin=dict(l=0,r=0,t=10,b=0))
            st.plotly_chart(fig_ai, use_container_width=True)

            # 카카오 알림
            if kakao_alert and KAKAO_TOKEN:
                msg_stocks = "\n".join([f"• {s['ticker']} {s['weight']}%" for s in stocks])
                msg = f"[AI 추천] {risk} 포트폴리오\n{msg_stocks}\n총 투자: ${amount:,}"
                if send_kakao(KAKAO_TOKEN, msg):
                    st.success("포트폴리오 추천을 카카오톡으로 전송했어요!")

            st.warning("⚠ AI 추천은 참고용이며 투자 조언이 아닙니다. 최종 판단은 본인이 해주세요.")
        else:
            st.error("AI 추천 생성 실패. API 키를 확인하거나 잠시 후 다시 시도해주세요.")

# ─── 탭 8: 카카오 알림 설정 ─────────────────────────────
with tabs[7]:
    st.subheader("카카오톡 알림 설정")

    st.markdown("""
**카카오톡 알림 발급 방법 (5분 소요)**

1. [developers.kakao.com](https://developers.kakao.com) → 로그인 → 내 애플리케이션
2. 앱 만들기 → 앱 이름 입력 → 저장
3. 왼쪽 메뉴 **카카오 로그인** → 활성화 ON
4. **Redirect URI** 설정: `https://example.com` (임시)
5. 도구 → **토큰 발급** → 내 카카오 계정으로 로그인
6. 발급된 **액세스 토큰** 복사
7. Streamlit Cloud → Settings → Secrets → `KAKAO_ACCESS_TOKEN = "토큰값"` 입력
""")

    st.divider()
    st.subheader("알림 테스트")
    test_msg = st.text_area("테스트 메시지", value=f"[주식 알림 테스트]\n{ticker} 현재가: ${curr_price:.2f}")

    if st.button("카카오톡 테스트 전송"):
        if not KAKAO_TOKEN:
            st.error("Secrets에 KAKAO_ACCESS_TOKEN이 설정되지 않았어요.")
        else:
            with st.spinner("전송 중..."):
                ok = send_kakao(KAKAO_TOKEN, test_msg)
            if ok:
                st.success("전송 성공! 카카오톡을 확인하세요.")
            else:
                st.error("전송 실패. 토큰이 만료됐을 수 있어요. 재발급 후 다시 시도해주세요.")

    st.divider()
    st.subheader("자동 알림 조건 현황")
    conditions = [
        ("목표가 도달", f"${alert_high:.0f}" if alert_high > 0 else "미설정", alert_high > 0),
        ("하한가 도달", f"${alert_low:.0f}" if alert_low > 0 else "미설정", alert_low > 0),
        ("부정 뉴스 급증", "3건 이상 감지 시", True),
        ("예측 결과 수신", "예측 실행 시", True),
        ("AI 추천 결과", "추천 실행 시", True),
    ]
    for name, val, active in conditions:
        col1, col2, col3 = st.columns([2, 2, 1])
        col1.write(name)
        col2.write(val)
        col3.write("✅ 활성" if (active and kakao_alert) else "⬜ 비활성")

st.divider()
st.caption(f"데이터 출처: Yahoo Finance, NewsAPI · Claude AI 분석 포함 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
