import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import requests
import json
from datetime import datetime

st.set_page_config(
    page_title="대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* ── 기본 레이아웃 ── */
    .block-container { padding: 0.8rem 1rem 2rem; max-width: 1200px; }
    .stTabs [data-baseweb="tab"] { font-size: 13px; padding: 8px 12px; }

    /* ── 카드 공통 ── */
    .signal-card {
        background: #f8f9fa; border-radius: 10px;
        padding: 10px 14px; margin-bottom: 6px;
        display: flex; justify-content: space-between; align-items: center;
    }
    .news-card { border-left: 3px solid #ddd; padding: 8px 12px; margin-bottom: 8px; border-radius: 0 8px 8px 0; }
    .news-pos { border-left-color: #2d8a4e; }
    .news-neg { border-left-color: #c0392b; }

    /* ── TOP100 종목 카드 (모바일 전용) ── */
    .stock-card {
        background: #fff;
        border: 1px solid #f0f0f0;
        border-radius: 12px;
        padding: 12px 14px;
        margin-bottom: 8px;
        cursor: pointer;
        transition: box-shadow .15s;
    }
    .stock-card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
    .stock-card-top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px; }
    .stock-card-bottom { display: flex; justify-content: space-between; align-items: center; }
    .stock-ticker { font-size: 15px; font-weight: 700; }
    .stock-name { font-size: 12px; color: #888; margin-top: 1px; }
    .stock-price { font-size: 15px; font-weight: 600; text-align: right; }
    .stock-chg { font-size: 13px; font-weight: 500; text-align: right; }
    .stock-meta { font-size: 11px; color: #aaa; }
    .sector-badge { font-size: 10px; padding: 2px 7px; border-radius: 8px; }

    /* ── 타임프레임 컨트롤 소형화 ── */
    .tf-bar button {
        padding: 2px 8px !important;
        font-size: 12px !important;
        min-height: 28px !important;
        height: 28px !important;
        line-height: 1 !important;
    }
    .tf-bar [data-baseweb="select"] > div {
        min-height: 28px !important;
        font-size: 12px !important;
        padding-top: 0 !important;
        padding-bottom: 0 !important;
    }

    /* ── 모바일 반응형 ── */
    @media (max-width: 768px) {
        .block-container { padding: 0.5rem 0.5rem 2rem !important; }
        .stTabs [data-baseweb="tab"] { font-size: 11px !important; padding: 6px 8px !important; }
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 1.1rem !important; }
        /* 메트릭 카드 작게 */
        [data-testid="metric-container"] { padding: 8px !important; }
        [data-testid="metric-container"] label { font-size: 11px !important; }
        [data-testid="metric-container"] [data-testid="stMetricValue"] { font-size: 16px !important; }
        /* 사이드바 숨김 */
        [data-testid="stSidebar"] { display: none; }
        /* 버튼 풀width */
        .stButton button { width: 100%; font-size: 13px !important; }
        /* 분석 버튼 소형화 */
        [data-testid="stHorizontalBlock"] .stButton button {
            padding: 4px 6px !important;
            font-size: 12px !important;
            min-height: 32px !important;
        }
    }
</style>
""", unsafe_allow_html=True)

NEWS_API_KEY      = st.secrets.get("NEWS_API_KEY", "")
KAKAO_TOKEN       = st.secrets.get("KAKAO_ACCESS_TOKEN", "")
ANTHROPIC_API_KEY = st.secrets.get("ANTHROPIC_API_KEY", "")

# ── 종목 100개 ──────────────────────────────────────────
TOP100 = [
    ("AAPL","Apple","빅테크"),("NVDA","NVIDIA","반도체"),("MSFT","Microsoft","빅테크"),
    ("AMZN","Amazon","빅테크"),("GOOGL","Alphabet","빅테크"),("META","Meta","빅테크"),
    ("TSLA","Tesla","전기차"),("AVGO","Broadcom","반도체"),("TSM","TSMC","반도체"),
    ("NFLX","Netflix","빅테크"),("AMD","AMD","반도체"),("ORCL","Oracle","빅테크"),
    ("ASML","ASML","반도체"),("COST","Costco","소비재"),("QCOM","Qualcomm","반도체"),
    ("AMAT","Applied Materials","반도체"),("TXN","Texas Instruments","반도체"),
    ("INTU","Intuit","빅테크"),("AMGN","Amgen","헬스케어"),("MU","Micron","반도체"),
    ("HON","Honeywell","산업"),("INTC","Intel","반도체"),("LRCX","Lam Research","반도체"),
    ("KLAC","KLA Corp","반도체"),("MRVL","Marvell","반도체"),("CDNS","Cadence","반도체"),
    ("SNPS","Synopsys","반도체"),("PANW","Palo Alto Networks","AI/클라우드"),
    ("CRWD","CrowdStrike","AI/클라우드"),("ABNB","Airbnb","소비재"),
    ("DDOG","Datadog","AI/클라우드"),("SNOW","Snowflake","AI/클라우드"),
    ("TEAM","Atlassian","빅테크"),("ZS","Zscaler","AI/클라우드"),
    ("JPM","JPMorgan","금융"),("BAC","Bank of America","금융"),
    ("GS","Goldman Sachs","금융"),("MS","Morgan Stanley","금융"),
    ("V","Visa","금융"),("MA","Mastercard","금융"),("BRK-B","Berkshire B","금융"),
    ("WFC","Wells Fargo","금융"),("SCHW","Charles Schwab","금융"),
    ("AXP","American Express","금융"),("BLK","BlackRock","금융"),
    ("SPGI","S&P Global","금융"),("UNH","UnitedHealth","헬스케어"),
    ("JNJ","Johnson & Johnson","헬스케어"),("LLY","Eli Lilly","헬스케어"),
    ("PFE","Pfizer","헬스케어"),("ABBV","AbbVie","헬스케어"),
    ("MRK","Merck","헬스케어"),("TMO","Thermo Fisher","헬스케어"),
    ("DHR","Danaher","헬스케어"),("ISRG","Intuitive Surgical","헬스케어"),
    ("BSX","Boston Scientific","헬스케어"),("REGN","Regeneron","헬스케어"),
    ("GILD","Gilead","헬스케어"),("WMT","Walmart","소비재"),
    ("HD","Home Depot","소비재"),("MCD","McDonald's","소비재"),
    ("NKE","Nike","소비재"),("SBUX","Starbucks","소비재"),
    ("LOW","Lowe's","소비재"),("TGT","Target","소비재"),
    ("BKNG","Booking Holdings","소비재"),("MAR","Marriott","소비재"),
    ("CMG","Chipotle","소비재"),("XOM","Exxon Mobil","에너지"),
    ("CVX","Chevron","에너지"),("COP","ConocoPhillips","에너지"),
    ("SLB","Schlumberger","에너지"),("NEE","NextEra Energy","에너지"),
    ("DUK","Duke Energy","에너지"),("SO","Southern Company","에너지"),
    ("GE","GE Aerospace","산업"),("CAT","Caterpillar","산업"),
    ("BA","Boeing","산업"),("RTX","RTX Corp","산업"),
    ("LMT","Lockheed Martin","산업"),("UPS","UPS","산업"),
    ("FDX","FedEx","산업"),("DE","John Deere","산업"),
    ("MMM","3M","산업"),("UBER","Uber","성장주"),
    ("LYFT","Lyft","성장주"),("COIN","Coinbase","성장주"),
    ("MSTR","MicroStrategy","성장주"),("PLTR","Palantir","성장주"),
    ("ARM","ARM Holdings","반도체"),("SMCI","Super Micro","반도체"),
    ("DELL","Dell","빅테크"),("CRM","Salesforce","빅테크"),
    ("NOW","ServiceNow","빅테크"),("ADBE","Adobe","빅테크"),
    ("SHOP","Shopify","성장주"),("SQ","Block","금융"),
    ("PYPL","PayPal","금융"),("SPOT","Spotify","성장주"),
    ("LIN","Linde","산업"),("HOG","Harley-Davidson","소비재"),
]

POPULAR_STOCKS = {f"{t} - {n}": t for t, n, s in TOP100}

SECTOR_MAP = {}
for ticker, name, sector in TOP100:
    SECTOR_MAP.setdefault(sector, []).append(ticker)

SECTOR_COLORS = {
    "빅테크": "#3498db", "반도체": "#9b59b6", "AI/클라우드": "#1abc9c",
    "금융": "#f39c12", "헬스케어": "#2ecc71", "소비재": "#e67e22",
    "에너지": "#e74c3c", "산업": "#95a5a6", "전기차": "#1abc9c", "성장주": "#e91e8c",
}

# ── 세션 상태 ────────────────────────────────────────────
if "selected_ticker" not in st.session_state:
    st.session_state.selected_ticker = "AAPL"
if "active_main_tab" not in st.session_state:
    st.session_state.active_main_tab = 0
if "go_to_detail" not in st.session_state:
    st.session_state.go_to_detail = False
if "detail_selectbox_key" not in st.session_state:
    st.session_state.detail_selectbox_key = 0
if "portfolio" not in st.session_state:
    st.session_state.portfolio = []

# ── 데이터 함수 ──────────────────────────────────────────
@st.cache_data(ttl=300)
def get_stock(ticker, period="1y"):
    try:
        s = yf.Ticker(ticker)
        hist = s.history(period=period)
        if hist is None or hist.empty:
            hist = s.history(period="6mo")
        try:
            info = s.info or {}
        except Exception:
            info = {}
        # info가 비어있으면 fast_info로 보완
        if not info.get("regularMarketPrice") and not info.get("currentPrice"):
            try:
                fi = s.fast_info
                info["regularMarketPrice"] = getattr(fi, "last_price", None)
                info["marketCap"]          = getattr(fi, "market_cap", None)
                info["fiftyTwoWeekHigh"]   = getattr(fi, "year_high", None)
                info["fiftyTwoWeekLow"]    = getattr(fi, "year_low", None)
            except Exception:
                pass
        return hist, info
    except Exception:
        return None, {}

# 분봉/시봉/일봉 통합 데이터 함수
# interval: 1m,5m,15m,60m,240m -> period 자동 매핑
INTERVAL_CONFIG = {
    "1분":   {"interval":"1m",  "period":"1d",  "dtfmt":"%H:%M",       "label":"1분봉"},
    "5분":   {"interval":"5m",  "period":"5d",  "dtfmt":"%m/%d %H:%M", "label":"5분봉"},
    "10분":  {"interval":"15m", "period":"5d",  "dtfmt":"%m/%d %H:%M", "label":"15분봉"},
    "60분":  {"interval":"60m", "period":"1mo", "dtfmt":"%m/%d %H:%M", "label":"60분봉"},
    "240분": {"interval":"60m", "period":"3mo", "dtfmt":"%m/%d",       "label":"4시간봉"},
    "일":    {"interval":"1d",  "period":"1y",  "dtfmt":"%Y/%m/%d",    "label":"일봉"},
    "주":    {"interval":"1wk", "period":"5y",  "dtfmt":"%Y/%m/%d",    "label":"주봉"},
    "월":    {"interval":"1mo", "period":"10y", "dtfmt":"%Y/%m",       "label":"월봉"},
    "년":    {"interval":"3mo", "period":"max", "dtfmt":"%Y",          "label":"분기봉"},
}

@st.cache_data(ttl=120)
def get_chart_data(ticker, timeframe):
    cfg = INTERVAL_CONFIG.get(timeframe, INTERVAL_CONFIG["일"])
    try:
        s = yf.Ticker(ticker)
        hist = s.history(period=cfg["period"], interval=cfg["interval"])
        if hist.index.tz is not None:
            hist.index = hist.index.tz_convert("America/New_York")
        return hist
    except:
        return None

@st.cache_data(ttl=600)
def get_rank_data(tickers):
    rows = []
    for ticker, name, sector in tickers:
        try:
            s = yf.Ticker(ticker)
            info = s.fast_info
            hist = s.history(period="2d")
            if hist is None or len(hist) < 2:
                continue
            curr = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            chg  = (curr - prev) / prev * 100
            vol  = hist["Volume"].iloc[-1]
            mktcap = getattr(info, "market_cap", 0) or 0
            rows.append({
                "ticker": ticker, "name": name, "sector": sector,
                "price": curr, "change_pct": chg,
                "volume": vol, "mktcap": mktcap,
                "turnover": curr * vol,
            })
        except:
            pass
    return pd.DataFrame(rows)

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
    if p > n: return "긍정", "🟢", "news-pos"
    if n > p: return "부정", "🔴", "news-neg"
    return "중립", "⚪", "news-neu"

def compute_signals(hist):
    close = hist["Close"]
    signals = {}
    if len(close) >= 50:
        ma20 = close.rolling(20).mean()
        ma50 = close.rolling(50).mean()
        signals["이동평균 MA20/50"] = ("매수","🟢") if ma20.iloc[-1] > ma50.iloc[-1] else ("매도","🔴")
        if len(close) >= 200:
            ma200 = close.rolling(200).mean()
            if ma20.iloc[-1] > ma200.iloc[-1]:
                signals["골든크로스"] = ("매수","🟢")
            else:
                signals["데드크로스"] = ("매도","🔴")
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = 100 - (100 / (1 + gain / loss))
    rsi_val = round(rsi.iloc[-1], 1)
    if rsi_val < 30: signals[f"RSI ({rsi_val})"] = ("과매도—매수","🟢")
    elif rsi_val > 70: signals[f"RSI ({rsi_val})"] = ("과매수—매도","🔴")
    else: signals[f"RSI ({rsi_val})"] = ("중립","⚪")
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd = ema12 - ema26
    sig  = macd.ewm(span=9).mean()
    signals["MACD"] = ("매수","🟢") if macd.iloc[-1] > sig.iloc[-1] else ("매도","🔴")
    std = close.rolling(20).std()
    ma20b = close.rolling(20).mean()
    if close.iloc[-1] < (ma20b - 2*std).iloc[-1]: signals["볼린저밴드"] = ("하단이탈—반등","🟢")
    elif close.iloc[-1] > (ma20b + 2*std).iloc[-1]: signals["볼린저밴드"] = ("상단돌파—과열","🔴")
    else: signals["볼린저밴드"] = ("밴드내","⚪")
    return signals, rsi_val

def compute_ai_score(hist, info):
    """기술적 지표 + 재무 데이터 종합해 0~100 점수 산출"""
    score = 50  # 기본 중립
    details = []
    close = hist["Close"]

    # 이동평균 (20점)
    if len(close) >= 50:
        ma20 = close.rolling(20).mean().iloc[-1]
        ma50 = close.rolling(50).mean().iloc[-1]
        if ma20 > ma50:
            score += 10; details.append(("MA20>MA50", "+10", "🟢"))
        else:
            score -= 10; details.append(("MA20<MA50", "-10", "🔴"))

    # RSI (20점)
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rsi = (100 - (100 / (1 + gain / loss))).iloc[-1]
    if rsi < 30:
        score += 15; details.append((f"RSI {rsi:.0f} 과매도", "+15", "🟢"))
    elif rsi < 50:
        score += 5;  details.append((f"RSI {rsi:.0f} 중립↑", "+5", "🟡"))
    elif rsi < 70:
        score -= 5;  details.append((f"RSI {rsi:.0f} 중립↓", "-5", "🟡"))
    else:
        score -= 15; details.append((f"RSI {rsi:.0f} 과매수", "-15", "🔴"))

    # MACD (15점)
    ema12 = close.ewm(span=12).mean()
    ema26 = close.ewm(span=26).mean()
    macd  = (ema12 - ema26).iloc[-1]
    sig   = (ema12 - ema26).ewm(span=9).mean().iloc[-1]
    if macd > sig:
        score += 10; details.append(("MACD 상향 교차", "+10", "🟢"))
    else:
        score -= 10; details.append(("MACD 하향 교차", "-10", "🔴"))

    # 볼린저밴드 (10점)
    ma20b = close.rolling(20).mean()
    std   = close.rolling(20).std()
    curr  = close.iloc[-1]
    if curr < (ma20b - 2*std).iloc[-1]:
        score += 8;  details.append(("BB 하단 이탈", "+8", "🟢"))
    elif curr > (ma20b + 2*std).iloc[-1]:
        score -= 8;  details.append(("BB 상단 돌파", "-8", "🔴"))
    else:
        details.append(("BB 밴드 내 위치", "0", "⚪"))

    # 52주 위치 (10점)
    h52 = info.get("fiftyTwoWeekHigh", curr)
    l52 = info.get("fiftyTwoWeekLow",  curr)
    if h52 > l52:
        pos = (curr - l52) / (h52 - l52) * 100
        if pos < 30:
            score += 8;  details.append((f"52주 하단권 {pos:.0f}%", "+8", "🟢"))
        elif pos > 80:
            score -= 5;  details.append((f"52주 상단권 {pos:.0f}%", "-5", "🔴"))
        else:
            details.append((f"52주 중간권 {pos:.0f}%", "0", "⚪"))

    # PER (5점)
    per = info.get("trailingPE")
    if per:
        if per < 15:
            score += 5;  details.append((f"PER {per:.1f} 저평가", "+5", "🟢"))
        elif per > 40:
            score -= 5;  details.append((f"PER {per:.1f} 고평가", "-5", "🔴"))
        else:
            details.append((f"PER {per:.1f} 적정", "0", "⚪"))

    score = max(0, min(100, score))
    if score >= 70:   grade, grade_col = "강한 매수 신호", "#2d8a4e"
    elif score >= 55: grade, grade_col = "약한 매수 신호", "#5dade2"
    elif score >= 45: grade, grade_col = "중립", "#888"
    elif score >= 30: grade, grade_col = "약한 매도 신호", "#e67e22"
    else:             grade, grade_col = "강한 매도 신호", "#c0392b"

    return score, grade, grade_col, details, rsi

def send_kakao(token, message):
    if not token: return False
    try:
        r = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers={"Authorization": f"Bearer {token}"},
            data={"template_object": json.dumps({
                "object_type": "text", "text": message,
                "link": {"web_url": "https://finance.yahoo.com"}
            })}, timeout=5
        )
        return r.status_code == 200
    except: return False

def run_prediction(hist, days):
    try:
        from sklearn.linear_model import LinearRegression
        from sklearn.preprocessing import PolynomialFeatures
        close = hist["Close"].values
        n = len(close)
        window = min(20, n // 5)
        smoothed = pd.Series(close).rolling(window, min_periods=1).mean().values
        X = np.arange(n).reshape(-1, 1)
        poly = PolynomialFeatures(degree=2)
        X_poly = poly.fit_transform(X)
        model = LinearRegression()
        model.fit(X_poly, smoothed)
        X_future = np.arange(n + days).reshape(-1, 1)
        y_pred = model.predict(poly.transform(X_future))
        residuals = smoothed - model.predict(X_poly)
        std = np.std(residuals)
        last_date = pd.to_datetime(hist.index[-1]).tz_localize(None)
        future_dates = pd.date_range(start=last_date, periods=n + days)
        df_hist = pd.DataFrame({"ds": pd.to_datetime(hist.index).tz_localize(None), "y": close})
        fc = pd.DataFrame({
            "ds": future_dates, "yhat": y_pred,
            "yhat_upper": y_pred + 1.96*std, "yhat_lower": y_pred - 1.96*std,
        })
        return df_hist, fc
    except Exception as e:
        st.error(f"예측 오류: {e}")
        return None, None

RULE_PORTFOLIO = {
    "안정형 (저위험)": {
        "summary": "배당주·대형주 중심의 안정적 포트폴리오",
        "strategy": "변동성이 낮고 배당수익률이 높은 종목 위주로 구성했어요. 경기 방어적 섹터 비중을 높였어요.",
        "stocks": [
            {"ticker":"JPM","name":"JPMorgan","weight":20,"reason":"배당 안정적, 미국 최대 은행"},
            {"ticker":"V","name":"Visa","weight":15,"reason":"글로벌 결제 인프라 독점"},
            {"ticker":"JNJ","name":"J&J","weight":15,"reason":"배당왕, 방어적 헬스케어"},
            {"ticker":"WMT","name":"Walmart","weight":15,"reason":"경기 무관 필수소비재"},
            {"ticker":"LMT","name":"Lockheed Martin","weight":15,"reason":"방산 안정 수익"},
            {"ticker":"COST","name":"Costco","weight":10,"reason":"회원제 고충성도"},
            {"ticker":"UNH","name":"UnitedHealth","weight":10,"reason":"미국 최대 건강보험"},
        ]
    },
    "중립형 (중위험)": {
        "summary": "성장성과 안정성을 균형있게 갖춘 포트폴리오",
        "strategy": "빅테크와 반도체 성장주를 핵심으로, 금융·헬스케어로 리스크를 분산했어요.",
        "stocks": [
            {"ticker":"AAPL","name":"Apple","weight":20,"reason":"생태계 독점, 안정 성장"},
            {"ticker":"MSFT","name":"Microsoft","weight":20,"reason":"클라우드·AI 1위"},
            {"ticker":"NVDA","name":"NVIDIA","weight":20,"reason":"AI 인프라 핵심"},
            {"ticker":"AMD","name":"AMD","weight":10,"reason":"데이터센터 점유율 확대"},
            {"ticker":"V","name":"Visa","weight":15,"reason":"결제 인프라 독점"},
            {"ticker":"LLY","name":"Eli Lilly","weight":15,"reason":"비만치료제 고성장"},
        ]
    },
    "공격형 (고위험)": {
        "summary": "고성장 기술주 중심의 공격적 포트폴리오",
        "strategy": "AI·반도체·성장 플랫폼에 집중 투자해요. 단기 변동성은 크지만 장기 고수익을 추구해요.",
        "stocks": [
            {"ticker":"NVDA","name":"NVIDIA","weight":30,"reason":"AI GPU 시장 90% 점유"},
            {"ticker":"AMD","name":"AMD","weight":15,"reason":"AI 반도체 2위"},
            {"ticker":"TSLA","name":"Tesla","weight":15,"reason":"로보택시·에너지 확장"},
            {"ticker":"PLTR","name":"Palantir","weight":10,"reason":"AI 국방·기업 솔루션"},
            {"ticker":"META","name":"Meta","weight":15,"reason":"AI 광고·메타버스"},
            {"ticker":"GOOGL","name":"Alphabet","weight":15,"reason":"AI 검색·클라우드"},
        ]
    },
}

def ai_portfolio_recommend(risk, amount, sectors, api_key):
    if not api_key:
        return RULE_PORTFOLIO.get(risk, RULE_PORTFOLIO["중립형 (중위험)"])
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={"x-api-key": api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-4-20250514", "max_tokens": 1000,
                  "messages": [{"role": "user", "content":
                      f'미국 주식 전문가로서 포트폴리오 추천. 성향:{risk}, 금액:${amount:,}, 섹터:{",".join(sectors)}. '
                      f'JSON만 반환: {{"summary":"요약","stocks":[{{"ticker":"AAPL","name":"Apple","weight":20,"reason":"이유"}}],"strategy":"전략"}} weight합계100, 5~7종목'}]},
            timeout=30
        )
        text = r.json()["content"][0]["text"].strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)
    except:
        return RULE_PORTFOLIO.get(risk, RULE_PORTFOLIO["중립형 (중위험)"])

def compute_portfolio_stats(holdings):
    total_val  = sum(h["shares"] * h["curr"] for h in holdings)
    total_cost = sum(h["shares"] * h["avg"]  for h in holdings)
    total_gain = total_val - total_cost
    total_ret  = (total_gain / total_cost * 100) if total_cost else 0
    return total_val, total_cost, total_gain, total_ret

# ────────────────────────────────────────────────────────
# 메인 탭 2개
# ────────────────────────────────────────────────────────
st.title("📈 대시보드")

# TOP100에서 종목 클릭 시 탭2 자동 이동 알림
main_tabs = st.tabs(["🏆 거래대금 TOP 100", "🔍 종목 상세 분석"])

# ════════════════════════════════════════════════════════
# 메인 탭 1: 거래대금 TOP 100
# ════════════════════════════════════════════════════════
with main_tabs[0]:
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        sector_filter = st.selectbox("섹터 필터", ["전체"] + sorted(list(set(s for _,_,s in TOP100))))
    with col_f2:
        sort_by = st.selectbox("정렬 기준", ["거래대금", "등락률 (상승)", "등락률 (하락)", "현재가", "시가총액"])
    with col_f3:
        st.markdown("<br>", unsafe_allow_html=True)
        load_btn = st.button("🔄 새로고침", use_container_width=True)

    # 섹터 필터 적용
    if sector_filter == "전체":
        filtered_100 = TOP100
    else:
        filtered_100 = [(t,n,s) for t,n,s in TOP100 if s == sector_filter]

    with st.spinner(f"데이터 불러오는 중... ({len(filtered_100)}개 종목)"):
        df_rank = get_rank_data(tuple(filtered_100))

    if df_rank.empty:
        st.warning("데이터를 불러올 수 없어요. 잠시 후 다시 시도해주세요.")
    else:
        # 정렬
        if sort_by == "거래대금":
            df_rank = df_rank.sort_values("turnover", ascending=False)
        elif sort_by == "등락률 (상승)":
            df_rank = df_rank.sort_values("change_pct", ascending=False)
        elif sort_by == "등락률 (하락)":
            df_rank = df_rank.sort_values("change_pct", ascending=True)
        elif sort_by == "현재가":
            df_rank = df_rank.sort_values("price", ascending=False)
        elif sort_by == "시가총액":
            df_rank = df_rank.sort_values("mktcap", ascending=False)

        df_rank = df_rank.reset_index(drop=True)

        # 요약 지표
        up_cnt   = (df_rank["change_pct"] > 0).sum()
        down_cnt = (df_rank["change_pct"] < 0).sum()
        avg_chg  = df_rank["change_pct"].mean()
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("상승 종목", f"{up_cnt}개")
        m2.metric("하락 종목", f"{down_cnt}개")
        m3.metric("평균 등락률", f"{avg_chg:+.2f}%", delta_color="normal" if avg_chg >= 0 else "inverse")
        m4.metric("조회 종목 수", f"{len(df_rank)}개")

        st.markdown("---")

        # ── 헤더 ──
        hd = st.columns([0.3, 0.8, 1.5, 0.8, 0.9, 0.9, 1.0, 1.0, 0.6])
        for col, label in zip(hd, ["#","티커","종목명","섹터","현재가","등락률","거래대금","시가총액","상세"]):
            col.markdown(f"<p style='font-size:12px;color:#aaa;font-weight:600;margin:0;padding:4px 0'>{label}</p>",
                         unsafe_allow_html=True)
        st.markdown("<hr style='margin:2px 0 8px;border-color:#e8e8e8;border-width:2px'>", unsafe_allow_html=True)

        # ── 종목 행 ──
        for i, row in df_rank.iterrows():
            chg        = row["change_pct"]
            chg_col    = "#2d8a4e" if chg >= 0 else "#c0392b"
            chg_bg     = "#eafaf1" if chg >= 0 else "#fdedec"
            chg_sym    = "▲" if chg >= 0 else "▼"
            turnover_b = row["turnover"] / 1e9
            mktcap_b   = row["mktcap"]  / 1e9 if row["mktcap"] else 0
            sec_col    = SECTOR_COLORS.get(row["sector"], "#888")

            cols = st.columns([0.3, 0.8, 1.5, 0.8, 0.9, 0.9, 1.0, 1.0, 0.6])
            cols[0].markdown(
                f"<p style='font-size:13px;color:#ccc;font-weight:500;margin:0;padding:8px 0'>{i+1}</p>",
                unsafe_allow_html=True)
            cols[1].markdown(
                f"<p style='font-size:15px;font-weight:800;color:#1a1a1a;margin:0;padding:8px 0'>{row['ticker']}</p>",
                unsafe_allow_html=True)
            cols[2].markdown(
                f"<p style='font-size:14px;color:#444;margin:0;padding:8px 0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis'>{row['name']}</p>",
                unsafe_allow_html=True)
            cols[3].markdown(
                f"<div style='padding:8px 0'><span style='font-size:12px;background:{sec_col}18;color:{sec_col};padding:3px 8px;border-radius:8px;font-weight:500'>{row['sector']}</span></div>",
                unsafe_allow_html=True)
            cols[4].markdown(
                f"<p style='font-size:15px;font-weight:700;color:#1a1a1a;margin:0;padding:8px 0'>${row['price']:.2f}</p>",
                unsafe_allow_html=True)
            cols[5].markdown(
                f"<div style='padding:8px 0'><span style='font-size:14px;font-weight:700;color:{chg_col};background:{chg_bg};padding:3px 8px;border-radius:6px'>{chg_sym}{abs(chg):.2f}%</span></div>",
                unsafe_allow_html=True)
            cols[6].markdown(
                f"<p style='font-size:14px;font-weight:500;color:#333;margin:0;padding:8px 0'>${turnover_b:.1f}B</p>",
                unsafe_allow_html=True)
            cols[7].markdown(
                f"<p style='font-size:14px;font-weight:500;color:#333;margin:0;padding:8px 0'>${mktcap_b:.0f}B</p>",
                unsafe_allow_html=True)

            if cols[8].button("분석→", key=f"go_{row['ticker']}", use_container_width=True):
                st.session_state.selected_ticker = row["ticker"]
                st.session_state.detail_selectbox_key = st.session_state.get("detail_selectbox_key", 0) + 1
                st.rerun()

            st.markdown("<hr style='margin:0;border-color:#f0f0f0'>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════
# 메인 탭 2: 종목 상세 분석
# ════════════════════════════════════════════════════════
with main_tabs[1]:
    # TOP100에서 넘어온 경우 안내
    sel_t = st.session_state.get("selected_ticker","AAPL")
    sel_name = next((n for t,n,s in TOP100 if t==sel_t), sel_t)
    st.markdown(f"<div style='background:#e8f4fd;border-radius:8px;padding:8px 14px;margin-bottom:12px;font-size:13px'>"
                f"📊 현재 선택 종목: <b>{sel_t} — {sel_name}</b> &nbsp;|&nbsp; "
                f"<span style='color:#888'>TOP 100 탭에서 종목을 클릭하면 여기서 바로 분석돼요</span></div>",
                unsafe_allow_html=True)

    # 사이드 컨트롤
    ctrl1, ctrl2, ctrl3 = st.columns([2, 1, 1])
    with ctrl1:
        all_options = [f"{t} - {n}" for t,n,s in TOP100]
        default_idx = next((i for i,(t,n,s) in enumerate(TOP100) if t == st.session_state.selected_ticker), 0)
        # key에 counter를 넣어 분석 버튼 클릭 시 selectbox를 강제 재렌더링
        sb_key = f"detail_ticker_{st.session_state.get('detail_selectbox_key', 0)}"
        selected_label = st.selectbox("종목 선택", all_options, index=default_idx, key=sb_key)
        ticker = selected_label.split(" - ")[0]
        st.session_state.selected_ticker = ticker
    with ctrl2:
        kakao_alert = st.toggle("카카오 알림", value=False)
    with ctrl3:
        with st.expander("가격 알림"):
            alert_high = st.number_input("목표가 $", min_value=0.0, value=0.0, step=1.0)
            alert_low  = st.number_input("하한가 $", min_value=0.0, value=0.0, step=1.0)

    # 타임프레임 세션 초기화
    if "timeframe" not in st.session_state:
        st.session_state.timeframe = "일"
    timeframe = st.session_state.timeframe
    period = INTERVAL_CONFIG[timeframe]["period"]

    # 데이터 로드 (일반 + 차트용)
    with st.spinner(f"{ticker} 데이터 불러오는 중..."):
        hist, info = get_stock(ticker, "1y")   # 신호 계산용은 항상 1y
        chart_hist = get_chart_data(ticker, timeframe)  # 차트용

    if hist is None or hist.empty:
        st.error(f"**{ticker}** 데이터를 불러오지 못했어요.")
        st.caption("Yahoo Finance 일시 장애 또는 티커 오류일 수 있어요. 아래 버튼으로 재시도하거나 잠시 후 다시 시도해주세요.")
        if st.button("🔄 다시 시도", type="primary"):
            st.cache_data.clear()
            st.rerun()
        st.stop()

    curr_price = hist["Close"].iloc[-1]
    prev_price = hist["Close"].iloc[-2] if len(hist) >= 2 else curr_price
    change_pct = (curr_price - prev_price) / prev_price * 100 if prev_price else 0

    # 알림 체크
    if alert_high > 0 and curr_price >= alert_high:
        msg = f"[주식 알림] {ticker} 목표가 도달!\n현재가: ${curr_price:.2f}"
        st.warning(msg)
        if kakao_alert and KAKAO_TOKEN:
            send_kakao(KAKAO_TOKEN, msg) and st.success("카카오톡 알림 전송!")

    if alert_low > 0 and curr_price <= alert_low:
        msg = f"[주식 알림] {ticker} 하한가 도달!\n현재가: ${curr_price:.2f}"
        st.error(msg)
        if kakao_alert and KAKAO_TOKEN:
            send_kakao(KAKAO_TOKEN, msg)

    # 상단 지표
    company = info.get("longName", ticker)
    st.subheader(f"{company} ({ticker})")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("현재가", f"${curr_price:.2f}", f"{change_pct:+.2f}%",
              delta_color="normal" if change_pct >= 0 else "inverse")
    m2.metric("시가총액", f"${info.get('marketCap',0)/1e9:.1f}B" if info.get("marketCap") else "N/A")
    m3.metric("52주 최고", f"${info.get('fiftyTwoWeekHigh',0):.2f}" if info.get("fiftyTwoWeekHigh") else "N/A")
    m4.metric("52주 최저", f"${info.get('fiftyTwoWeekLow',0):.2f}" if info.get("fiftyTwoWeekLow") else "N/A")
    m5.metric("배당수익률", f"{info.get('dividendYield',0)*100:.2f}%" if info.get("dividendYield") else "N/A")

    # 상세 탭
    tabs = st.tabs(["📊 차트 & 지표", "📋 재무 분석", "🔔 매매 신호", "📰 뉴스 & 감성",
                    "💼 포트폴리오", "🔮 주가 예측", "🤖 AI 추천", "📱 카카오 알림"])

    # ── 탭 1: 차트 ───────────────────────────────────────
    with tabs[0]:
        col_c, col_s = st.columns([3, 1])
        with col_c:

            # ── 타임프레임 컨트롤 (차트 바로 위) ──
            MIN_TF  = ["1분", "5분", "10분", "60분", "240분"]
            DAY_TF  = ["일", "주", "월", "년"]
            is_min  = st.session_state.timeframe in MIN_TF

            st.markdown('<div class="tf-bar">', unsafe_allow_html=True)
            tf_cols = st.columns([1.3, 0.7, 0.7, 0.7, 0.7])

            with tf_cols[0]:
                cur_min_idx = MIN_TF.index(st.session_state.timeframe) if is_min else 0
                sel_min = st.selectbox(
                    "분봉 선택",
                    MIN_TF,
                    index=cur_min_idx,
                    key="min_tf_sel",
                    label_visibility="collapsed"
                )
                # 분봉 모드일 때: 드롭다운 값 변경 → 즉시 반영
                # 분봉 모드 아닐 때: 드롭다운을 클릭(값이 0번이 아닌 것 선택, 또는 버튼처럼 사용)
                # → 분봉 드롭다운 아래 작은 "분봉 전환" 버튼 제공
                if is_min and sel_min != st.session_state.timeframe:
                    st.session_state.timeframe = sel_min
                    st.rerun()
                if not is_min:
                    if st.button(f"▶ {sel_min} 적용", key="apply_min_tf",
                                 use_container_width=True):
                        st.session_state.timeframe = sel_min
                        st.rerun()

            for i, tf in enumerate(DAY_TF):
                with tf_cols[i + 1]:
                    is_active = st.session_state.timeframe == tf
                    if st.button(tf, key=f"tf_{tf}", use_container_width=True,
                                 type="primary" if is_active else "secondary"):
                        st.session_state.timeframe = tf
                        st.rerun()

            st.markdown('</div>', unsafe_allow_html=True)
            timeframe = st.session_state.timeframe
            cfg = INTERVAL_CONFIG[timeframe]

            if chart_hist is None or chart_hist.empty:
                st.warning("차트 데이터를 불러올 수 없어요.")
            else:
                ch = chart_hist.copy()
                # x축 레이블 포맷
                x_labels = ch.index.strftime(cfg["dtfmt"])

                # 캔들 차트
                fig = go.Figure()
                fig.add_trace(go.Candlestick(
                    x=ch.index, open=ch["Open"], high=ch["High"],
                    low=ch["Low"], close=ch["Close"], name=ticker,
                    increasing_line_color="#2d8a4e", decreasing_line_color="#c0392b"
                ))
                # MA는 일봉 이상에서만
                if timeframe in ["일","주","월","년"]:
                    ma20c = ch["Close"].rolling(20).mean()
                    ma50c = ch["Close"].rolling(50).mean()
                    fig.add_trace(go.Scatter(x=ch.index, y=ma20c, name="MA20",
                                            line=dict(color="#3498db", width=1.2)))
                    fig.add_trace(go.Scatter(x=ch.index, y=ma50c, name="MA50",
                                            line=dict(color="#e67e22", width=1.2, dash="dot")))
                    std_c = ch["Close"].rolling(20).std()
                    fig.add_trace(go.Scatter(x=ch.index, y=ma20c+2*std_c, name="BB상단",
                                            line=dict(color="gray", width=0.8, dash="dash")))
                    fig.add_trace(go.Scatter(x=ch.index, y=ma20c-2*std_c, name="BB하단",
                                            line=dict(color="gray", width=0.8, dash="dash"),
                                            fill="tonexty", fillcolor="rgba(128,128,128,0.05)"))

                # x축 타입 설정 (분봉은 category로)
                xaxis_cfg = dict(showgrid=False)
                if timeframe in ["1분","5분","10분","60분","240분"]:
                    xaxis_cfg["type"] = "category"
                    xaxis_cfg["ticktext"] = x_labels
                    xaxis_cfg["tickvals"] = list(range(len(ch)))
                    xaxis_cfg["tickangle"] = -30
                    xaxis_cfg["nticks"] = 10

                fig.update_layout(
                    xaxis_rangeslider_visible=False, height=420,
                    margin=dict(l=0,r=0,t=10,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=xaxis_cfg, yaxis=dict(gridcolor="#f0f0f0"),
                    legend=dict(orientation="h", y=1.05),
                    title=dict(text=f"{ticker} · {cfg['label']}", font=dict(size=13), x=0)
                )
                st.plotly_chart(fig, use_container_width=True)

                # 거래량
                vol_colors = ["#2d8a4e" if c>=o else "#c0392b"
                              for c,o in zip(ch["Close"], ch["Open"])]
                fig_vol = go.Figure(go.Bar(
                    x=ch.index if timeframe not in ["1분","5분","10분","60분","240분"] else list(range(len(ch))),
                    y=ch["Volume"], marker_color=vol_colors))
                fig_vol.update_layout(
                    height=100, margin=dict(l=0,r=0,t=0,b=0),
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    xaxis=dict(showgrid=False,
                               ticktext=x_labels if timeframe in ["1분","5분","10분","60분","240분"] else None,
                               tickvals=list(range(len(ch))) if timeframe in ["1분","5분","10분","60분","240분"] else None,
                               nticks=10),
                    yaxis=dict(showgrid=False, showticklabels=False))
                st.plotly_chart(fig_vol, use_container_width=True)

                # 현재 타임프레임 정보
                st.caption(f"· {cfg['label']} | {len(ch)}개 캔들 | 마지막 업데이트: {datetime.now().strftime('%H:%M:%S')}")

        with col_s:
            st.subheader("멀티 비교")
            cmp_list = st.multiselect("비교 종목", [t for t,_,_ in TOP100[:20]], default=["AAPL","NVDA"])
            if cmp_list:
                fig_cmp = go.Figure()
                for t in cmp_list:
                    h2, _ = get_stock(t, period)
                    if h2 is not None and not h2.empty:
                        norm = h2["Close"] / h2["Close"].iloc[0] * 100
                        fig_cmp.add_trace(go.Scatter(x=h2.index, y=norm, name=t, mode="lines"))
                fig_cmp.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                      yaxis_title="수익률(기준100)", xaxis=dict(showgrid=False),
                                      yaxis=dict(gridcolor="#f0f0f0"), legend=dict(orientation="h", y=1.1))
                st.plotly_chart(fig_cmp, use_container_width=True)

            st.subheader("52주 위치")
            h52 = info.get("fiftyTwoWeekHigh", curr_price)
            l52 = info.get("fiftyTwoWeekLow",  curr_price)
            if h52 > l52:
                pos_pct = (curr_price - l52) / (h52 - l52) * 100
                st.progress(int(pos_pct))
                st.caption(f"위치: {pos_pct:.1f}%\n최저 ${l52:.2f} ~ 최고 ${h52:.2f}")

    # ── 탭 2: 재무 분석 ─────────────────────────────────
    with tabs[1]:
        cf1, cf2 = st.columns(2)
        with cf1:
            st.subheader("핵심 재무 지표")
            fin = {
                "PER": info.get("trailingPE"), "PBR": info.get("priceToBook"),
                "PSR": info.get("priceToSalesTrailing12Months"), "EPS": info.get("trailingEps"),
                "베타": info.get("beta"), "부채비율": info.get("debtToEquity"),
                "ROE": info.get("returnOnEquity"), "ROA": info.get("returnOnAssets"),
                "영업이익률": info.get("operatingMargins"), "순이익률": info.get("profitMargins"),
            }
            for k, v in fin.items():
                if v is not None:
                    fmt = f"{v*100:.2f}%" if k in ["ROE","ROA","영업이익률","순이익률"] else f"{round(v,2)}"
                    st.metric(k, fmt)
        with cf2:
            st.subheader("애널리스트 의견")
            target = info.get("targetMeanPrice")
            rec    = info.get("recommendationKey","N/A")
            if target:
                upside = (target - curr_price) / curr_price * 100
                st.metric("목표 주가", f"${target:.2f}", f"{upside:+.1f}%",
                          delta_color="normal" if upside > 0 else "inverse")
            rec_map = {"buy":"강력 매수","overperform":"매수","hold":"보유","underperform":"매도","sell":"강력 매도"}
            st.info(f"추천: **{rec_map.get(rec, rec.upper())}**")
            try:
                fin_stmt = yf.Ticker(ticker).financials
                if fin_stmt is not None and not fin_stmt.empty:
                    rev = fin_stmt.loc["Total Revenue"] if "Total Revenue" in fin_stmt.index else None
                    net = fin_stmt.loc["Net Income"]    if "Net Income"    in fin_stmt.index else None
                    if rev is not None:
                        fig_fin = go.Figure()
                        fig_fin.add_trace(go.Bar(x=[str(d.year) for d in rev.index], y=rev.values/1e9, name="매출(B)", marker_color="#3498db"))
                        if net is not None:
                            fig_fin.add_trace(go.Bar(x=[str(d.year) for d in net.index], y=net.values/1e9, name="순이익(B)", marker_color="#2d8a4e"))
                        fig_fin.update_layout(height=260, barmode="group", margin=dict(l=0,r=0,t=10,b=0),
                                              paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                        st.plotly_chart(fig_fin, use_container_width=True)
            except: st.caption("재무제표 데이터를 불러올 수 없어요.")

    # ── 탭 3: 매매 신호 ─────────────────────────────────
    with tabs[2]:
        if len(hist) >= 20:
            signals, rsi_val = compute_signals(hist)
            ai_score, grade, grade_col, score_details, _ = compute_ai_score(hist, info)

            buy_cnt  = sum(1 for v in signals.values() if "매수" in v[0] or "과매도" in v[0] or "반등" in v[0])
            sell_cnt = sum(1 for v in signals.values() if "매도" in v[0] or "과매수" in v[0] or "과열" in v[0])

            # ── AI 종합 점수 대시보드 ──
            st.markdown("#### AI 종합 점수")
            sc1, sc2, sc3 = st.columns([1, 2, 1])
            with sc1:
                fig_gauge = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=ai_score,
                    number={"suffix": "점", "font": {"size": 36}},
                    gauge={
                        "axis": {"range": [0, 100], "tickwidth": 1},
                        "bar":  {"color": grade_col, "thickness": 0.3},
                        "steps": [
                            {"range": [0,  30], "color": "#fdedec"},
                            {"range": [30, 45], "color": "#fef9e7"},
                            {"range": [45, 55], "color": "#f5f5f5"},
                            {"range": [55, 70], "color": "#eaf4fb"},
                            {"range": [70,100], "color": "#eafaf1"},
                        ],
                        "threshold": {"line": {"color": grade_col, "width": 3}, "value": ai_score}
                    }
                ))
                fig_gauge.update_layout(height=220, margin=dict(l=10,r=10,t=20,b=10),
                                        paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_gauge, use_container_width=True)

            with sc2:
                st.markdown(f"""
                <div style='background:{grade_col}18;border-left:4px solid {grade_col};
                            border-radius:0 10px 10px 0;padding:14px 16px;margin-bottom:10px'>
                    <div style='font-size:22px;font-weight:700;color:{grade_col}'>{grade}</div>
                    <div style='font-size:12px;color:#888;margin-top:4px'>
                        기술적 지표 + 재무 데이터 종합 분석 점수
                    </div>
                </div>""", unsafe_allow_html=True)
                for name, delta, icon in score_details:
                    clr = "#2d8a4e" if "+" in delta else "#c0392b" if "-" in delta else "#888"
                    st.markdown(
                        f"<div style='display:flex;justify-content:space-between;padding:4px 0;"
                        f"border-bottom:0.5px solid #f0f0f0;font-size:13px'>"
                        f"<span>{icon} {name}</span>"
                        f"<span style='font-weight:600;color:{clr}'>{delta}</span></div>",
                        unsafe_allow_html=True)

            with sc3:
                fig_rsi = go.Figure(go.Indicator(
                    mode="gauge+number", value=rsi_val, title={"text":"RSI"},
                    gauge={"axis":{"range":[0,100]}, "bar":{"color":"#3498db"},
                           "steps":[{"range":[0,30],"color":"#eafaf1"},
                                    {"range":[30,70],"color":"#fdfefe"},
                                    {"range":[70,100],"color":"#fdedec"}],
                           "threshold":{"line":{"color":"red","width":2},"value":70}}))
                fig_rsi.update_layout(height=220, margin=dict(l=10,r=10,t=30,b=10),
                                      paper_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_rsi, use_container_width=True)

            st.divider()
            st.markdown("#### 개별 지표 신호")
            cs1, cs2 = st.columns(2)
            with cs1:
                if buy_cnt > sell_cnt: st.success(f"**종합: 매수 우세** ({buy_cnt}/{len(signals)})")
                elif sell_cnt > buy_cnt: st.error(f"**종합: 매도 우세** ({sell_cnt}/{len(signals)})")
                else: st.info("**종합: 중립**")
                for name, (label, icon) in signals.items():
                    bg = "#eafaf1" if "매수" in label or "과매도" in label or "반등" in label else                          "#fdedec" if "매도" in label or "과매수" in label or "과열" in label else "#f5f5f5"
                    st.markdown(f'<div class="signal-card" style="background:{bg}">'
                                f'<span style="font-size:13px">{icon} <b>{name}</b></span>'
                                f'<span style="font-size:12px;color:#555">{label}</span></div>', unsafe_allow_html=True)
            with cs2:
                if rsi_val < 30: st.success("RSI: 과매도 구간 — 반등 가능성")
                elif rsi_val > 70: st.error("RSI: 과매수 구간 — 조정 주의")
                else: st.info(f"RSI: 중립 구간 ({rsi_val:.1f})")

            # 카카오 알림
            if kakao_alert and KAKAO_TOKEN:
                msg = f"[AI 종합 점수] {ticker}\n점수: {ai_score}/100 — {grade}\nRSI: {rsi_val:.1f} | 매수신호: {buy_cnt}/{len(signals)}\n⚠ 참고용 정보입니다"
                if st.button("📱 카카오톡으로 점수 전송", key="kakao_score"):
                    send_kakao(KAKAO_TOKEN, msg) and st.success("전송 완료!")

    # ── 탭 4: 뉴스 & 감성 ───────────────────────────────
    with tabs[3]:
        articles = get_news(info.get("longName", ticker), NEWS_API_KEY)
        if articles:
            pos_n = neg_n = neu_n = 0
            for a in articles:
                title = a.get("title","") or ""
                desc  = a.get("description","") or ""
                sl, si, sc = sentiment(title + " " + desc)
                if "긍정" in sl: pos_n+=1
                elif "부정" in sl: neg_n+=1
                else: neu_n+=1
                st.markdown(f'<div class="news-card {sc}"><div style="font-size:13px;font-weight:500;margin-bottom:3px">{title[:80]}</div>'
                            f'<div style="font-size:11px;color:#888">{si} {sl} · {a.get("source",{}).get("name","")} · {a.get("publishedAt","")[:10]}</div></div>',
                            unsafe_allow_html=True)
            st.divider()
            total_n = pos_n+neg_n+neu_n
            nc1,nc2,nc3 = st.columns(3)
            nc1.metric("긍정", f"{pos_n}건", f"{pos_n/total_n*100:.0f}%")
            nc2.metric("중립", f"{neu_n}건", f"{neu_n/total_n*100:.0f}%")
            nc3.metric("부정", f"{neg_n}건", f"{neg_n/total_n*100:.0f}%")
        else:
            st.info("뉴스 API 키를 Secrets에 추가하면 실시간 뉴스가 표시돼요. (NEWS_API_KEY)")

    # ── 탭 5: 포트폴리오 ────────────────────────────────
    with tabs[4]:
        st.subheader("내 포트폴리오")
        with st.expander("+ 종목 추가"):
            pc1,pc2,pc3 = st.columns(3)
            p_ticker = pc1.text_input("티커", placeholder="AAPL")
            p_shares = pc2.number_input("수량", min_value=0.0, step=0.1)
            p_avg    = pc3.number_input("평균 매수가 ($)", min_value=0.0, step=0.1)
            if st.button("추가"):
                if p_ticker and p_shares > 0 and p_avg > 0:
                    h2,_ = get_stock(p_ticker.upper(), "1d")
                    curr2 = h2["Close"].iloc[-1] if h2 is not None and not h2.empty else p_avg
                    st.session_state.portfolio.append({"ticker":p_ticker.upper(),"shares":p_shares,"avg":p_avg,"curr":curr2})
                    st.success(f"{p_ticker.upper()} 추가 완료!")
                    st.rerun()

        if st.session_state.portfolio:
            tv,tc,tg,tr = compute_portfolio_stats(st.session_state.portfolio)
            pm1,pm2,pm3 = st.columns(3)
            pm1.metric("총 평가금액", f"${tv:,.0f}")
            pm2.metric("총 투자금액", f"${tc:,.0f}")
            pm3.metric("총 손익", f"${tg:,.0f}", f"{tr:+.2f}%", delta_color="normal" if tr>=0 else "inverse")
            for i,h in enumerate(st.session_state.portfolio):
                val = h["shares"]*h["curr"]
                ret = (h["curr"]-h["avg"])/h["avg"]*100
                pa,pb,pc_,pd_ = st.columns([2,1,1,1])
                pa.write(f"**{h['ticker']}**")
                pb.metric("현재가", f"${h['curr']:.2f}")
                pc_.metric("평가금액", f"${val:,.0f}", f"{ret:+.1f}%", delta_color="normal" if ret>=0 else "inverse")
                if pd_.button("삭제", key=f"del_{i}"):
                    st.session_state.portfolio.pop(i); st.rerun()
            labels = [h["ticker"] for h in st.session_state.portfolio]
            values = [h["shares"]*h["curr"] for h in st.session_state.portfolio]
            pie1,pie2 = st.columns(2)
            with pie1:
                fig_pie = go.Figure(go.Pie(labels=labels, values=values, hole=0.4))
                fig_pie.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0))
                st.plotly_chart(fig_pie, use_container_width=True)
            with pie2:
                rets = [(h["ticker"],(h["curr"]-h["avg"])/h["avg"]*100) for h in st.session_state.portfolio]
                rets.sort(key=lambda x: x[1])
                fig_bar = go.Figure(go.Bar(x=[r[1] for r in rets], y=[r[0] for r in rets], orientation="h",
                                           marker_color=["#2d8a4e" if r[1]>=0 else "#c0392b" for r in rets]))
                fig_bar.update_layout(height=260, margin=dict(l=0,r=0,t=10,b=0),
                                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
                st.plotly_chart(fig_bar, use_container_width=True)

            # 리밸런싱
            st.subheader("리밸런싱 계산기")
            rb_cols = st.columns(len(st.session_state.portfolio))
            targets = [col.number_input(f"{h['ticker']} (%)", 0, 100,
                       int(100/len(st.session_state.portfolio)), key=f"rb_{i}")
                       for i,(h,col) in enumerate(zip(st.session_state.portfolio, rb_cols))]
            if sum(targets)==100:
                for h,tgt in zip(st.session_state.portfolio, targets):
                    curr_w = (h["shares"]*h["curr"])/tv*100
                    diff   = tgt - curr_w
                    action = "매수" if diff>0 else "매도"
                    amt    = abs(diff/100*tv)
                    r1,r2 = st.columns(2)
                    r1.write(f"**{h['ticker']}**: {curr_w:.1f}% → {tgt}%")
                    r2.write(f"→ {action} {amt/h['curr']:.2f}주 (${amt:,.0f})")
            elif sum(targets)!=0:
                st.warning(f"비중 합계 {sum(targets)}% — 100%로 맞춰주세요.")
        else:
            st.info("종목을 추가해서 포트폴리오를 관리해보세요!")

    # ── 탭 6: 주가 예측 ─────────────────────────────────
    with tabs[5]:
        st.subheader("주가 예측")
        st.caption("과거 주가 추세를 학습해 미래 가격을 예측해요. (다항회귀 + 95% 신뢰구간)")
        pred_days = st.slider("예측 기간 (일)", 7, 90, 30)
        if st.button("예측 시작", type="primary"):
            with st.spinner("모델 학습 중..."):
                df_p, fc = run_prediction(hist, pred_days)
            if fc is not None:
                pred_price = fc["yhat"].iloc[-1]
                upside     = (pred_price - curr_price) / curr_price * 100
                pp1,pp2,pp3 = st.columns(3)
                pp1.metric(f"{pred_days}일 후 예측가", f"${pred_price:.2f}", f"{upside:+.1f}%",
                           delta_color="normal" if upside>0 else "inverse")
                pp2.metric("예측 상단", f"${fc['yhat_upper'].iloc[-1]:.2f}")
                pp3.metric("예측 하단", f"${fc['yhat_lower'].iloc[-1]:.2f}")
                fig_pred = go.Figure()
                fig_pred.add_trace(go.Scatter(x=df_p["ds"], y=df_p["y"], name="실제", line=dict(color="#3498db",width=1.5)))
                fig_pred.add_trace(go.Scatter(x=fc["ds"], y=fc["yhat"], name="예측", line=dict(color="#e74c3c",width=1.5,dash="dash")))
                fig_pred.add_trace(go.Scatter(
                    x=pd.concat([fc["ds"],fc["ds"][::-1]]),
                    y=pd.concat([fc["yhat_upper"],fc["yhat_lower"][::-1]]),
                    fill="toself", fillcolor="rgba(231,76,60,0.1)",
                    line=dict(color="rgba(0,0,0,0)"), name="신뢰구간"))
                fig_pred.update_layout(height=400, margin=dict(l=0,r=0,t=10,b=0),
                                       paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                       xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#f0f0f0"),
                                       legend=dict(orientation="h",y=1.05))
                st.plotly_chart(fig_pred, use_container_width=True)
                if kakao_alert and KAKAO_TOKEN:
                    msg = f"[예측] {ticker} {pred_days}일 후 ${pred_price:.2f} ({upside:+.1f}%)"
                    send_kakao(KAKAO_TOKEN, msg) and st.success("카카오톡 전송 완료!")
                st.warning("⚠ 참고용 예측이며 실제 투자 결과와 다를 수 있어요.")

    # ── 탭 7: AI 추천 ────────────────────────────────────
    with tabs[6]:
        st.subheader("포트폴리오 추천")
        st.caption("투자 성향에 맞는 포트폴리오를 추천해드려요. Claude API 키가 없어도 규칙 기반으로 동작해요.")
        if not ANTHROPIC_API_KEY:
            st.info("Claude API 키 없이 규칙 기반 추천으로 동작해요. API 키를 추가하면 더 정교한 AI 추천을 받을 수 있어요.")
        ai1, ai2 = st.columns(2)
        with ai1:
            risk   = st.selectbox("투자 성향", ["안정형 (저위험)","중립형 (중위험)","공격형 (고위험)"])
            amount = st.number_input("투자 금액 ($)", min_value=1000, value=10000, step=1000)
        with ai2:
            sectors = st.multiselect("관심 섹터", list(set(s for _,_,s in TOP100)),
                                     default=["빅테크","반도체"])
        if st.button("포트폴리오 추천 받기", type="primary"):
            with st.spinner("분석 중..."):
                result = ai_portfolio_recommend(risk, amount, sectors, ANTHROPIC_API_KEY)
            if result:
                st.success(f"**{result.get('summary','')}**")
                st.markdown(f"_{result.get('strategy','')}_")
                st.divider()
                for s in result.get("stocks",[]):
                    w     = s.get("weight",0)
                    alloc = amount * w / 100
                    ai_c1, ai_c2, ai_c3 = st.columns([2,1,2])
                    ai_c1.markdown(f"**{s.get('ticker')}** — {s.get('name')}")
                    ai_c2.metric("비중", f"{w}%", f"${alloc:,.0f}")
                    ai_c3.caption(s.get("reason",""))
                    st.progress(w)
                fig_ai = go.Figure(go.Pie(
                    labels=[s["ticker"] for s in result.get("stocks",[])],
                    values=[s["weight"] for s in result.get("stocks",[])],
                    hole=0.4, textinfo="label+percent"))
                fig_ai.update_layout(height=300, margin=dict(l=0,r=0,t=10,b=0))
                st.plotly_chart(fig_ai, use_container_width=True)
                if kakao_alert and KAKAO_TOKEN:
                    msg = f"[AI추천] {risk}\n" + "\n".join([f"• {s['ticker']} {s['weight']}%" for s in result.get("stocks",[])])
                    send_kakao(KAKAO_TOKEN, msg) and st.success("카카오톡 전송 완료!")
                st.warning("⚠ 참고용 추천이며 투자 조언이 아닙니다.")

    # ── 탭 8: 카카오 알림 ────────────────────────────────
    with tabs[7]:
        st.subheader("카카오톡 알림 설정")
        st.markdown("""
        """)
        st.divider()
        test_msg = st.text_area("테스트 메시지", value=f"[주식 알림 테스트]\n{ticker} 현재가: ${curr_price:.2f}")
        if st.button("카카오톡 테스트 전송"):
            if not KAKAO_TOKEN:
                st.error("Secrets에 KAKAO_ACCESS_TOKEN이 없어요.")
            else:
                ok = send_kakao(KAKAO_TOKEN, test_msg)
                st.success("전송 성공!") if ok else st.error("전송 실패. 토큰을 확인해주세요.")

st.divider()
st.caption(f"데이터: Yahoo Finance · NewsAPI · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
