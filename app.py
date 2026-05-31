# ==============================================================================
# 台股波段拉回選股工具 v3.2
# 修正：① 動能記憶改用 shift(1)，避免 High 自含偏差
#       ② 新增 MA20 斜率篩選（條件④），確保均線仍向上
#       ③ 停損改用近 10 日擺動低點 × 0.98（最多 10% 幅度）
#       ④ 結果表格新增：距高點天數、今日量/均量、MA20斜率(5日)
#       ⑤ 漏斗改為顯示相對前一關卡通過率
#       ⑥ K 線圖標示停損 / 目標水平線
#       ⑦ 資料抓取改用執行緒池並行（~30 秒，原 2 分鐘）
#       ⑧ 側邊欄按鈕全客製化 (注入 ✨ 展開 / ✖ 摺疊 中文字)
# ==============================================================================

import re
import io
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
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
# ==============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

/* ═══════════════════════════════════════════════
   強制深色：覆蓋 Streamlit 所有預設白色區塊
   ═══════════════════════════════════════════════ */
html, body { background-color: #0a0e1a !important; }

.stApp, .stApp > div, [data-testid="stAppViewContainer"], [data-testid="stAppViewContainer"] > section {
    background-color: #0a0e1a !important; background: #0a0e1a !important;
}

[data-testid="stHeader"], header[data-testid="stHeader"] {
    background-color: transparent !important; background: transparent !important;
    border-bottom: none !important; z-index: 999999 !important; 
}

.stAppDeployButton, [data-testid="stToolbarActions"], [data-testid="stStatusWidget"] { 
    display: none !important; 
}

/* ── sidebar 收起時，header 左上角的展開按鈕（double_arrow_right Material Icon） ──
   Material Icons 是字體渲染，不是 svg，必須用 font-size:0 消除，再用 ::after 補中文  */

/* 把 Material Icon 字體縮成 0（消除 double_arrow_right 文字） */
[data-testid="stSidebarOpenNavButton"] button,
[data-testid="stSidebarOpenNavButton"] button * {
    font-size: 0 !important;
    color: transparent !important;
    visibility: hidden !important;
}
/* 外層容器：藍色按鈕樣式 */
[data-testid="stSidebarOpenNavButton"] {
    background: linear-gradient(135deg, #1d4ed8, #3b82f6) !important;
    border-radius: 8px !important;
    margin: 10px !important;
    padding: 2px !important;
    box-shadow: 0 4px 12px rgba(59,130,246,0.4) !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 90px !important;
    min-height: 36px !important;
    position: relative !important;
    cursor: pointer !important;
}
[data-testid="stSidebarOpenNavButton"]:hover {
    background: linear-gradient(135deg, #2563eb, #60a5fa) !important;
    box-shadow: 0 6px 16px rgba(59,130,246,0.6) !important;
    transform: translateY(-2px) !important;
}
/* 中文注入在外層容器的 ::after（button 內容已清空，不怕遮擋） */
[data-testid="stSidebarOpenNavButton"]::after {
    content: "✨ 展開" !important;
    color: #ffffff !important;
    font-size: 1rem !important;
    font-weight: 700 !important;
    letter-spacing: 2px !important;
    font-family: 'Noto Sans TC', sans-serif !important;
    visibility: visible !important;
    position: absolute !important;
    pointer-events: none !important;
    display: block !important;
}

/* ==========================================================
   ★ 側邊欄展開/摺疊按鈕全客製化 (取代原生英文與圖示) ★
   ========================================================== */

/* ── 共用：隱藏所有按鈕內的 svg / span / p ── */
[data-testid="collapsedControl"] button svg,
[data-testid="collapsedControl"] button span,
[data-testid="collapsedControl"] button p,
[data-testid="stSidebarCollapseButton"] svg,
[data-testid="stSidebarCollapseButton"] span,
[data-testid="stSidebarCollapseButton"] p {
    display: none !important;
    visibility: hidden !important;
}

/* ── 展開按鈕（側邊欄收起時）── */
[data-testid="collapsedControl"] {
    background: transparent !important;
    padding: 0 !important;
    margin: 12px !important;
    position: relative !important;
}
/* 用 text-indent 把原生文字推出視窗，不影響 ::after */
[data-testid="collapsedControl"] button {
    background: linear-gradient(135deg, #1d4ed8, #3b82f6) !important;
    border: none !important;
    border-radius: 8px !important;
    padding: 8px 28px !important;
    box-shadow: 0 4px 12px rgba(59,130,246,0.4) !important;
    cursor: pointer !important;
    transition: all 0.3s ease !important;
    text-indent: -9999px !important;   /* 把原生文字推出去 */
    overflow: hidden !important;
    white-space: nowrap !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    min-width: 90px !important;
    min-height: 36px !important;
    position: relative !important;
}
[data-testid="collapsedControl"] button:hover {
    background: linear-gradient(135deg, #2563eb, #60a5fa) !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(59,130,246,0.6) !important;
}
[data-testid="collapsedControl"] button::after {
    content: "✨ 展開" !important;
    text-indent: 0 !important;        /* 把 ::after 拉回來 */
    color: #ffffff !important;
    font-weight: 700 !important;
    font-size: 1rem !important;
    letter-spacing: 2px !important;
    font-family: 'Noto Sans TC', sans-serif !important;
    position: absolute !important;
    display: block !important;
    pointer-events: none !important;
}

/* ── 摺疊按鈕（側邊欄展開時）── */
[data-testid="stSidebarCollapseButton"] {
    background: rgba(239,68,68,0.15) !important;
    border: none !important;
    border-radius: 6px !important;
    padding: 6px 20px !important;
    cursor: pointer !important;
    transition: all 0.2s !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    text-indent: -9999px !important;   /* 把原生文字推出去 */
    overflow: hidden !important;
    white-space: nowrap !important;
    min-width: 80px !important;
    min-height: 32px !important;
    position: relative !important;
}
[data-testid="stSidebarCollapseButton"]:hover {
    background: rgba(239,68,68,0.4) !important;
}
[data-testid="stSidebarCollapseButton"]::after {
    content: "✖ 摺疊" !important;
    text-indent: 0 !important;        /* 把 ::after 拉回來 */
    color: #f87171 !important;
    font-weight: 700 !important;
    font-size: 0.95rem !important;
    letter-spacing: 1px !important;
    font-family: 'Noto Sans TC', sans-serif !important;
    position: absolute !important;
    display: block !important;
    pointer-events: none !important;
}
/* ========================================================== */

.block-container { padding-top: 3rem !important; padding-bottom: 2rem !important; }
[data-testid="stMain"], [data-testid="block-container"], .main .block-container { background-color: #0a0e1a !important; max-width: 100% !important; }
html, body, [class*="css"], p, span, div, label, h1, h2, h3, h4 { font-family: 'Noto Sans TC', sans-serif !important; color: #e2e8f0; }

[data-testid="stSidebar"], [data-testid="stSidebar"] > div { background: #0d1829 !important; border-right: 1px solid rgba(59,130,246,0.15) !important; }
[data-testid="stSidebarUserContent"] { padding-top: 0 !important; }
[data-testid="stSidebar"] p, [data-testid="stSidebar"] span, [data-testid="stSidebar"] label, [data-testid="stSidebar"] div { color: #cbd5e1 !important; }
[data-testid="stSidebar"] .stMarkdown h3 { color: #60a5fa !important; font-size: 0.85rem !important; text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 1px solid rgba(59,130,246,0.2); padding-bottom: 6px; margin-top: 4px; }

[data-testid="stSlider"] label { color: #94a3b8 !important; font-size: 0.82rem !important; }
[data-testid="stSlider"] p { color: #60a5fa !important; font-weight: 700 !important; }
[data-testid="stRadio"] label { color: #94a3b8 !important; }
[data-testid="stRadio"] div[role="radiogroup"] p { color: #e2e8f0 !important; }

textarea { background-color: #0f1c30 !important; color: #e2e8f0 !important; border: 1px solid rgba(59,130,246,0.25) !important; border-radius: 8px !important; }
[data-testid="stCaptionContainer"] p, small, .stCaption { color: #64748b !important; }
hr { border-color: rgba(59,130,246,0.15) !important; margin: 10px 0 !important; }

.stButton > button { background: linear-gradient(135deg, #1d4ed8, #1e40af) !important; color: #fff !important; border: none !important; border-radius: 8px !important; font-weight: 600 !important; padding: 10px 24px !important; width: 100% !important; transition: all 0.2s ease !important; }
.stButton > button:hover { background: linear-gradient(135deg, #2563eb, #1d4ed8) !important; transform: translateY(-1px) !important; box-shadow: 0 4px 15px rgba(59,130,246,0.35) !important; }

[data-testid="stProgressBar"] > div { background: rgba(59,130,246,0.15) !important; border-radius: 4px; }
[data-testid="stProgressBar"] > div > div { background: linear-gradient(90deg,#3b82f6,#60a5fa) !important; }
[data-testid="stDataFrame"] { border: 1px solid rgba(59,130,246,0.18) !important; border-radius: 10px !important; }
[data-testid="stAlert"] { border-radius: 8px !important; }

[data-testid="stSelectbox"] div[data-baseweb="select"] > div { background-color: #0f1c30 !important; border-color: rgba(59,130,246,0.25) !important; color: #e2e8f0 !important; }
body [data-baseweb="popover"], body [data-baseweb="menu"], body ul[role="listbox"] { background-color: #1e293b !important; border: 1px solid rgba(59,130,246,0.3) !important; }
body [data-baseweb="menu"] li, body [data-baseweb="list-item"], body ul[role="listbox"] li, body [role="option"] { background-color: #1e293b !important; color: #e2e8f0 !important; }
body [role="option"]:hover, body [data-baseweb="menu"] li:hover { background-color: #2d4a7a !important; color: #ffffff !important; }
body [aria-selected="true"][role="option"] { background-color: #1d4ed8 !important; color: #ffffff !important; }

body [data-baseweb="tooltip"], body [role="tooltip"], div[data-baseweb="tooltip"] div, [data-testid="stTooltipHoverTarget"] + div, body [class*="Tooltip"], body [class*="tooltip"] { background-color: #1e293b !important; color: #e2e8f0 !important; border: 1px solid rgba(59,130,246,0.35) !important; border-radius: 6px !important; font-size: 0.82rem !important; box-shadow: 0 4px 16px rgba(0,0,0,0.5) !important; }
body [data-baseweb="tooltip"] [data-popper-arrow]::before, body [role="tooltip"] [data-popper-arrow]::before { border-color: #1e293b !important; }

.hero-header { background: linear-gradient(120deg, #1a2744 0%, #162038 45%, #1e1035 100%); border: 1px solid rgba(59,130,246,0.28); border-radius: 16px; padding: 26px 34px; margin-bottom: 18px; position: relative; overflow: hidden; }
.hero-header::before { content: ''; position: absolute; top: -50px; right: -50px; width: 180px; height: 180px; background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%); border-radius: 50%; pointer-events: none; }
.hero-title { font-size: 2rem; font-weight: 900; background: linear-gradient(90deg, #60a5fa 0%, #f87171 55%, #fbbf24 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; margin: 0 0 6px 0; }
.hero-subtitle { color: #94a3b8 !important; font-size: 0.9rem; margin: 0; }

.sched-card { background: #0f1e33; border: 1px solid rgba(34,197,94,0.28); border-radius: 10px; padding: 12px 16px; height: 70px; }
.sched-card.warn { border-color: rgba(251,191,36,0.38); }
.sched-lbl { color: #475569; font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px; }
.sched-val { color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-size: 0.92rem; font-weight: 600; }
.sched-val.green { color: #22c55e; }
.sched-val.amber { color: #fbbf24; }

.strat-info { background: linear-gradient(135deg, #172035, #1c2a48); border-left: 3px solid #3b82f6; border-radius: 8px; padding: 14px 18px; margin-bottom: 14px; font-size: 0.86rem; color: #94a3b8; line-height: 1.75; }
.strat-info strong { color: #60a5fa; }

.funnel-card { background: #0f1e33; border: 1px solid rgba(59,130,246,0.18); border-radius: 10px; padding: 14px 18px; font-size: 0.83rem; }
.funnel-row { display: flex; align-items: center; justify-content: space-between; padding: 5px 0; border-bottom: 1px solid rgba(59,130,246,0.08); color: #94a3b8; }
.funnel-row:last-child { border-bottom: none; }
.funnel-pass { color: #22c55e; font-weight: 700; font-family: 'JetBrains Mono', monospace; }
.funnel-label { color: #64748b; font-size: 0.78rem; }

.risk-warn { background: linear-gradient(135deg, #1f1510, #2d1b0e); border: 1px solid rgba(251,191,36,0.3); border-radius: 8px; padding: 12px 18px; margin-top: 22px; margin-bottom: 14px; color: #fbbf24; font-size: 0.8rem; text-align: center; }
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

# K 線分析網址（帶入 ?stock=代號 可自動填入並分析）
KLINE_BASE_URL = "https://flydav003-alt.github.io/k-line/"

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


_RENAME = {
    "date": "Date", "open": "Open",
    "max": "High", "min": "Low",
    "close": "Close",
    "Trading_Volume": "Volume",
    "trading_volume": "Volume",
}
_NEED = ["Open", "High", "Low", "Close", "Volume"]


def _fetch_one(sid: str, start: str, end: str, token: str):
    """單支股票抓取，供 ThreadPoolExecutor 並行呼叫"""
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
            return sid, None
        df = pd.DataFrame(pl["data"]).rename(columns=_RENAME)
        if not all(col in df.columns for col in ["Date"] + _NEED):
            return sid, None
        df["Date"] = pd.to_datetime(df["Date"])
        df = df.set_index("Date").sort_index()
        df = df[_NEED].apply(pd.to_numeric, errors="coerce").dropna(subset=["Close"])
        if len(df) >= 100:
            return sid, df
        return sid, None
    except Exception:
        return sid, None


def fetch_prices(ids: list[str], start: str, end: str, token: str) -> dict[str, pd.DataFrame]:
    """
    並行呼叫 FinMind TaiwanStockPrice，回傳 dict[stock_id -> OHLCV DataFrame]
    ThreadPoolExecutor max_workers=5，避免 FinMind 限流；速度從 ~2 分鐘降至 ~30 秒
    """
    result: dict[str, pd.DataFrame] = {}
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = {ex.submit(_fetch_one, sid, start, end, token): sid for sid in ids}
        for f in as_completed(futures):
            sid, df = f.result()
            if df is not None:
                result[sid] = df
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


def rsi(s: pd.Series, w: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / w, adjust=False, min_periods=w).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / w, adjust=False, min_periods=w).mean()
    rs = gain / loss.replace(0, np.nan)
    return (100 - 100 / (1 + rs)).fillna(100)


def is_volume_decreasing(v: pd.Series) -> bool:
    last3 = v.iloc[-4:-1]
    if len(last3) < 3 or last3.isna().any():
        return False
    return bool(last3.iloc[0] > last3.iloc[1] > last3.iloc[2])


def bullish_body_ratio(df: pd.DataFrame) -> float:
    o0 = df["Open"].iloc[-1]
    h0 = df["High"].iloc[-1]
    l0 = df["Low"].iloc[-1]
    c0 = df["Close"].iloc[-1]
    day_range = h0 - l0
    if pd.isna(day_range) or day_range <= 0 or c0 <= o0:
        return 0.0
    return float((c0 - o0) / day_range)


# ==============================================================================
# ── 6. 篩選策略（含條件漏斗統計）
#
#  條件 ①~⑥：
#    ④ 均線斜率%：MA20看近5日百分比變化；MA60看近10日百分比變化
#  「寬鬆模式」（strict=False）：
#    ⑤ 量縮：放寬為 < vol_ratio * 1.3
#    ⑥ 止跌轉折：今收 > 昨高  OR  今收站回 MA20（MA20 站回也算）
#
#  同時回傳各條件通過數，方便 UI 顯示漏斗分析
# ==============================================================================
def run_filter(
    data: dict[str, pd.DataFrame],
    p: dict,
    strict: bool = True,
    stage: str = "entry",
) -> tuple[pd.DataFrame, dict]:
    """
    回傳 (result_df, funnel_counts)
    funnel_counts = {條件名: 通過數}  — 6 個關卡（含新增的 ④ MA20斜率）
    """
    funnel = {
        "① 長線多頭": 0,
        "② 動能記憶": 0,
        "③ 波段拉回": 0,
        "③+ 回踩確認": 0,
        "④ 均線斜率%": 0,
        "⑤ 量縮洗盤": 0,
        "⑤+ 轉強量能": 0,
        "⑥ 止跌轉折": 0,
        "⑦ 其他條件": 0,
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
            ma5_s   = sma(c, 5)
            ma10_s  = sma(c, 10)
            ma50_s  = sma(c, 50)
            ma60_s  = sma(c, 60)
            ma200_s = sma(c, 200)
            atr14   = atr(df, 14)

            c0, c1  = c.iloc[-1], c.iloc[-2]
            h1      = h.iloc[-2]
            ma5_0   = ma5_s.iloc[-1];   ma5_1  = ma5_s.iloc[-2]  if len(ma5_s)  >= 2 else np.nan
            ma10_0  = ma10_s.iloc[-1];  ma10_1 = ma10_s.iloc[-2] if len(ma10_s) >= 2 else np.nan
            ma20_0  = ma20_s.iloc[-1];  ma20_1 = ma20_s.iloc[-2] if len(ma20_s) >= 2 else np.nan
            ma50_0  = ma50_s.iloc[-1]
            ma60_0  = ma60_s.iloc[-1]
            ma200_0 = ma200_s.iloc[-1]
            atr_0   = atr14.iloc[-1]

            if any(pd.isna([c0, c1, h1, ma5_0, ma5_1, ma10_0, ma10_1,
                            ma20_0, ma20_1, ma50_0, ma60_0, ma200_0, atr_0])):
                continue

            # ① 長線多頭
            if not (ma50_0 > ma200_0 and c0 > ma200_0):
                continue
            funnel["① 長線多頭"] += 1

            # ② 動能記憶（修正：shift(1) 取前一日的 M 日最高，排除當天 High 自含偏差）
            N, M = p["momentum_days"], p["high_window"]
            prior_M_high = h.rolling(M).max().shift(1)   # 昨天為止的 M 日最高
            recent_sl    = slice(-(N + 1), -1)
            if not (c.iloc[recent_sl] >= prior_M_high.iloc[recent_sl]).any():
                continue
            funnel["② 動能記憶"] += 1

            # ③ 波段拉回 — 基準均線 + 可選站回MA5/MA10
            pullback_mode = p.get("pullback_mode", "回踩MA20")
            pullback_ma   = p.get("pullback_ma", 20)
            use_ma5       = p.get("use_ma5", False)
            use_ma10      = p.get("use_ma10", False)

            # 基準均線距離判斷（所有模式都要過）
            if pullback_mode == "回踩MA60":
                ma_ref = ma60_0
                ma_ref_1 = ma60_s.iloc[-2] if len(ma60_s) >= 2 else np.nan
                ma_ref_series = ma60_s
                if pd.isna(ma_ref) or ma_ref == 0:
                    continue
            else:
                ma_ref = ma20_0
                ma_ref_1 = ma20_1
                ma_ref_series = ma20_s

            close_dist = (c0 - ma_ref) / ma_ref * 100
            pb_window = max(1, p.get("touch_window", 5))
            low_dist_series = (l.iloc[-pb_window:] - ma_ref_series.iloc[-pb_window:]) / ma_ref_series.iloc[-pb_window:] * 100
            pullback_low_dist = low_dist_series.min()

            # 收盤要站回基準均線；近期低點允許小幅跌破均線，避免錯過假跌破後收回的波段買點。
            if not (c0 >= ma_ref and close_dist <= p["pullback_upper"]):
                continue
            if pd.isna(pullback_low_dist) or pullback_low_dist < p["pullback_lower"]:
                continue
            dist = pullback_low_dist

            # 站回MA5（可選，AND條件）— 今收在 MA5 上方即可
            if use_ma5:
                if pd.isna(ma5_0):
                    continue
                if not (c0 > ma5_0):
                    continue

            # 站回MA10（可選，AND條件）— 今收在 MA10 上方即可
            if use_ma10:
                if pd.isna(ma10_0):
                    continue
                if not (c0 > ma10_0):
                    continue

            funnel["③ 波段拉回"] += 1

            # ③+ 回踩確認（可選）
            touch_enabled = p.get("touch_enabled", True)
            if touch_enabled:
                touch_window = p.get("touch_window", 5)
                touch_tol    = p.get("touch_tol", 3.0)
                # 回踩確認的均線：MA20/MA60回踩用所選均線；MA5/MA10站回用MA20
                if pullback_mode == "回踩MA60":
                    ma_ref_series = ma60_s
                else:
                    ma_ref_series = ma20_s
                window_low      = l.iloc[-touch_window:]
                window_ma       = ma_ref_series.iloc[-touch_window:]
                touch_threshold = window_ma * (1 + touch_tol / 100)
                touched = (window_low <= touch_threshold).any()
                if not touched:
                    continue
            funnel["③+ 回踩確認"] += 1

            # ④ 均線斜率（正規化百分比；MA60模式看10日，其餘看MA20近5日）
            if pullback_mode == "回踩MA60":
                slope_base = ma60_s.iloc[-11] if len(ma60_s) >= 11 else np.nan
                slope_val = (ma60_0 / slope_base - 1) * 100 if slope_base and not pd.isna(slope_base) else 0.0
            else:
                slope_base = ma20_s.iloc[-6] if len(ma20_s) >= 6 else np.nan
                slope_val = (ma20_0 / slope_base - 1) * 100 if slope_base and not pd.isna(slope_base) else 0.0
            if slope_val < p.get("ma_slope_pct_min", 0.0):
                continue
            if p.get("use_rsi_filter", False):
                rsi_s = rsi(c, 14)
                rsi_0 = rsi_s.iloc[-1]
                if pd.isna(rsi_0) or not (p.get("rsi_min", 35.0) <= rsi_0 <= p.get("rsi_max", 65.0)):
                    continue
                if p.get("rsi_require_rebound", False):
                    lookback = max(2, int(p.get("rsi_rebound_lookback", 5)))
                    recent_rsi = rsi_s.iloc[-lookback:]
                    if recent_rsi.isna().all() or recent_rsi.min() > p.get("rsi_rebound_min", 40.0):
                        continue
                    if rsi_0 < p.get("rsi_rebound_confirm", 45.0):
                        continue
            funnel["④ 均線斜率%"] += 1

            # ⑤ 量縮洗盤
            v3  = v.iloc[-4:-1].mean()
            v20 = v.iloc[-21:-1].mean()
            if pd.isna(v3) or pd.isna(v20) or v20 == 0:
                continue
            vs = v3 / v20
            if vs >= vol_limit:
                continue
            if p.get("require_volume_decreasing", False) and not is_volume_decreasing(v):
                continue
            funnel["⑤ 量縮洗盤"] += 1

            # ⑤+ 今日轉強量能：拉回時量縮，但觸發日不能完全沒量，也避免爆量追高。
            v0_val = v.iloc[-1]
            vol_today_ratio = v0_val / v20 if v20 > 0 else 0.0
            volume_rebound = p.get("today_vol_min", 0.6) <= vol_today_ratio < p.get("today_vol_max", 2.0)
            if stage == "entry" and not volume_rebound:
                continue
            if volume_rebound:
                funnel["⑤+ 轉強量能"] += 1

            # ⑥ 止跌轉折
            # 嚴格：今收 > 昨高
            # 寬鬆：今收 > 昨高  OR  今收站回所選均線（今收 > ma_ref 且昨收 < 昨日ma_ref）
            if pullback_mode == "回踩MA60":
                reversal_loose = (c0 > h1) or (
                    not pd.isna(ma_ref_1) and c0 > ma60_0 and c1 < ma_ref_1
                )
            else:
                reversal_loose = (c0 > h1) or (
                    not pd.isna(ma20_1) and c0 > ma20_0 and c1 < ma20_1
                )
            reversal_strict = (c0 > h1)
            passed_reversal = reversal_strict if strict else reversal_loose
            if stage == "entry" and not passed_reversal:
                continue
            body_ratio = bullish_body_ratio(df)
            if (
                stage == "entry"
                and p.get("use_bullish_body", True)
                and body_ratio < p.get("bullish_body_min_ratio", 0.30)
            ):
                continue
            if passed_reversal:
                funnel["⑥ 止跌轉折"] += 1

            # 第一波拉回判斷（優化版）
            # 計算從高點後的拉回次數，只有一次（或仍在首次拉回附近）才標為首波
            first = False
            try:
                peak_idx    = h.iloc[-M:].idxmax()
                peak_pos    = df.index.get_loc(peak_idx)
                current_pos = len(df) - 1

                pullback_count = 0
                first_pull_pos = None

                # 從高點後一根掃到昨天（不含今天，避免把當前這次算進去）
                for pos in range(peak_pos + 1, current_pos):
                    ci   = c.iloc[pos]
                    ma_i = ma_ref_series.iloc[pos]
                    if pd.isna(ci) or pd.isna(ma_i) or ma_i == 0:
                        continue
                    dist_i = (ci - ma_i) / ma_i * 100
                    if p["pullback_lower"] <= dist_i <= p["pullback_upper"]:
                        pullback_count += 1
                        if first_pull_pos is None:
                            first_pull_pos = pos

                # 從未拉回過 → 這次是首波
                if pullback_count == 0:
                    first = True
                # 只有一次拉回且距今 ≤ 8 個交易日 → 視為仍在首波區
                elif pullback_count == 1 and (current_pos - first_pull_pos <= 8):
                    first = True
                else:
                    first = False
            except Exception:
                first = False  # 無法判斷時保守標為非首波

            # ── 停損：兩層合併（結構前低 + 均線），ATR緩衝 ──
            if p.get("force_first_wave", False) and not first:
                continue

            atr_buf_mult = p.get("atr_buf", 0.5)
            buf          = atr_0 * atr_buf_mult

            swing_window  = p.get("swing_window", 20)
            swing_low     = l.iloc[-swing_window:].min()
            stop_structure = swing_low - buf                      # 前低下方一個緩衝
            stop_ma        = ma_ref - buf                         # 所選均線下方一個緩衝
            stop           = max(stop_structure, stop_ma)         # 取較高（較緊）
            stop           = max(stop, c0 * (1 - p.get("max_stop_pct", 0.10)))

            # ── 止盈：斐波那契延伸（比例由側欄參數決定）──
            # swing_high / swing_low 統一用波段窗口，振幅一致，目標價不偏移
            swing_high = h.iloc[-swing_window:].max()
            amp        = swing_high - swing_low
            fib_t1     = p.get("fib_t1", 0.272)
            fib_t2     = p.get("fib_t2", 0.618)
            target_t1  = round(swing_high + amp * fib_t1, 2)
            target_t2  = round(swing_high + amp * fib_t2, 2)

            # RR 用保守目標 T1 計算，不高估
            risk   = c0 - stop
            reward = target_t1 - c0
            rr     = round(reward / risk, 2) if risk > 0 else 0.0
            if rr < p["min_rr"]:
                continue
            funnel["⑦ 其他條件"] += 1

            # ── 附加欄位 ──
            # 距高點天數：型態新鮮度指標
            try:
                high_idx       = h.iloc[-M:].idxmax()
                days_from_high = int((df.index[-1] - high_idx).days)
            except Exception:
                days_from_high = 0

            results.append({
                "代號":          sid,
                "名稱":          STOCK_NAME_MAP.get(sid, ""),
                "收盤價":        round(c0, 2),
                "漲跌幅(%)":     round((c0 - c1) / c1 * 100, 2) if c1 else 0,
                "拉回深度(%)":   round(dist, 2),
                "量縮比":        round(vs, 2),
                "今日量/均量":   round(vol_today_ratio, 2),
                "均線斜率%":      round(slope_val, 2),
                "轉折確認":      "✅" if passed_reversal and volume_rebound else "觀察",
                "距高點天數":    days_from_high,
                "停損價":        round(stop, 2),
                "目標T1":        target_t1,
                "目標T2":        target_t2,
                "空間%":         round((target_t1 - c0) / c0 * 100, 1) if c0 > 0 else 0,
                "損益比(RR)":    rr,
                "首波拉回":      "✅" if first else "—",
                "MA20":          round(ma20_0, 2),
                "MA60":          round(ma60_0, 2),
                "MA200":         round(ma200_0, 2),
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
def kline(df: pd.DataFrame, sid: str,
          stop_price: float | None = None,
          target_t1: float | None = None,
          target_t2: float | None = None) -> go.Figure:
    df = df.copy().sort_index().tail(250)
    df["MA5"]   = sma(df["Close"], 5)
    df["MA10"]  = sma(df["Close"], 10)
    df["MA20"]  = sma(df["Close"], 20)
    df["MA60"]  = sma(df["Close"], 60)
    df["MA200"] = sma(df["Close"], 200)

    # ── 布林通道（20日，2倍標準差）──
    bb_period = 20
    df["BB_mid"]   = df["Close"].rolling(bb_period).mean()
    bb_std         = df["Close"].rolling(bb_period).std()
    df["BB_upper"] = df["BB_mid"] + 2 * bb_std
    df["BB_lower"] = df["BB_mid"] - 2 * bb_std

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

    # ── 均線（點 Legend 可切換；MA5/MA10 預設隱藏）──
    for col_name, clr, w, dash in [
        ("MA5",  "#a78bfa", 1.2, "solid"),
        ("MA10", "#60a5fa", 1.5, "solid"),
        ("MA20", "#fb923c", 1.5, "solid"),
        ("MA60", "#34d399", 1.8, "solid"),
        ("MA200","#f43f5e", 2.0, "dot"),
    ]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col_name],
            line=dict(color=clr, width=w, dash=dash),
            name=col_name,
            legendgroup=col_name,
            visible="legendonly" if col_name in ("MA5", "MA10") else True,
        ), row=1, col=1)

    # ── 布林通道（只顯示上軌 + 下軌，合一 legend 項目「BB」，黃色虛線；預設隱藏）──
    bb_clr = "#facc15"  # 黃色
    # 上軌（showlegend=True，legend 顯示 "BB"）
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_upper"],
        line=dict(color=bb_clr, width=1.2, dash="dash"),
        name="BB",
        legendgroup="BB",
        showlegend=True,
        visible="legendonly",
    ), row=1, col=1)
    # 下軌（同 legendgroup，不重複顯示 legend 項目）
    fig.add_trace(go.Scatter(
        x=df.index, y=df["BB_lower"],
        line=dict(color=bb_clr, width=1.2, dash="dash"),
        name="BB",
        legendgroup="BB",
        showlegend=False,
        visible="legendonly",
    ), row=1, col=1)

    fig.add_trace(go.Bar(x=df.index, y=df["Volume"],
                         marker_color=colors, name="量", opacity=0.72), row=2, col=1)

    # ── 停損 / 目標水平線 ──
    if stop_price is not None:
        fig.add_hline(
            y=stop_price, row=1, col=1,
            line=dict(color="#ef4444", width=1.5, dash="dot"),
            annotation_text=f"⛔ 停損 {stop_price:.2f}",
            annotation_position="bottom right",
            annotation_font=dict(color="#ef4444", size=10),
        )
    if target_t1 is not None:
        fig.add_hline(
            y=target_t1, row=1, col=1,
            line=dict(color="#22c55e", width=1.5, dash="dot"),
            annotation_text=f"🎯 T1 {target_t1:.2f}",
            annotation_position="top right",
            annotation_font=dict(color="#22c55e", size=10),
        )
    if target_t2 is not None:
        fig.add_hline(
            y=target_t2, row=1, col=1,
            line=dict(color="#a78bfa", width=1.5, dash="dash"),
            annotation_text=f"🚀 T2 {target_t2:.2f}",
            annotation_position="top right",
            annotation_font=dict(color="#a78bfa", size=10),
        )

    fig.update_layout(
        height=580, paper_bgcolor="#0a0e1a", plot_bgcolor="#0a0e1a",
        font=dict(color="#e2e8f0", size=12, family="Noto Sans TC"),
        legend=dict(orientation="h", yanchor="top", y=0.99,
                    xanchor="left", x=0, bgcolor="rgba(10,14,26,0.75)",
                    bordercolor="rgba(59,130,246,0.2)", borderwidth=1,
                    font=dict(color="#e2e8f0", size=12)),
        xaxis_rangeslider_visible=False,
        margin=dict(l=8, r=8, t=38, b=8),
    )
    fig.update_xaxes(gridcolor="rgba(59,130,246,0.07)", linecolor="rgba(59,130,246,0.2)",
                     tickfont=dict(color="#e2e8f0"))
    fig.update_yaxes(gridcolor="rgba(59,130,246,0.07)", linecolor="rgba(59,130,246,0.2)",
                     tickfont=dict(color="#e2e8f0"))
    for ann in fig.layout.annotations:
        ann.font.update(color="#cbd5e1", size=12)
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


    # ════════════════════════════════════════════════
    # SIDEBAR
    # ════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("### ⚙️ 策略參數")

        st.markdown("**① 長線多頭**")
        st.caption("MA50 > MA200 且 Close > MA200（固定）")
        st.divider()

        st.markdown("**② 動能記憶**",
            help="近N日內，收盤價是否曾突破前M日最高價。用來確認這支股票近期有過強勢動能，不是一路緩跌的弱勢股。N=回看多久、M=定義『高點』的窗口。")
        momentum_days = st.slider("回看天數 N", 5, 60, 25, 5,
            help="往回看幾天內有沒有出現過突破前高。25日=近一個月內曾創M日新高即符合")
        high_window   = st.slider("新高窗口 M（天）", 20, 120, 60, 5,
            help="『前高』的定義窗口。60日=前60日最高價。M越大代表要突破越長期的高點，條件越嚴")
        st.divider()

        st.markdown("**③ 波段拉回 — 買點模式**")

        # MA20 / MA60 回踩：單選
        pullback_base = st.radio(
            "回踩基準均線",
            ["回踩MA20", "回踩MA60"],
            index=0, horizontal=True,
            help="回踩MA20：短波段（今收在MA20上方0~上限%） | 回踩MA60：大波段季線（今收在MA60上方0~上限%）"
        )

        # MA5 / MA10 站回：獨立開關，可同時啟用
        st.caption("站回確認（可複選）")
        use_ma5  = st.toggle("站回MA5",  value=False,
            help="今收 > MA5，確認目前站在5日線上方。可與站回MA10同時開啟（AND條件）")
        use_ma10 = st.toggle("站回MA10", value=False,
            help="今收 > MA10，確認目前站在10日線上方。可與站回MA5同時開啟（AND條件）")
        if use_ma5 and use_ma10:
            st.caption("📐 同時要求今收 > MA5 AND 今收 > MA10（最嚴格，確認完整站回）")
        elif use_ma5:
            st.caption("📐 要求今收 > MA5")
        elif use_ma10:
            st.caption("📐 要求今收 > MA10")

        # 距離上限
        pullback_lower = st.slider(
            "回踩低點允許跌破均線 %", -5.0, 1.0, -2.0, 0.5,
            help="看近期低點是否小破均線。-2%=允許 Low 跌到均線下方2%以內，但今日收盤仍必須站回基準均線"
        )
        pullback_upper = st.slider(
            "距基準均線上方最大距離 %", 0.5, 15.0, 8.0, 0.5,
            help="今日收盤距所選均線（MA20或MA60）不超過此值。站回MA5/MA10時同樣套用此前提，確保還在均線附近"
        )

        # 從設定推導內部參數
        pullback_ma    = 60 if pullback_base == "回踩MA60" else 20
        pullback_mode  = pullback_base  # 向後相容

        if pullback_base == "回踩MA20":
            st.caption(f"📐 近期低點可到 MA20 {pullback_lower:.1f}%；今收需站回 MA20 且不高於 +{pullback_upper:.1f}%")
        else:
            st.caption(f"📐 近期低點可到 MA60 {pullback_lower:.1f}%；今收需站回 MA60 且不高於 +{pullback_upper:.1f}%")


        st.markdown("**③+ 回踩確認**")
        touch_enabled = st.toggle("啟用回踩確認", value=True,
            help="開啟後：要求近N日內Low曾貼近均線，確保真的發生過回踩動作，而非一直飄在均線上方")
        st.caption("🟢 開啟 = 必須有回踩動作｜⚪ 關閉 = 只看今日位置")
        if touch_enabled:
            touch_window = st.slider("回踩偵測窗口（日）", 3, 20, 5, 1,
                help="往回看幾天內有沒有發生回踩。5日=近一週；10日=近兩週")
            touch_tol = st.slider("回踩容忍度（%）", 0.0, 5.0, 3.0, 0.5,
                help="Low 距均線多近算回踩。3%=Low曾進入均線上方3%以內（含跌破均線）即算")
            st.caption(f"📐 近 {touch_window} 日內，Low ≤ 均線 × (1 + {touch_tol:.1f}%)")
        else:
            touch_window = 5
            touch_tol    = 3.0
        st.divider()

        st.markdown("**④ 均線斜率（均線方向）**")
        slope_label = "MA60 近10日" if pullback_mode == "回踩MA60" else "MA20 近5日"
        ma_slope_pct_min = st.slider(
            f"{slope_label} 最小斜率 %", -5.0, 5.0, 0.0, 0.1,
            help="正規化百分比斜率。MA20=(今日MA20/5日前MA20-1)*100；MA60=(今日MA60/10日前MA60-1)*100"
        )
        st.caption(f"📐 {slope_label} 斜率% < {ma_slope_pct_min:.1f}% 則排除")
        st.divider()

        st.markdown("**⑤ 量縮比例**")
        vol_ratio = st.slider("近3日量 / 20日量 < Y", 0.3, 1.5, 1.0, 0.05,
            help="預設放寬至 1.0（量不放大即可）；寬鬆模式下再×1.3")
        st.markdown("**⑤+ 今日轉強量能**")
        today_vol_min = st.slider("今日量 / 20日量 下限", 0.0, 2.0, 0.6, 0.1,
            help="避免轉折日完全沒量。0.6=今日量至少達20日均量的60%")
        today_vol_max = st.slider("今日量 / 20日量 上限", 0.8, 5.0, 2.0, 0.1,
            help="避免爆大量追高。2.0=今日量低於20日均量2倍")
        st.divider()

        strict_mode = st.toggle("⑥ 嚴格模式（止跌轉折）", value=True,
            help="開啟：今收 > 昨高（突破昨日高點，確定吃掉賣壓）。關閉：今收站回均線（今收 > MA20，且昨收還在 MA20 以下），量縮門檻放寬×1.3")
        st.caption("🔒 嚴格 = 今收>昨高 + 量縮<Y\n🔓 寬鬆 = 多接受站回所選均線（MA20/MA60依你的買點模式）+ 量縮放寬")
        st.divider()

        st.markdown("**⑦ 其他條件**")
        require_volume_decreasing = st.toggle("強化量縮：近3日量遞減", value=False,
            help="近3日量需逐日下降，作為更嚴格的量縮確認。")
        use_bullish_body = st.toggle("轉折日需陽線實體", value=True,
            help="進場觸發日需收盤大於開盤，避免十字星或猶豫K。")
        bullish_body_min_ratio = st.slider("陽線實體 / 日振幅 >=", 0.10, 0.80, 0.30, 0.05,
            help="0.30 代表陽線實體至少佔當日高低振幅 30%。")
        force_first_wave = st.toggle("只做首波拉回", value=False,
            help="啟用後，只保留首波拉回或仍在首波區附近的股票。")
        use_rsi_filter = st.toggle("啟用 RSI 篩選", value=False,
            help="RSI 用本地收盤價計算，不額外消耗 API。")
        if use_rsi_filter:
            rsi_min, rsi_max = st.slider("RSI(14) 區間", 10.0, 90.0, (35.0, 65.0), 1.0)
            rsi_require_rebound = st.toggle("RSI 需曾超賣後轉強", value=False,
                help="近幾日曾低於門檻，且今日重新站上確認值。")
            if rsi_require_rebound:
                rsi_rebound_lookback = st.slider("RSI 回看日數", 3, 10, 5, 1)
                rsi_rebound_min = st.slider("回看期曾低於", 20.0, 50.0, 40.0, 1.0)
                rsi_rebound_confirm = st.slider("今日 RSI 至少", 30.0, 60.0, 45.0, 1.0)
            else:
                rsi_rebound_lookback = 5
                rsi_rebound_min = 40.0
                rsi_rebound_confirm = 45.0
        else:
            rsi_min, rsi_max = 35.0, 65.0
            rsi_require_rebound = False
            rsi_rebound_lookback = 5
            rsi_rebound_min = 40.0
            rsi_rebound_confirm = 45.0
        st.divider()

        min_rr = st.slider("最低 RR", 0.5, 5.0, 1.5, 0.5,
            help="損益比低於此值的股票不顯示。RR=1.5 代表潛在獲利是潛在虧損的1.5倍")
        atr_buf = st.slider("停損 ATR 緩衝倍數", 0.3, 1.5, 0.8, 0.1,
            help="停損線 = 前低（或均線）再往下 N 倍ATR。倍數越大停損越寬，越不容易被假跌破洗出去。預設0.8")
        max_stop_pct = st.slider("最大停損幅度 %", 5.0, 20.0, 10.0, 0.5,
            help="停損硬上限。10%=不允許停損距離超過買價10%")
        swing_window = st.slider("波段計算窗口（日）", 10, 60, 30, 5,
            help="用來計算前高、前低與目標價。大波段可拉到30~40")
        fib_t1 = st.slider("T1延伸比例", 0.1, 0.8, 0.382, 0.01,
            help="T1=前高+振幅×比例。0.382較適合波段第一段止盈")
        fib_t2 = st.slider("T2延伸比例", 0.3, 1.2, 1.0, 0.01,
            help="T2=前高+振幅×比例。1.0較適合波段第二段目標")
        st.caption(f"📐 停損緩衝 = ATR(14) × {atr_buf}；最大停損 {max_stop_pct:.1f}%；窗口 {swing_window} 日")
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
                  pullback_mode=pullback_mode,
                  pullback_ma=pullback_ma, pullback_lower=pullback_lower, pullback_upper=pullback_upper,
                  use_ma5=use_ma5, use_ma10=use_ma10,
                  vol_ratio=vol_ratio, min_rr=min_rr, atr_buf=atr_buf,
                  ma_slope_pct_min=ma_slope_pct_min,
                  today_vol_min=today_vol_min, today_vol_max=today_vol_max,
                  use_bullish_body=use_bullish_body,
                  bullish_body_min_ratio=bullish_body_min_ratio,
                  force_first_wave=force_first_wave,
                  use_rsi_filter=use_rsi_filter,
                  rsi_min=rsi_min, rsi_max=rsi_max,
                  rsi_require_rebound=rsi_require_rebound,
                  rsi_rebound_lookback=rsi_rebound_lookback,
                  rsi_rebound_min=rsi_rebound_min,
                  rsi_rebound_confirm=rsi_rebound_confirm,
                  require_volume_decreasing=require_volume_decreasing,
                  max_stop_pct=max_stop_pct / 100, swing_window=swing_window,
                  fib_t1=fib_t1, fib_t2=fib_t2,
                  touch_enabled=touch_enabled, touch_window=touch_window, touch_tol=touch_tol)

    # Step A：有按「抓取」按鈕 → 打 FinMind，存入 session_state
    if run_btn:
        pb = st.progress(0, text="⏳ 從 FinMind 並行抓取中（5 執行緒，約 30 秒，之後調參數不需再抓）...")
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
        entry_df, entry_funnel = run_filter(data, params, strict=strict_mode, stage="entry")
        watch_df, watch_funnel = run_filter(data, params, strict=strict_mode, stage="watch")

        stage_view = st.radio(
            "策略階段",
            ["進場觸發", "觀察名單"],
            horizontal=True,
            help="觀察名單=結構已符合，等待轉強量能與止跌轉折；進場觸發=今日已出現可執行買點"
        )
        if stage_view == "進場觸發":
            result_df, funnel = entry_df, entry_funnel
        else:
            result_df, funnel = watch_df, watch_funnel

        # ── 指標卡片 ──
        k1, k2, k3, k4, k5 = st.columns(5)
        
        def make_mini_card(title, val, extra=""):
            return f"""
            <div style="background:#0f1e33;border:1px solid rgba(59,130,246,0.2);
                        border-radius:10px;padding:10px 10px 9px;text-align:center;
                        min-height:82px;display:flex;flex-direction:column;
                        justify-content:center;gap:3px;">
                <div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;
                            letter-spacing:0.05em;line-height:1.3;">{title}</div>
                <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;
                            font-size:1.05rem;font-weight:700;line-height:1.2;
                            display:flex;justify-content:center;align-items:center;">
                    {val} {extra}
                </div>
            </div>
            """
            
        with k1:
            st.markdown(make_mini_card("📊 已載入", f"{ok:,} 檔"), unsafe_allow_html=True)
        with k2:
            st.markdown(make_mini_card("⏭️ 無資料", f"{skip:,} 檔"), unsafe_allow_html=True)
        with k3:
            st.markdown(make_mini_card("🔓 篩選模式", "嚴格" if strict_mode else "寬鬆"), unsafe_allow_html=True)
        with k4:
            st.markdown(make_mini_card("👀 觀察名單", f"{len(watch_df):,} 檔"), unsafe_allow_html=True)
        with k5:
            delta_html = f"<span style='color:#22c55e;font-size:0.75rem;margin-left:8px;font-family:\"Noto Sans TC\",sans-serif;'>(RR≥{min_rr})</span>" if len(result_df) else ""
            st.markdown(make_mini_card("🎯 進場觸發", f"{len(entry_df):,} 檔", delta_html), unsafe_allow_html=True)

        st.divider()

        # ── 條件漏斗分析（相對前一關卡通過率）──
        st.markdown("#### 🔬 條件漏斗分析（每關相對前一關的通過率，找出最卡瓶頸）")
        total   = len(data)
        n_gates = len(funnel)
        fcols   = st.columns(n_gates)
        prev_cnt = total  # 初始母數為整個股票池
        for i, (cname, cnt) in enumerate(funnel.items()):
            pct_rel = cnt / prev_cnt * 100 if prev_cnt else 0
            delta_txt = f"{pct_rel:.0f}% 通過" if i > 0 else f"{pct_rel:.0f}%（總池）"
            arrow     = "↑" if pct_rel >= 50 else "↓"
            clr = "#22c55e" if pct_rel >= 70 else "#fbbf24" if pct_rel >= 40 else "#f87171"
            with fcols[i]:
                st.markdown(f"""
                <div style="background:#0f1e33;border:1px solid rgba(59,130,246,0.2);
                            border-radius:10px;padding:10px 10px 9px;text-align:center;
                            min-height:82px;display:flex;flex-direction:column;
                            justify-content:center;gap:3px;">
                    <div style="color:#64748b;font-size:0.65rem;text-transform:uppercase;
                                letter-spacing:0.05em;line-height:1.3;">{cname}</div>
                    <div style="color:#e2e8f0;font-family:'JetBrains Mono',monospace;
                                font-size:1.05rem;font-weight:700;line-height:1.2;">{cnt} 檔</div>
                    <div style="color:{clr};font-size:0.68rem;font-weight:600;">
                        {arrow} {delta_txt}
                    </div>
                </div>
                """, unsafe_allow_html=True)
            prev_cnt = cnt

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
            st.markdown(f"### 📋 {stage_view} — {len(result_df)} 檔（依 RR 降序）")
            # 加入 K 線連結欄位
            result_df = result_df.copy()
            result_df["K線分析"] = result_df["代號"].apply(
                lambda sid: f"{KLINE_BASE_URL}?stock={sid}"
            )
            disp = [
                "K線分析","代號","名稱","收盤價","漲跌幅(%)","拉回深度(%)",
                "量縮比","今日量/均量","均線斜率%","轉折確認","距高點天數",
                "空間%","損益比(RR)","首波拉回","停損價","目標T1","目標T2",
            ]
            slope_col_help  = "近10日 MA60 百分比變化；正=向上，負=下彎" if params.get("pullback_mode") == "回踩MA60" else "近5日 MA20 百分比變化；正=向上，負=下彎"
            st.dataframe(
                result_df[disp],
                use_container_width=True,
                height=min(580, 45 + 38*len(result_df)),
                column_config={
                    "K線分析":       st.column_config.LinkColumn(
                                        "K線",
                                        display_text="分析",
                                        width=50,
                                        help="點擊開啟 K 線分析，自動帶入代號",
                                    ),
                    "代號":          st.column_config.TextColumn("代號",  width=45),
                    "名稱":          st.column_config.TextColumn("名稱",  width=60),
                    "收盤價":        st.column_config.NumberColumn("收盤",  format="%.1f"),
                    "漲跌幅(%)":     st.column_config.NumberColumn("漲跌",  format="%.1f%%"),
                    "拉回深度(%)":   st.column_config.NumberColumn("拉回%", format="%.1f%%", width=60),
                    "量縮比":        st.column_config.NumberColumn("量縮",  format="%.2f"),
                    "今日量/均量":   st.column_config.NumberColumn("均量",  format="%.2f",
                                        help="今日成交量 ÷ 20日均量；進場觸發需落在設定區間"),
                    "均線斜率%":     st.column_config.NumberColumn("斜率%",  format="%.2f%%",
                                        help=slope_col_help),
                    "轉折確認":      st.column_config.TextColumn("轉折", width=65,
                                        help="觀察=結構符合但尚未同時通過今日量能與止跌轉折；✅=已觸發"),
                    "距高點天數":    st.column_config.NumberColumn("高點",  format="%d天",
                                        help="距 M 日高點的天數；越小表示型態越新鮮"),
                    "停損價":        st.column_config.NumberColumn("停損",  format="%.1f"),
                    "目標T1":        st.column_config.NumberColumn("目標T1", format="%.1f",
                                        help="第一段止盈目標，RR以此計算"),
                    "目標T2":        st.column_config.NumberColumn("目標T2", format="%.1f",
                                        help="第二段波段目標"),
                    "空間%":         st.column_config.NumberColumn("空間%", format="%.1f%%",
                                        help="以 T1 目標價計算的潛在上漲空間"),
                    "損益比(RR)":    st.column_config.NumberColumn("RR",    format="%.2f", width=55),
                    "首波拉回":      st.column_config.TextColumn("首波",    width="small"),
                },
                hide_index=True,
            )

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
                # ── K 線進階分析超連結 ──
                stock_name = STOCK_NAME_MAP.get(sid, "")
                kline_url  = f"{KLINE_BASE_URL}?stock={sid}"
                st.markdown(
                    f"""<div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;">
                        <span style="font-family:monospace;font-size:1.05rem;font-weight:700;color:#e2e8f0;">{sid} {stock_name}</span>
                        <a href="{kline_url}" target="_blank" rel="noopener"
                           style="display:inline-flex;align-items:center;gap:6px;
                                  background:linear-gradient(135deg,#1d4ed8,#1e40af);
                                  color:#fff;text-decoration:none;font-size:0.82rem;font-weight:600;
                                  padding:6px 14px;border-radius:6px;
                                  border:1px solid rgba(96,165,250,0.4);
                                  transition:opacity .15s;">
                            📈 進階 K 線分析 &nbsp;↗
                        </a>
                    </div>""",
                    unsafe_allow_html=True,
                )
                st.plotly_chart(
                    kline(data[sid], sid,
                          stop_price=result_df.iloc[idx]["停損價"],
                          target_t1=result_df.iloc[idx]["目標T1"],
                          target_t2=result_df.iloc[idx]["目標T2"]),
                    use_container_width=True,
                )
                row = result_df.iloc[idx]
                ka, kb, kc, kd, ke = st.columns(5)
                with ka: st.metric("收盤", f"${row['收盤價']:.2f}", delta=f"{row['漲跌幅(%)']:.2f}%")
                with kb: st.metric("停損", f"${row['停損價']:.2f}")
                with kc: st.metric("目標T1", f"${row['目標T1']:.2f}")
                with kd: st.metric("目標T2", f"${row['目標T2']:.2f}")
                with ke: st.metric("RR",  f"{row['損益比(RR)']:.2f}x")

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
                        f"| 回踩低點 | **{pullback_lower:.1f}% 以內** |\n"
                        f"| 今收距均線 | **0% ～ +{pullback_upper:.1f}%** |\n"
                        f"| 量縮比 Y | **{vol_ratio}** |\n"
                        f"| 最低 RR | **{min_rr}x** |\n"
                        f"| 股票池 | **{len(user_ids)}** 檔 |")

    st.markdown("""<div class="risk-warn">
        ⚠️ 本系統僅供技術分析參考，不構成投資建議。股市有風險，請嚴格執行停損。
    </div>""", unsafe_allow_html=True)
    
    # 將策略說明移至最下方
    st.markdown("""<div class="strat-info">
        🎯 <strong>策略核心：</strong>多頭趨勢中的波段拉回止跌轉折高損益比選股<br>
        <strong>①長線多頭</strong>（MA50>MA200, Close>MA200）→
        <strong>②動能記憶</strong>（近N日收盤曾突破前M日高，shift(1)修正）→
        <strong>③波段拉回</strong>（近期低點允許小破均線，今收需站回 MA20/MA60 且不過度乖離）→
        <strong>④均線斜率%</strong>（MA20/MA60 正規化百分比斜率>門檻）→
        <strong>⑤量縮洗盤</strong>（近3日量&lt;20日量×Y）→
        <strong>⑤+今日轉強量能</strong>（今日量落在設定區間）→
        <strong>⑥止跌轉折</strong>（今收&gt;昨高 或 站回均線）。觀察名單先看①~⑤，進場觸發再要求⑤+與⑥。
    </div>""", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
