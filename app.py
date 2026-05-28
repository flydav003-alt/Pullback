# ==============================================================================
# 台股波段拉回選股工具 v3.1
# 修正：① 深色 CSS 完整覆蓋 Streamlit 白色預設主題
#       ② 篩選條件新增「寬鬆模式」及各條件獨立計數分析
#       ③ 止跌轉折放寬：今收 > 前 N 日任一高點 OR 今收站回 MA20
# ==============================================================================

import re
import io
import time
import warnings
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st

warnings.filterwarnings("ignore")

# ==============================================================================
# ── 0. 頁面設定
# ==============================================================================
st.set_page_config(
    page_title="台股波段拉回選股",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ_TW = ZoneInfo("Asia/Taipei")

# ==============================================================================
# ── 1. 深色主題 CSS
#    關鍵修正：強制覆蓋 Streamlit 的白色 header / toolbar / main block
# ==============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

/* ═══════════════════════════════════════════════
   強制深色：覆蓋 Streamlit 所有預設白色區塊
   ═══════════════════════════════════════════════ */
html, body { background-color: #0a0e1a !important; }

/* 最外層 App 容器 */
.stApp,
.stApp > div,
[data-testid="stAppViewContainer"],
[data-testid="stAppViewContainer"] > section {
    background-color: #0a0e1a !important;
    background: #0a0e1a !important;
}

/* ⚠️ 頂部 toolbar / header（白色條的主因）*/
[data-testid="stHeader"],
[data-testid="stToolbar"],
header[data-testid="stHeader"] {
    background-color: #0a0e1a !important;
    background: #0a0e1a !important;
    border-bottom: 1px solid rgba(59,130,246,0.12) !important;
}

/* main content 區塊 */
[data-testid="stMain"],
[data-testid="block-container"],
.main .block-container {
    background-color: #0a0e1a !important;
    padding-top: 1.5rem !important;
    max-width: 100% !important;
}

/* 全域文字 */
html, body, [class*="css"], p, span, div, label, h1, h2, h3, h4 {
    font-family: 'Noto Sans TC', sans-serif !important;
    color: #e2e8f0;
}

/* ── Sidebar ── */
[data-testid="stSidebar"],
[data-testid="stSidebar"] > div {
    background: #0d1829 !important;
    border-right: 1px solid rgba(59,130,246,0.15) !important;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #cbd5e1 !important;
}
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #60a5fa !important;
    font-size: 0.85rem !important;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border-bottom: 1px solid rgba(59,130,246,0.2);
    padding-bottom: 6px;
    margin-top: 4px;
}

/* ── Slider ── */
[data-testid="stSlider"] label { color: #94a3b8 !important; font-size: 0.82rem !important; }
[data-testid="stSlider"] p { color: #60a5fa !important; font-weight: 700 !important; }

/* ── Radio ── */
[data-testid="stRadio"] label { color: #94a3b8 !important; }
[data-testid="stRadio"] div[role="radiogroup"] p { color: #e2e8f0 !important; }

/* ── TextArea ── */
textarea {
    background-color: #0f1c30 !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(59,130,246,0.25) !important;
    border-radius: 8px !important;
}

/* ── Caption / small text ── */
[data-testid="stCaptionContainer"] p,
small, .stCaption { color: #64748b !important; }

/* ── Divider ── */
hr { border-color: rgba(59,130,246,0.15) !important; margin: 10px 0 !important; }

/* ── Metric 卡片 ── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e2d4a 0%, #162038 100%) !important;
    border: 1px solid rgba(59,130,246,0.22) !important;
    border-radius: 12px !important;
    padding: 16px 20px !important;
}
[data-testid="stMetricLabel"] p,
[data-testid="stMetric"] label {
    color: #64748b !important;
    font-size: 0.75rem !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 1.8rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricDelta"] {
    color: #22c55e !important;
    font-size: 0.82rem !important;
}

/* ── Button ── */
.stButton > button {
    background: linear-gradient(135deg, #1d4ed8, #1e40af) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    padding: 10px 24px !important;
    width: 100% !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 15px rgba(59,130,246,0.35) !important;
}

/* ── Progress bar ── */
[data-testid="stProgressBar"] > div { background: rgba(59,130,246,0.15) !important; border-radius: 4px; }
[data-testid="stProgressBar"] > div > div { background: linear-gradient(90deg,#3b82f6,#60a5fa) !important; }

/* ── DataFrame ── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(59,130,246,0.18) !important;
    border-radius: 10px !important;
}

/* ── Warning / Info ── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── Selectbox 選單本體 ── */
[data-testid="stSelectbox"] div[data-baseweb="select"] > div {
    background-color: #0f1c30 !important;
    border-color: rgba(59,130,246,0.25) !important;
    color: #e2e8f0 !important;
}

/* ── Selectbox 下拉選單字色修正 ──
   Streamlit 把 popover 渲染在 body 最外層（portal），
   需要直接針對 body 下的 baseweb 元件覆蓋 */
body [data-baseweb="popover"],
body [data-baseweb="menu"],
body ul[role="listbox"] {
    background-color: #1e293b !important;
    border: 1px solid rgba(59,130,246,0.3) !important;
}
body [data-baseweb="menu"] li,
body [data-baseweb="list-item"],
body ul[role="listbox"] li,
body [role="option"] {
    background-color: #1e293b !important;
    color: #e2e8f0 !important;
}
body [role="option"]:hover,
body [data-baseweb="menu"] li:hover {
    background-color: #2d4a7a !important;
    color: #ffffff !important;
}
body [aria-selected="true"][role="option"] {
    background-color: #1d4ed8 !important;
    color: #ffffff !important;
}

/* ── Tooltip（問號 hover）──
   同樣是 portal 渲染在 body 最外層，需從 body 選取 */
body [data-baseweb="tooltip"],
body [role="tooltip"],
div[data-baseweb="tooltip"] div,
[data-testid="stTooltipHoverTarget"] + div,
body [class*="Tooltip"],
body [class*="tooltip"] {
    background-color: #1e293b !important;
    color: #e2e8f0 !important;
    border: 1px solid rgba(59,130,246,0.35) !important;
    border-radius: 6px !important;
    font-size: 0.82rem !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important;
}
/* tooltip 箭頭 */
body [data-baseweb="tooltip"] [data-popper-arrow]::before,
body [role="tooltip"] [data-popper-arrow]::before {
    border-color: #1e293b !important;
}

/* ════════════════════════════════════════════════
   自訂元件樣式
   ════════════════════════════════════════════════ */

/* 英雄標題 */
.hero-header {
    background: linear-gradient(120deg, #1a2744 0%, #162038 45%, #1e1035 100%);
    border: 1px solid rgba(59,130,246,0.28);
    border-radius: 16px;
    padding: 26px 34px;
    margin-bottom: 18px;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -50px; right: -50px;
    width: 180px; height: 180px;
    background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%);
    border-radius: 50%;
    pointer-events: none;
}
.hero-title {
    font-size: 2rem;
    font-weight: 900;
    background: linear-gradient(90deg, #60a5fa 0%, #f87171 55%, #fbbf24 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 6px 0;
}
.hero-subtitle { color: #94a3b8 !important; font-size: 0.9rem; margin: 0; }

/* 排程狀態卡 */
.sched-card {
    background: #0f1e33;
    border: 1px solid rgba(34,197,94,0.28);
    border-radius: 10px;
    padding: 12px 16px;
    height: 70px;
}
.sched-card.warn { border-color: rgba(251,191,36,0.38); }
.sched-lbl { color: #475569; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.sched-val { color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-size: 0.92rem; font-weight: 600; }
.sched-val.green { color: #22c55e; }
.sched-val.amber { color: #fbbf24; }

/* 策略說明欄 */
.strat-info {
    background: linear-gradient(135deg, #172035, #1c2a48);
    border-left: 3px solid #3b82f6;
    border-radius: 8px;
    padding: 14px 18px;
    margin-bottom: 14px;
    font-size: 0.86rem;
    color: #94a3b8;
    line-height: 1.75;
}
.strat-info strong { color: #60a5fa; }

/* 條件漏斗分析卡 */
.funnel-card {
    background: #0f1e33;
    border: 1px solid rgba(59,130,246,0.18);
    border-radius: 10px;
    padding: 14px 18px;
    font-size: 0.83rem;
}
.funnel-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 0;
    border-bottom: 1px solid rgba(59,130,246,0.08);
    color: #94a3b8;
}
.funnel-row:last-child { border-bottom: none; }
.funnel-pass { color: #22c55e; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.funnel-label { color: #64748b; font-size: 0.78rem; }

/* 風險提醒 */
.risk-warn {
    background: linear-gradient(135deg, #1f1510, #2d1b0e);
    border: 1px solid rgba(251,191,36,0.3);
    border-radius: 8px;
    padding: 12px 18px;
    margin-top: 22px;
    color: #fbbf24;
    font-size: 0.8rem;
    text-align: center;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# ── 2. 股票池
# ==============================================================================
STOCK_STRING = """
2454聯發科3035智原3443創意3661世芯-KY6526達發5269祥碩3529力旺5274信驊6533晶心科
2379瑞昱4919新唐2401凌陽3041揚智2363矽統8227巨有科技2388威盛3014聯陽3094聯傑3122笙泉
3135凌航3169亞信3228金麗科3259鑫創4952凌通4968立積5272笙科5471松翰6103合邦6104創惟
6129普誠6202盛群6229研通6233旺玖6237驊訊6243迅杰6462神盾6494九齊6679鈺太6693廣閎科
6716應廣6756威鋒電子6909創控7556意德士6568宏觀2330台積電2303聯電5347世界6770力積電
2344華邦電2481強茂8261富鼎3707漢磊5425台半6435大中3675德微5299杰力2302麗正2329華泰
2340光磊2342茂矽3105穩懋3686達能4923力士6552易華電6937天虹7712博盛半導體8086宏捷科
8162微矽電子1560中砂3583辛耘6187萬潤6640均華3131弘塑3551世禾3413京鼎8028昇陽半導體
4770上品3016嘉晶5536聖暉5543崇佑-KY3663鑫科6953家碩2338光罩3374精材3467台灣精材
6261久元6548長科6854錼創科技3711日月光投控2449京元電子6239力成6147頎邦3264欣銓
6510精測6223旺矽6515穎崴2360致茂6271同欣電8150南茂6257矽格8110華東8131福懋科
3265台星科6683雍智科技6788華景電7734印能科技2351順德2369菱生2434統懋2441超豐3178公準
3372典範3581博磊5302太欣5344立衛6208日揚6411晶焱6423億而得6525捷敏-KY7768頌勝科技
7822倍利科8383千附3030德律5285界霖2337旺宏2408南亞科3006晶豪科2451創見4967十銓
8271宇瞻8299群聯3260威剛6531愛普8088品安3268海德威6732昇佳電子4973廣穎5351鈺創
8040九暘6485點序8054安國8277商丞2436偉詮電3257虹冠電3317尼克森3438類比科3588通嘉
6138茂達6291沛亨6415矽力-KY6651全宇昕6799來頡8081致新6488環球晶3532台勝科6182合晶
5483中美晶3680家登4749新應材6532瑞耘8091翔名3029零壹3150鈺寶3555重鵬3567逸昌
4951精拓科5443均豪6573虹揚-KY6720久昌6823濾能6829千附精密6895宏碩系統6921嘉雨思
7704明遠精密7749意騰-KY7751竑騰7769鴻勁7810捷創科技8024佑華8102傑霖科技2404漢唐
6139亞翔6196帆宣6215和椿6438迅得6691洋基工程6698旭暉應材7730暉盛7828創新服務
3037欣興8046南電3189景碩2383台光電2368金像電6274台燿4958臻鼎-KY6269台郡2313華通
6191精成科5469瀚宇博2367燿華3044健鼎3645達邁3715定穎投控6213聯茂6672騰輝電子-KY
8039台虹8213志超6108競國6153嘉聯益2317鴻海3231緯創2382廣達6669緯穎2356英業達
3706神達4938和碩8210勤誠3013晟銘電2395研華6414樺漢6166凌華3088艾訊8050廣積
3022威強電3416融程電2324仁寶2353宏碁2354鴻準2357華碩2376技嘉2377微星2385群光
3515華擎6117迎廣7711永擎2059川湖3017奇鋐3324雙鴻2421建準3653健策4931新盛力
6230超眾6831邁科6805富世達2308台達電6409旭隼6412群電6282康舒6121新普3211順達
2301光寶科2420新巨2457飛宏3015全漢3617碩天4979華星光3163波若威6451訊芯-KY4908前鼎
6442光聖3450聯鈞3596智易3363上詮3081聯亞5222全訊5487通泰7770君曜7772耀穎2345智邦
5388中磊6285啟碁4906正文2455全新3047訊舟3380明泰3704合勤控4977眾達-KY6416瑞祺電通
5468凱鈺2409友達3008大立光3019亞光3362先進光3406玉晶光3454晶睿3481群創3504揚明光
3630新鉅科4976佳凌6209今國光6789采鈺2458義隆3034聯詠3141晶宏3227原相3527聚積
3530晶相光3545敦泰3556禾瑞亞3592瑞鼎4961天鈺5236凌陽創新6684安格6695芯鼎8016矽創
3023信邦3665貿聯-KY6279胡連6205詮欣3217優群3376新日興2392正崴2462良得電3533嘉澤
6133金橋6197佳必琪6272驊陞6715嘉基8103瀚荃3491昇達科7717萊德光電2485兆赫3138耀登
3062建漢2314台揚2312金寶2419仲琦2355敬鵬4916事欣科6443元晶2327國巨3624光頡6207雷科
2478大毅8042金山電3117年程3026禾伸堂2472立隆電6173信昌電6127九豪2492華新科3236千如
6155鈞寶6204艾華3090日電貿2375凱美6449鈺邦6432今展科2428興勤6224聚鼎3191和進
4760勤凱6175立敦6284佳邦5328華容3357臺慶科8121越峰5228鈺鎧3042晶技
"""


def extract_stock_ids(s: str) -> list[str]:
    """提取 4~5 位數股號，re.ASCII 確保中文不干擾 \\b 邊界"""
    codes = re.findall(r'\b(\d{4,5})\b', s, re.ASCII)
    seen, out = set(), []
    for c in codes:
        if c not in seen:
            seen.add(c); out.append(c)
    return out


def build_name_map(s: str) -> dict[str, str]:
    """從 STOCK_STRING 解析 {股號: 中文名稱}
    注意：\b 在中文字元前會失效，改用 lookahead 確保名稱正確截斷
    """
    pairs = re.findall(r'(\d{4,5})([^\d\s]{1,12}?)(?=\d{4}|\s|$)', s)
    return {code: name.strip() for code, name in pairs if name.strip()}


DEFAULT_STOCK_IDS = extract_stock_ids(STOCK_STRING)
STOCK_NAME_MAP = build_name_map(STOCK_STRING)

# ==============================================================================
# ── 3. FinMind API
# ==============================================================================
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"


def get_token() -> str:
    try:
        t = st.secrets["finmind"]["token"]
        if not t or t == "your_token_here":
            st.error("⚠️ 請在 Streamlit Secrets 設定有效的 FinMind token！")
            st.stop()
        return t
    except KeyError:
        st.error("⚠️ 找不到 FinMind token，請至 Settings → Secrets 設定。")
        st.stop()


def fetch_prices(ids: list[str], start: str, end: str, token: str) -> dict[str, pd.DataFrame]:
    """
    逐支呼叫 FinMind TaiwanStockPrice，回傳 dict[stock_id → OHLCV DataFrame]
    每支間隔 50ms，避免限流
    """
    result: dict[str, pd.DataFrame] = {}
    RENAME = {
        "date": "Date", "open": "Open",
        "max": "High", "min": "Low",
        "close": "Close",
        "Trading_Volume": "Volume",
        "trading_volume": "Volume",
    }
    NEED = ["Open", "High", "Low", "Close", "Volume"]

    for sid in ids:
        try:
            r = requests.get(FINMIND_URL, params={
                "dataset": "TaiwanStockPrice",
                "data_id": sid,
                "start_date": start,
                "end_date": end,
                "token": token,
            }, timeout=15)
            r.raise_for_status()
            pl = r.json()
            if pl.get("status") != 200 or not pl.get("data"):
                continue
            df = pd.DataFrame(pl["data"]).rename(columns=RENAME)
            if not all(c in df.columns for c in ["Date"] + NEED):
                continue
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.set_index("Date").sort_index()
            df = df[NEED].apply(pd.to_numeric, errors="coerce").dropna(subset=["Close"])
            if len(df) >= 100:
                result[sid] = df
        except Exception:
            pass
        time.sleep(0.05)
    return result


@st.cache_data(ttl=3600, show_spinner=False)
def cached_fetch(ids_tuple: tuple, start: str, end: str, token: str):
    data = fetch_prices(list(ids_tuple), start, end, token)
    return data, len(data), len(ids_tuple) - len(data)


# ==============================================================================
# ── 4. 排程
# ==============================================================================
def tw_now() -> datetime:
    return datetime.now(tz=TZ_TW)


def should_auto_fetch() -> bool:
    n = tw_now()
    if n.weekday() >= 5 or n.hour < 18:
        return False
    return st.session_state.get("last_fetch_date") != n.date()


def next_fetch_str() -> str:
    n = tw_now()
    t6 = n.replace(hour=18, minute=0, second=0, microsecond=0)
    if n < t6 and n.weekday() < 5:
        return t6.strftime("%m/%d %H:%M")
    d = n + timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.replace(hour=18, minute=0, second=0, microsecond=0).strftime("%m/%d %H:%M")


# ==============================================================================
# ── 5. 技術指標
# ==============================================================================
def sma(s: pd.Series, w: int) -> pd.Series:
    return s.rolling(w, min_periods=w).mean()


def atr(df: pd.DataFrame, w: int = 14) -> pd.Series:
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([(h - l), (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    return tr.rolling(w).mean()


# ==============================================================================
# ── 6. 篩選策略（含條件漏斗統計）
#
#  新增「寬鬆模式」（strict=False）：
#    ④ 量縮：放寬為 < vol_ratio * 1.3
#    ⑤ 止跌轉折：今收 > 昨高  OR  今收 > MA20（MA20 站回也算）
#
#  同時回傳各條件通過數，方便 UI 顯示漏斗分析
# ==============================================================================
def run_filter(
    data: dict[str, pd.DataFrame],
    p: dict,
    strict: bool = True,
) -> tuple[pd.DataFrame, dict]:
    """
    回傳 (result_df, funnel_counts)
    funnel_counts = {條件名: 通過數}
    """
    funnel = {
        "① 長線多頭":  0,
        "② 動能記憶":  0,
        "③ 波段拉回":  0,
        "④ 量縮洗盤":  0,
        "⑤ 止跌轉折":  0,
    }
    results = []

    vol_limit = p["vol_ratio"] * (1.3 if not strict else 1.0)

    for sid, df in data.items():
        try:
            if len(df) < 210:
                continue
            df = df.copy().sort_index()
            c, h, l, v = df["Close"], df["High"], df["Low"], df["Volume"]

            ma20_s  = sma(c, 20)
            ma50_s  = sma(c, 50)
            ma60_s  = sma(c, 60)
            ma200_s = sma(c, 200)
            atr14   = atr(df, 14)

            c0, c1    = c.iloc[-1], c.iloc[-2]
            h0, h1    = h.iloc[-1], h.iloc[-2]
            ma20_0    = ma20_s.iloc[-1]
            ma50_0    = ma50_s.iloc[-1]
            ma60_0    = ma60_s.iloc[-1]
            ma200_0   = ma200_s.iloc[-1]
            atr_0     = atr14.iloc[-1]

            if any(pd.isna([c0, c1, h1, ma20_0, ma50_0, ma60_0, ma200_0, atr_0])):
                continue

            # ① 長線多頭
            if not (ma50_0 > ma200_0 and c0 > ma200_0):
                continue
            funnel["① 長線多頭"] += 1

            # ② 動能記憶
            N, M = p["momentum_days"], p["high_window"]
            hi_roll = h.rolling(M).max().iloc[-(N+1):-1]
            cl_look = c.iloc[-(N+1):-1]
            if not (cl_look >= hi_roll).any():
                continue
            funnel["② 動能記憶"] += 1

            # ③ 波段拉回
            pullback_ma = p.get("pullback_ma", 20)
            ma_ref = ma20_0 if pullback_ma == 20 else ma60_0
            if pd.isna(ma_ref) or ma_ref == 0:
                continue
            dist = (c0 - ma_ref) / ma_ref * 100
            if not (p["pullback_lower"] <= dist <= p["pullback_upper"]):
                continue
            funnel["③ 波段拉回"] += 1

            # ④ 量縮洗盤
            v3  = v.iloc[-4:-1].mean()
            v20 = v.iloc[-21:-1].mean()
            if pd.isna(v3) or pd.isna(v20) or v20 == 0:
                continue
            vs = v3 / v20
            if vs >= vol_limit:
                continue
            funnel["④ 量縮洗盤"] += 1

            # ⑤ 止跌轉折
            # 嚴格：今收 > 昨高
            # 寬鬆：今收 > 昨高  OR  今收站回 MA20（今收 > MA20 且昨收 < MA20）
            ma20_1 = ma20_s.iloc[-2] if len(ma20_s) >= 2 else np.nan
            reversal_strict = (c0 > h1)
            reversal_loose  = reversal_strict or (
                not pd.isna(ma20_1) and c0 > ma20_0 and c1 < ma20_1
            )
            passed_reversal = reversal_strict if strict else reversal_loose
            if not passed_reversal:
                continue
            funnel["⑤ 止跌轉折"] += 1

            # 第一波拉回
            first = True
            ma_ref_series = ma20_s if pullback_ma == 20 else ma60_s
            for i in range(2, 12):
                if i + 1 > len(c): break
                ci = c.iloc[-i]; hi1 = h.iloc[-(i+1)]; m_ref_i = ma_ref_series.iloc[-i]
                if pd.isna([ci, hi1, m_ref_i]).any(): continue
                ref_dist = (ci - m_ref_i) / m_ref_i * 100
                if (p["pullback_lower"] <= ref_dist <= p["pullback_upper"]) and ci > hi1:
                    first = False; break

            # 風險收益
            rl       = min(l.iloc[-1], l.iloc[-2])
            stop     = min(max(c0 - 1.5*atr_0, rl*0.98), c0*0.95)
            target   = max(c0*1.20, h.iloc[-M:].max()*1.02)
            risk     = c0 - stop
            reward   = target - c0
            rr       = round(reward/risk, 2) if risk > 0 else 0.0
            if rr < p["min_rr"]:
                continue

            results.append({
                "代號":        sid,
                "名稱":        STOCK_NAME_MAP.get(sid, ""),
                "收盤價":      round(c0, 2),
                "漲跌幅(%)":   round((c0-c1)/c1*100, 2) if c1 else 0,
                "拉回深度(%)": round(dist, 2),
                "量縮比":      round(vs, 2),
                "停損價":      round(stop, 2),
                "目標價":      round(target, 2),
                "損益比(RR)":  rr,
                "首波拉回":    "✅" if first else "—",
                "MA20":        round(ma20_0, 2),
                "MA60":        round(ma60_0, 2),
                "MA200":       round(ma200_0, 2),
            })

        except Exception:
            continue

    df_out = pd.DataFrame(results)
    if not df_out.empty:
        df_out = df_out.sort_values("損益比(RR)", ascending=False).reset_index(drop=True)
    return df_out, funnel


# ==============================================================================
# ── 7. K 線圖
# ==============================================================================
def kline(df: pd.DataFrame, sid: str) -> go.Figure:
    df = df.copy().sort_index().tail(250)
    df["MA20"]  = sma(df["Close"], 20)
    df["MA60"]  = sma(df["Close"], 60)
    df["MA200"] = sma(df["Close"], 200)

    colors = ["#ef4444" if r["Close"] >= r["Open"] else "#22c55e" for _, r in df.iterrows()]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        vertical_spacing=0.03, row_heights=[0.72, 0.28],
                        subplot_titles=(f"{sid} {STOCK_NAME_MAP.get(sid, '')}  K線 + 均線", "成交量"))

    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#ef4444", increasing_fillcolor="#ef4444",
        decreasing_line_color="#22c55e", decreasing_fillcolor="#22c55e",
        name="K線", line=dict(width=1),
    ), row=1, col=1)

    for col_name, clr, w, dash in [
        ("MA20", "#fb923c", 1.5, "solid"),
        ("MA60", "#60a5fa", 1.8, "solid"),
        ("MA200","#f43f5e", 2.0, "dot"),
    ]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col_name],
            line=dict(color=clr, width=w, dash=dash),
            name=col_name,
        ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df["Volume"],
                         marker_color=colors, name="量", opacity=0.72), row=2, col=1)

    fig.update_layout(
        height=580, paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
        font=dict(color="#94a3b8", size=11, family="Noto Sans TC"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="right", x=1, bgcolor="rgba(10,14,26,0.8)"),
        xaxis_rangeslider_visible=True,
        xaxis_rangeslider=dict(bgcolor="#0a0e1a",
                               bordercolor="rgba(59,130,246,0.2)", thickness=0.04),
        margin=dict(l=8, r=8, t=38, b=8),
    )
    fig.update_xaxes(gridcolor="rgba(59,130,246,0.07)", linecolor="rgba(59,130,246,0.2)")
    fig.update_yaxes(gridcolor="rgba(59,130,246,0.07)", linecolor="rgba(59,130,246,0.2)")
    for ann in fig.layout.annotations:
        ann.font.update(color="#64748b", size=11)
    return fig


# ==============================================================================
# ── 8. 資料抓取包裝
# ==============================================================================
def do_fetch(ids: list[str], token: str):
    n    = tw_now()
    end  = n.strftime("%Y-%m-%d")
    start = (n - timedelta(days=430)).strftime("%Y-%m-%d")
    data, ok, skip = cached_fetch(tuple(ids), start, end, token)
    st.session_state.update({
        "data_dict":       data,
        "success_cnt":     ok,
        "skip_cnt":        skip,
        "last_fetch_date": n.date(),
        "last_fetch_time": n.strftime("%Y/%m/%d %H:%M"),
    })
    return data, ok, skip


# ==============================================================================
# ── 9. 主程式
# ==============================================================================
def main():
    token    = get_token()
    has_data = bool(st.session_state.get("data_dict"))

    # ── 自動排程 ──
    if should_auto_fetch():
        with st.spinner("⏰ 18:00 自動抓取中..."):
            do_fetch(DEFAULT_STOCK_IDS, token)
        st.toast("✅ 排程自動抓取完成！", icon="🕕")
        has_data = True

    # ════════════════════════════════════════════════
    # 標題
    # ════════════════════════════════════════════════
    st.markdown("""
    <div class="hero-header">
        <p class="hero-title">📡 台股波段拉回選股系統</p>
        <p class="hero-subtitle">
            半導體 · AI · 衛星通訊供應鏈 ｜ FinMind 台股資料
            ｜ 每日 18:00 自動更新
        </p>
    </div>""", unsafe_allow_html=True)

    # 排程狀態列
    n_tw      = tw_now()
    last_time = st.session_state.get("last_fetch_time", "尚未抓取")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        st.markdown(f"""<div class="sched-card">
            <div class="sched-lbl">🕐 台灣時間</div>
            <div class="sched-val">{n_tw.strftime("%Y/%m/%d %H:%M:%S")}</div>
        </div>""", unsafe_allow_html=True)
    with sc2:
        st.markdown(f"""<div class="sched-card">
            <div class="sched-lbl">✅ 上次抓取</div>
            <div class="sched-val green">{last_time}</div>
        </div>""", unsafe_allow_html=True)
    with sc3:
        st.markdown(f"""<div class="sched-card warn">
            <div class="sched-lbl">⏰ 下次自動抓取</div>
            <div class="sched-val amber">{next_fetch_str()} 台灣時間</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<div style='height:10px'></div>", unsafe_allow_html=True)

    # 策略說明
    st.markdown("""<div class="strat-info">
        🎯 <strong>策略核心：</strong>多頭趨勢中的波段拉回止跌轉折高損益比選股<br>
        <strong>①長線多頭</strong>（MA50>MA200, Close>MA200）→
        <strong>②動能記憶</strong>（近期曾創N日新高）→
        <strong>③波段拉回</strong>（Close≈MA20/MA60 下限~上限%）→
        <strong>④量縮洗盤</strong>（近3日量&lt;20日量×Y）→
        <strong>⑤止跌轉折</strong>（今收>昨高 或 站回均線）
    </div>""", unsafe_allow_html=True)

    # ════════════════════════════════════════════════
    # SIDEBAR
    # ════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("### ⚙️ 策略參數")

        strict_mode = st.toggle("嚴格模式", value=True,
            help="關閉後：量縮放寬×1.3；止跌轉折多接受『今收站回MA20』")
        st.caption("🔒 嚴格 = 今收>昨高 + 量縮<Y\n🔓 寬鬆 = 多接受MA20站回 + 量縮放寬")
        st.divider()

        st.markdown("**① 長線多頭**")
        st.caption("MA50 > MA200 且 Close > MA200（固定）")
        st.divider()

        st.markdown("**② 動能記憶**")
        momentum_days = st.slider("回看天數 N", 5, 60, 25, 5)
        high_window   = st.slider("新高窗口 M（天）", 20, 120, 60, 5)
        st.divider()

        st.markdown("**③ 波段拉回**")
        pullback_type = st.radio(
            "拉回基準均線",
            ["小拉回 MA20", "大拉回 MA60"],
            index=0, horizontal=True,
            help="MA20：短波段拉回（10~30天）；MA60：大波段拉回（季線級別）"
        )
        pullback_ma = 20 if "MA20" in pullback_type else 60
        pullback_lower = st.slider(
            "下限（股價低於均線 %）", -10.0, 0.0, -5.0, 0.5,
            help="負值 = 股價跌破均線幾%。-5% 代表最多允許跌到均線以下 5%"
        )
        pullback_upper = st.slider(
            "上限（股價高於均線 %）", 0.0, 15.0, 10.0, 0.5,
            help="正值 = 股價站在均線上幾%。10% 代表最多允許站在均線以上 10%"
        )
        st.caption(f"📐 篩選範圍：{'MA20' if pullback_ma==20 else 'MA60'} 距離 {pullback_lower:+.1f}% ～ {pullback_upper:+.1f}%")
        st.divider()

        st.markdown("**④ 量縮比例**")
        vol_ratio = st.slider("近3日量 / 20日量 < Y", 0.3, 1.5, 1.0, 0.05,
            help="預設放寬至 1.0（量不放大即可）；寬鬆模式下再×1.3")
        st.divider()

        st.markdown("**⑤ 損益比門檻**")
        min_rr = st.slider("最低 RR", 0.5, 5.0, 1.5, 0.5)
        st.divider()

        st.markdown("### 📋 股票池")
        user_input = st.text_area("股號（每行一個）",
                                   value="\n".join(DEFAULT_STOCK_IDS), height=180)
        raw_ids = re.findall(r'\b(\d{4,5})\b', user_input, re.ASCII)
        seen_s: set[str] = set()
        user_ids: list[str] = []
        for x in raw_ids:
            if x not in seen_s:
                seen_s.add(x); user_ids.append(x)
        st.caption(f"已設定 **{len(user_ids)}** 檔股票")
        st.divider()

        # ── 抓取按鈕（唯一會打 FinMind 的地方）──
        run_btn = st.button("🚀 抓取最新資料", type="primary", use_container_width=True,
                            help="點一次即可，資料會記憶在本頁。調整參數不需再按此按鈕。")

        # 資料狀態顯示
        if has_data:
            fetch_time = st.session_state.get("last_fetch_time", "")
            fetch_cnt  = st.session_state.get("success_cnt", 0)
            st.success(f"✅ 資料已載入 {fetch_cnt} 檔\n{fetch_time}")
            st.caption("⬆️ 調整上方參數即可即時重新篩選，不消耗 API")
        else:
            st.warning("尚無資料，請先按上方按鈕抓取")

        st.divider()
        st.markdown("### ℹ️ FinMind")
        st.caption("Token 存於 Streamlit Secrets")
        used = len(user_ids)
        st.progress(min(used/600, 1.0), text=f"每次抓取消耗 {used}/600 calls")

    # ════════════════════════════════════════════════
    # 主頁面邏輯
    # 核心架構：「抓資料」與「篩選」完全分離
    #
    #  ┌─ run_btn 按下 ─────────────────────────────┐
    #  │  呼叫 FinMind API（唯一消耗 token 的地方）  │
    #  │  結果存入 st.session_state["data_dict"]     │
    #  └────────────────────────────────────────────┘
    #           ↓ 資料存活於整個 session
    #  ┌─ 每次頁面 rerun（含滑動 Slider）───────────┐
    #  │  直接從 session_state 取資料               │
    #  │  重跑 run_filter()（純本地運算，<1秒）      │
    #  │  完全不碰 FinMind                          │
    #  └────────────────────────────────────────────┘
    # ════════════════════════════════════════════════
    params = dict(momentum_days=momentum_days, high_window=high_window,
                  pullback_ma=pullback_ma, pullback_lower=pullback_lower, pullback_upper=pullback_upper,
                  vol_ratio=vol_ratio, min_rr=min_rr)

    # Step A：有按「抓取」按鈕 → 打 FinMind，存入 session_state
    if run_btn:
        pb = st.progress(0, text="⏳ 從 FinMind 抓取資料中（約 1~2 分鐘，之後調參數不需再抓）...")
        with st.spinner(""):
            data, ok, skip = do_fetch(user_ids, token)
        pb.progress(100, text=f"✅ 載入 {ok} 檔完成！調整左側參數即可即時篩選。")
        has_data = True
        time.sleep(0.8)
        pb.empty()

    # Step B：有資料就永遠顯示篩選結果（不管有沒有按按鈕）
    if has_data:
        data = st.session_state["data_dict"]
        ok   = st.session_state["success_cnt"]
        skip = st.session_state["skip_cnt"]

        # 篩選（純本地運算，每次 rerun 都跑，< 1 秒，不打 API）
        result_df, funnel = run_filter(data, params, strict=strict_mode)

        # ── 指標卡片 ──
        k1, k2, k3, k4 = st.columns(4)
        with k1: st.metric("📊 已載入", f"{ok:,} 檔")
        with k2: st.metric("⏭️ 無資料", f"{skip:,} 檔")
        with k3: st.metric("🔓 篩選模式", "嚴格" if strict_mode else "寬鬆")
        with k4: st.metric("🎯 符合條件", f"{len(result_df):,} 檔",
                            delta=f"RR≥{min_rr}" if len(result_df) else None)

        st.divider()

        # ── 條件漏斗分析 ──
        st.markdown("#### 🔬 條件漏斗分析（各條件通過數，幫助你找到調參瓶頸）")
        total = len(data)
        fcols = st.columns(5)
        for i, (cname, cnt) in enumerate(funnel.items()):
            pct = cnt/total*100 if total else 0
            with fcols[i]:
                st.metric(cname, f"{cnt} 檔", delta=f"{pct:.1f}%")

        bottleneck = min(funnel, key=funnel.get)
        bn_cnt = funnel[bottleneck]
        if bn_cnt < 5:
            st.info(
                f"💡 **瓶頸：{bottleneck}**（僅 {bn_cnt} 檔通過）"
                f" → 建議{'切換寬鬆模式' if strict_mode else '放寬該條件參數'}"
            )

        st.divider()

        # ── 結果表格 ──
        if result_df.empty:
            st.warning("⚠️ 無符合個股。請看上方漏斗找瓶頸，或切換寬鬆模式。")
        else:
            st.markdown(f"### 📋 篩選結果 — {len(result_df)} 檔（依 RR 降序）")
            disp = ["代號","名稱","收盤價","漲跌幅(%)","拉回深度(%)","量縮比","停損價","目標價","損益比(RR)","首波拉回"]
            st.dataframe(
                result_df[disp],
                use_container_width=True,
                height=min(580, 45 + 38*len(result_df)),
                column_config={
                    "代號":        st.column_config.TextColumn("代號", width="small"),
                    "名稱":        st.column_config.TextColumn("名稱", width="small"),
                    "收盤價":      st.column_config.NumberColumn("收盤", format="%.2f"),
                    "漲跌幅(%)":   st.column_config.NumberColumn("漲跌", format="%.2f%%"),
                    "拉回深度(%)": st.column_config.NumberColumn("拉回", format="%.2f%%"),
                    "量縮比":      st.column_config.ProgressColumn("量縮比", min_value=0, max_value=1.5, format="%.2f"),
                    "停損價":      st.column_config.NumberColumn("停損", format="%.2f"),
                    "目標價":      st.column_config.NumberColumn("目標", format="%.2f"),
                    "損益比(RR)":  st.column_config.NumberColumn("RR", format="%.2f"),
                    "首波拉回":    st.column_config.TextColumn("首波", width="small"),
                },
                hide_index=True,
            )

            buf = io.StringIO()
            result_df.to_csv(buf, index=False, encoding="utf-8-sig")
            st.download_button("⬇️ 下載 CSV", buf.getvalue(),
                               f"pullback_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                               mime="text/csv")

            st.divider()

            # ── K 線圖 ──
            st.markdown("### 📈 個股 K 線圖")
            opts = [
                f"{r['代號']} {STOCK_NAME_MAP.get(r['代號'], '')}  RR={r['損益比(RR)']}  收={r['收盤價']}"
                for _, r in result_df.iterrows()
            ]
            sel = st.selectbox("選擇個股", opts, index=0)
            idx = opts.index(sel)
            sid = result_df.iloc[idx]["代號"]

            if sid in data:
                st.plotly_chart(kline(data[sid], sid), use_container_width=True)
                row = result_df.iloc[idx]
                ka, kb, kc, kd = st.columns(4)
                with ka: st.metric("收盤", f"${row['收盤價']:.2f}", delta=f"{row['漲跌幅(%)']:.2f}%")
                with kb: st.metric("停損", f"${row['停損價']:.2f}")
                with kc: st.metric("目標", f"${row['目標價']:.2f}")
                with kd: st.metric("RR",  f"{row['損益比(RR)']:.2f}x")

    else:
        # 尚無資料
        st.info("👈 點擊左側「🚀 抓取最新資料」開始，或等待每日 18:00 自動抓取。\n\n"
                "**資料載入一次後，調整任何篩選參數都不會再消耗 FinMind API。**")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"| 參數 | 值 |\n|---|---|\n"
                        f"| 動能回看 N | **{momentum_days}** 天 |\n"
                        f"| 新高窗口 M | **{high_window}** 天 |\n"
                        f"| 拉回基準 | **{'MA20' if pullback_ma==20 else 'MA60'}** |")
        with c2:
            st.markdown(f"| 參數 | 值 |\n|---|---|\n"
                        f"| 拉回範圍 | **{pullback_lower:+.1f}% ～ {pullback_upper:+.1f}%** |\n"
                        f"| 量縮比 Y | **{vol_ratio}** |\n"
                        f"| 最低 RR | **{min_rr}x** |\n"
                        f"| 股票池 | **{len(user_ids)}** 檔 |")

    st.markdown("""<div class="risk-warn">
        ⚠️ 本系統僅供技術分析參考，不構成投資建議。股市有風險，請嚴格執行停損。
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
