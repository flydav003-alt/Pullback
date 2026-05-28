# ==============================================================================
# 台股波段拉回選股工具 v3.0
# 資料來源：FinMind API（台股專屬，穩定可靠）
# 安全機制：API Token 存於 Streamlit Secrets，不寫入程式碼
# 排程機制：每日 18:00（台灣時間）自動抓取；亦可手動觸發
# ==============================================================================

import re
import io
import time
import warnings
import threading
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo          # Python 3.9+ 內建時區支援

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import streamlit as st

warnings.filterwarnings("ignore")

# ==============================================================================
# ── 0. 頁面設定（必須是第一個 Streamlit 呼叫）
# ==============================================================================
st.set_page_config(
    page_title="台股波段拉回選股 v3",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# ── 1. 時區常數
# ==============================================================================
TZ_TW = ZoneInfo("Asia/Taipei")   # 台灣時間 UTC+8

# ==============================================================================
# ── 2. 全域 CSS（深色主題，台股紅漲綠跌）
# ==============================================================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] { font-family: 'Noto Sans TC', sans-serif; }

.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 50%, #0a1020 100%);
    color: #e2e8f0;
}
.hero-header {
    background: linear-gradient(120deg, #1a2744 0%, #162038 40%, #1e1035 100%);
    border: 1px solid rgba(59,130,246,0.25);
    border-radius: 16px;
    padding: 28px 36px;
    margin-bottom: 20px;
    position: relative;
    overflow: hidden;
}
.hero-header::before {
    content: '';
    position: absolute;
    top: -60px; right: -60px;
    width: 200px; height: 200px;
    background: radial-gradient(circle, rgba(59,130,246,0.15) 0%, transparent 70%);
    border-radius: 50%;
}
.hero-title {
    font-size: 2.2rem;
    font-weight: 900;
    background: linear-gradient(90deg, #60a5fa, #f87171, #fbbf24);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin: 0 0 8px 0;
    letter-spacing: -0.5px;
}
.hero-subtitle { color: #94a3b8; font-size: 0.95rem; margin: 0; }

/* 排程狀態卡 */
.schedule-card {
    background: linear-gradient(135deg, #0f2027 0%, #162533 100%);
    border: 1px solid rgba(34,197,94,0.3);
    border-radius: 10px;
    padding: 12px 18px;
    margin-bottom: 12px;
    font-size: 0.85rem;
}
.schedule-card.warn {
    border-color: rgba(251,191,36,0.4);
}
.schedule-card .label { color: #64748b; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; }
.schedule-card .value { color: #e2e8f0; font-family: 'JetBrains Mono', monospace; font-weight: 600; }
.schedule-card .highlight { color: #22c55e; font-weight: 700; }
.schedule-card .warn-text { color: #fbbf24; font-weight: 700; }

/* 策略說明 */
.strategy-info {
    background: linear-gradient(135deg, #172035 0%, #1a2744 100%);
    border-left: 4px solid #3b82f6;
    border-radius: 8px;
    padding: 16px 20px;
    margin-bottom: 16px;
    font-size: 0.88rem;
    color: #94a3b8;
    line-height: 1.7;
}
.strategy-info strong { color: #60a5fa; }

/* Metric 卡片 */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e2d4a 0%, #162038 100%);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 12px;
    padding: 16px 20px !important;
}
[data-testid="stMetric"] label { color: #64748b !important; font-size: 0.8rem !important; font-weight: 500 !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricValue"] { color: #f1f5f9 !important; font-family: 'JetBrains Mono', monospace !important; font-size: 2rem !important; font-weight: 700 !important; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1829 0%, #0a1020 100%);
    border-right: 1px solid rgba(59,130,246,0.15);
}
[data-testid="stSidebar"] .stMarkdown h3 { color: #60a5fa; font-size: 0.9rem; text-transform: uppercase; letter-spacing: 0.08em; border-bottom: 1px solid rgba(59,130,246,0.2); padding-bottom: 6px; }

/* 按鈕 */
.stButton > button {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
    color: white; border: none; border-radius: 8px;
    font-weight: 600; font-size: 0.95rem;
    padding: 10px 24px; width: 100%;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(59,130,246,0.4);
}

/* 風險警示 */
.risk-warning {
    background: linear-gradient(135deg, #1f1510 0%, #2d1b0e 100%);
    border: 1px solid rgba(251,191,36,0.3);
    border-radius: 8px;
    padding: 14px 20px;
    margin-top: 24px;
    color: #fbbf24;
    font-size: 0.82rem;
    text-align: center;
}

hr { border-color: rgba(59,130,246,0.15) !important; }
[data-testid="stDataFrame"] { border: 1px solid rgba(59,130,246,0.15); border-radius: 10px; overflow: hidden; }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# ── 3. 股票池（371 檔，半導體/AI/衛星供應鏈）
# ==============================================================================
STOCK_STRING = """
2454聯發科3035智原3443創意3661世芯-KY6526達發5269祥碩3529力旺5274信驊6643M316533晶心科
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


def extract_stock_ids(stock_str: str) -> list[str]:
    """
    從股票字串提取純數字股號（4~5 位）。
    re.ASCII 確保中文字符不被視為 word character，
    讓 \\b 能正確識別數字與中文的邊界。
    回傳格式：['2330', '2454', ...]（純股號，不含後綴）
    """
    codes = re.findall(r'\b(\d{4,5})\b', stock_str, re.ASCII)
    seen: set[str] = set()
    result: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            result.append(c)
    return result


# ── 預設股票池（純股號列表）
DEFAULT_STOCK_IDS = extract_stock_ids(STOCK_STRING)

# ==============================================================================
# ── 4. FinMind API 工具函式
# ==============================================================================

FINMIND_API_URL = "https://api.finmindtrade.com/api/v4/data"


def get_finmind_token() -> str:
    """
    從 Streamlit Secrets 讀取 FinMind API Token。
    Secrets 設定方式（.streamlit/secrets.toml）：
        [finmind]
        token = "your_token_here"
    """
    try:
        token = st.secrets["finmind"]["token"]
        if not token or token == "your_token_here":
            st.error("⚠️ 請在 Streamlit Secrets 設定有效的 FinMind token！")
            st.stop()
        return token
    except KeyError:
        st.error(
            "⚠️ 找不到 FinMind token！\n\n"
            "請在 Streamlit Cloud → App settings → Secrets 加入：\n"
            "```toml\n[finmind]\ntoken = \"your_token_here\"\n```"
        )
        st.stop()


def finmind_fetch_prices(
    stock_ids: list[str],
    start_date: str,
    end_date: str,
    token: str,
) -> dict[str, pd.DataFrame]:
    """
    呼叫 FinMind TaiwanStockPrice API，批次下載台股日線資料。

    FinMind 優勢：
      - 一次 API call 可帶多支股票（傳 stock_id 用逗號分隔）
      - 實際上 FinMind 每支股票算一個 request，但回傳穩定
      - 免費登入後 600 calls/hr，一批 60 支 = 60 calls，
        350 支分 6 批共 360 calls，一次掃描只需約 1 分鐘

    回傳：
        dict[stock_id → pd.DataFrame(OHLCV)]
    """
    result: dict[str, pd.DataFrame] = {}
    BATCH_SIZE = 60          # 每批 60 支，避免單次 payload 過大
    MIN_ROWS   = 100         # 資料筆數門檻

    batches = [stock_ids[i:i+BATCH_SIZE]
               for i in range(0, len(stock_ids), BATCH_SIZE)]

    for batch in batches:
        for stock_id in batch:
            try:
                resp = requests.get(
                    FINMIND_API_URL,
                    params={
                        "dataset":    "TaiwanStockPrice",
                        "data_id":    stock_id,
                        "start_date": start_date,
                        "end_date":   end_date,
                        "token":      token,
                    },
                    timeout=15,
                )
                resp.raise_for_status()
                payload = resp.json()

                # FinMind 回傳格式：{"status": 200, "data": [...]}
                if payload.get("status") != 200:
                    continue
                rows = payload.get("data", [])
                if not rows:
                    continue

                df = pd.DataFrame(rows)
                # FinMind 欄位名稱對應
                rename_map = {
                    "date":              "Date",
                    "open":              "Open",
                    "max":               "High",     # FinMind 用 max/min
                    "min":               "Low",
                    "close":             "Close",
                    "Trading_Volume":    "Volume",
                    "trading_volume":    "Volume",
                    "Trading_money":     "Amount",
                    "spread":            "Change",
                }
                df = df.rename(columns=rename_map)

                # 確保必要欄位存在
                required = ["Date", "Open", "High", "Low", "Close", "Volume"]
                if not all(c in df.columns for c in required):
                    continue

                df["Date"] = pd.to_datetime(df["Date"])
                df = df.set_index("Date").sort_index()
                df = df[required[1:]].apply(pd.to_numeric, errors="coerce")
                df = df.dropna(subset=["Close"])

                if len(df) >= MIN_ROWS:
                    result[stock_id] = df

            except Exception:
                # 單支失敗不中斷整批，靜默跳過
                continue

            # 小延遲避免過於頻繁打 API（每支間隔 50ms）
            time.sleep(0.05)

    return result


# ==============================================================================
# ── 5. 排程邏輯（台灣時間 18:00 自動觸發）
# ==============================================================================

# 台股收盤 13:30，官方資料更新約 15:00~17:00，18:00 確保資料完整
AUTO_FETCH_HOUR_TW = 18


def get_tw_now() -> datetime:
    """取得目前台灣時間"""
    return datetime.now(tz=TZ_TW)


def should_auto_fetch() -> bool:
    """
    判斷是否應自動抓取資料。
    條件：
      1. 今日尚未抓過（session_state 中 last_fetch_date != 今天）
      2. 目前台灣時間 >= 18:00
      3. 今日為交易日（週一至週五；台灣國定假日無法自動偵測，略過）
    """
    now_tw = get_tw_now()

    # 週末不自動抓（週六=5，週日=6）
    if now_tw.weekday() >= 5:
        return False

    # 時間未到 18:00 不抓
    if now_tw.hour < AUTO_FETCH_HOUR_TW:
        return False

    # 今日已抓過就不重複
    last_date = st.session_state.get("last_fetch_date")
    if last_date == now_tw.date():
        return False

    return True


def next_fetch_time() -> str:
    """計算下次自動抓取的台灣時間字串"""
    now_tw = get_tw_now()
    today_fetch = now_tw.replace(hour=AUTO_FETCH_HOUR_TW, minute=0, second=0, microsecond=0)

    if now_tw < today_fetch and now_tw.weekday() < 5:
        # 今天還沒到 18:00
        return today_fetch.strftime("%Y/%m/%d %H:%M")
    else:
        # 找下一個工作日
        next_day = now_tw + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)
        return next_day.replace(
            hour=AUTO_FETCH_HOUR_TW, minute=0, second=0, microsecond=0
        ).strftime("%Y/%m/%d %H:%M")


# ==============================================================================
# ── 6. 快取包裝：帶 TTL 的資料下載
# ==============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_finmind_data(
    stock_ids_tuple: tuple[str, ...],
    start_date: str,
    end_date: str,
    token: str,
) -> tuple[dict, int, int]:
    """
    帶 st.cache_data 快取的 FinMind 下載入口。
    TTL = 3600 秒（1 小時），同一組參數 1 小時內不重複打 API。

    參數用 tuple 是因為 list 不可 hash，st.cache_data 需要可 hash 的參數。
    token 也作為 cache key，確保換 token 時能正確失效。
    """
    stock_ids = list(stock_ids_tuple)
    data_dict = finmind_fetch_prices(stock_ids, start_date, end_date, token)
    success   = len(data_dict)
    skipped   = len(stock_ids) - success
    return data_dict, success, skipped


# ==============================================================================
# ── 7. 技術指標工具函式
# ==============================================================================

def calc_ma(series: pd.Series, window: int) -> pd.Series:
    """簡單移動平均線（SMA）"""
    return series.rolling(window=window, min_periods=window).mean()


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range（ATR）"""
    h, l, c = df["High"], df["Low"], df["Close"]
    tr = pd.concat([
        h - l,
        (h - c.shift(1)).abs(),
        (l - c.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# ==============================================================================
# ── 8. 核心篩選策略（Sidebar 參數即時生效，不加快取）
# ==============================================================================

def filter_pullback_stocks(data_dict: dict, params: dict) -> pd.DataFrame:
    """
    五重條件篩選波段拉回止跌轉折個股：

    ① 長線多頭：MA50 > MA200 且 Close > MA200
    ② 動能記憶：過去 N 天內曾創近 M 天新高
    ③ 波段拉回：Close 與 MA20 距離在 ±X%
    ④ 量縮洗盤：近 3 日均量 < 20 日均量 × Y
    ⑤ 止跌轉折：今收 > 昨高

    額外計算：停損價、目標價、損益比（RR）
    """
    results = []

    for stock_id, df in data_dict.items():
        try:
            if len(df) < 210:
                continue

            df  = df.copy().sort_index()
            c   = df["Close"]
            h   = df["High"]
            l   = df["Low"]
            v   = df["Volume"]

            # ── 均線 ──
            ma20  = calc_ma(c, 20)
            ma50  = calc_ma(c, 50)
            ma200 = calc_ma(c, 200)
            atr14 = calc_atr(df, 14)

            # ── 最後一根 K 棒資料 ──
            c0       = c.iloc[-1]       # 今日收盤
            c1       = c.iloc[-2]       # 昨日收盤
            h1       = h.iloc[-2]       # 昨日最高（止跌判斷用）
            ma20_0   = ma20.iloc[-1]
            ma50_0   = ma50.iloc[-1]
            ma200_0  = ma200.iloc[-1]
            atr_0    = atr14.iloc[-1]

            if any(pd.isna([c0, c1, h1, ma20_0, ma50_0, ma200_0, atr_0])):
                continue

            # ── ① 長線多頭 ──
            if not (ma50_0 > ma200_0 and c0 > ma200_0):
                continue

            # ── ② 動能記憶（過去 N 天內曾創近 M 天新高）──
            n = params["momentum_days"]
            m = params["high_window"]
            past_close   = c.iloc[-(n+1):-1]
            rolling_high = h.rolling(m).max().iloc[-(n+1):-1]
            if not (past_close >= rolling_high).any():
                continue

            # ── ③ 波段拉回（Close ≈ MA20 ± X%）──
            dist_pct = (c0 - ma20_0) / ma20_0 * 100
            if abs(dist_pct) > params["pullback_pct"]:
                continue

            # ── ④ 量縮洗盤 ──
            vol3  = v.iloc[-4:-1].mean()    # 近 3 日（不含今日）
            vol20 = v.iloc[-21:-1].mean()   # 近 20 日
            if pd.isna(vol3) or pd.isna(vol20) or vol20 == 0:
                continue
            vol_shrink = vol3 / vol20
            if vol_shrink >= params["vol_ratio"]:
                continue

            # ── ⑤ 止跌轉折（今收 > 昨高）──
            if c0 <= h1:
                continue

            # ── 第一波拉回偵測（近 10 日觸發次數）──
            first_pullback = True
            for i in range(2, 12):
                if i + 1 > len(c):
                    break
                ci    = c.iloc[-i]
                hi1   = h.iloc[-(i+1)]
                ma20i = ma20.iloc[-i]
                if pd.isna([ci, hi1, ma20i]).any():
                    continue
                if abs((ci - ma20i) / ma20i * 100) <= params["pullback_pct"] and ci > hi1:
                    first_pullback = False
                    break

            # ── 風險收益計算 ──
            recent_low  = min(l.iloc[-1], l.iloc[-2])
            stop_atr    = c0 - 1.5 * atr_0
            stop_pct    = recent_low * 0.98
            stop_loss   = min(max(stop_atr, stop_pct), c0 * 0.95)

            prev_high   = h.iloc[-m:].max()
            target      = max(c0 * 1.20, prev_high * 1.02)

            risk        = c0 - stop_loss
            reward      = target - c0
            rr          = reward / risk if risk > 0 else 0.0

            if rr < params["min_rr"]:
                continue

            chg_pct = (c0 - c1) / c1 * 100 if c1 != 0 else 0.0

            results.append({
                "代號":        stock_id,
                "收盤價":      round(c0, 2),
                "漲跌幅(%)":   round(chg_pct, 2),
                "拉回深度(%)": round(dist_pct, 2),
                "量縮比":      round(vol_shrink, 2),
                "停損價":      round(stop_loss, 2),
                "目標價":      round(target, 2),
                "損益比(RR)":  round(rr, 2),
                "首波拉回":    "✅" if first_pullback else "—",
                "MA20":        round(ma20_0, 2),
                "MA50":        round(ma50_0, 2),
                "MA200":       round(ma200_0, 2),
            })

        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    df_out = pd.DataFrame(results)
    return df_out.sort_values("損益比(RR)", ascending=False).reset_index(drop=True)


# ==============================================================================
# ── 9. Plotly K 線圖（Candlestick + Volume + MA 均線）
# ==============================================================================

def plot_candlestick(df: pd.DataFrame, stock_id: str) -> go.Figure:
    """
    繪製精美 K 線圖：
    - 台股紅漲綠跌配色
    - MA20（橙）、MA50（藍）、MA200（紅虛線）
    - Volume 子圖
    - Rangeslider
    """
    df = df.copy().sort_index().tail(250)
    df["MA20"]  = calc_ma(df["Close"], 20)
    df["MA50"]  = calc_ma(df["Close"], 50)
    df["MA200"] = calc_ma(df["Close"], 200)

    # K 棒顏色（台股：收 >= 開 = 紅；收 < 開 = 綠）
    bar_colors = [
        "#ef4444" if row["Close"] >= row["Open"] else "#22c55e"
        for _, row in df.iterrows()
    ]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
        subplot_titles=(f"{stock_id} — K 線與均線", "成交量"),
    )

    # K 線
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df["Open"], high=df["High"],
        low=df["Low"],   close=df["Close"],
        increasing_line_color="#ef4444", increasing_fillcolor="#ef4444",
        decreasing_line_color="#22c55e", decreasing_fillcolor="#22c55e",
        name="K線", line=dict(width=1),
    ), row=1, col=1)

    # MA20 橙線
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MA20"],
        line=dict(color="#fb923c", width=1.5),
        name="MA20",
    ), row=1, col=1)

    # MA50 藍線
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MA50"],
        line=dict(color="#60a5fa", width=1.8),
        name="MA50",
    ), row=1, col=1)

    # MA200 紅虛線
    fig.add_trace(go.Scatter(
        x=df.index, y=df["MA200"],
        line=dict(color="#f43f5e", width=2, dash="dot"),
        name="MA200",
    ), row=1, col=1)

    # 成交量
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"],
        marker_color=bar_colors,
        name="成交量", opacity=0.75,
    ), row=2, col=1)

    fig.update_layout(
        height=600,
        paper_bgcolor="#0d1526",
        plot_bgcolor="#0d1526",
        font=dict(color="#94a3b8", size=11, family="Noto Sans TC"),
        legend=dict(
            orientation="h", yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(13,21,38,0.8)",
        ),
        xaxis_rangeslider_visible=True,
        xaxis_rangeslider=dict(
            bgcolor="#0a0e1a",
            bordercolor="rgba(59,130,246,0.2)",
            thickness=0.04,
        ),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(gridcolor="rgba(59,130,246,0.08)", linecolor="rgba(59,130,246,0.2)")
    fig.update_yaxes(gridcolor="rgba(59,130,246,0.08)", linecolor="rgba(59,130,246,0.2)")
    for ann in fig.layout.annotations:
        ann.font.color = "#64748b"
        ann.font.size  = 11

    return fig


# ==============================================================================
# ── 10. 主程式 UI
# ==============================================================================

def do_fetch(stock_ids: list[str], token: str) -> tuple[dict, int, int]:
    """
    執行實際資料抓取並更新 session_state。
    供「手動掃描」按鈕與「自動排程」共用。
    """
    now_tw    = get_tw_now()
    end_dt    = now_tw.strftime("%Y-%m-%d")
    start_dt  = (now_tw - timedelta(days=430)).strftime("%Y-%m-%d")  # 確保 MA200 足夠

    data_dict, success, skipped = load_finmind_data(
        stock_ids_tuple=tuple(stock_ids),
        start_date=start_dt,
        end_date=end_dt,
        token=token,
    )

    # 更新 session_state
    st.session_state["data_dict"]       = data_dict
    st.session_state["success_cnt"]     = success
    st.session_state["skip_cnt"]        = skipped
    st.session_state["last_fetch_date"] = now_tw.date()
    st.session_state["last_fetch_time"] = now_tw.strftime("%Y/%m/%d %H:%M:%S")

    return data_dict, success, skipped


def main():
    # ── Token（從 Secrets 讀取）──
    token = get_finmind_token()

    # ── 自動排程觸發（無需使用者操作）──
    if should_auto_fetch():
        with st.spinner("⏰ 排程自動抓取中（台灣時間 18:00）..."):
            default_ids = extract_stock_ids(STOCK_STRING)
            do_fetch(default_ids, token)
        st.toast("✅ 排程自動抓取完成！", icon="🕕")

    # ─────────────────────────────────────────────────────────────────────
    # ── 標題 ──
    # ─────────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-header">
        <p class="hero-title">📡 台股波段拉回選股系統 v3</p>
        <p class="hero-subtitle">
            半導體 · AI · 衛星通訊完整供應鏈
            ｜FinMind 台股專屬資料
            ｜每日 18:00 自動更新 · 手動掃描隨時可用
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── 排程狀態資訊 ──
    now_tw     = get_tw_now()
    last_time  = st.session_state.get("last_fetch_time", "尚未抓取")
    next_time  = next_fetch_time()
    has_data   = "data_dict" in st.session_state and st.session_state["data_dict"]

    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        st.markdown(f"""
        <div class="schedule-card">
            <div class="label">🕐 台灣現在時間</div>
            <div class="value">{now_tw.strftime("%Y/%m/%d %H:%M:%S")}</div>
        </div>""", unsafe_allow_html=True)
    with col_s2:
        st.markdown(f"""
        <div class="schedule-card">
            <div class="label">✅ 上次抓取時間</div>
            <div class="value highlight">{last_time}</div>
        </div>""", unsafe_allow_html=True)
    with col_s3:
        st.markdown(f"""
        <div class="schedule-card warn">
            <div class="label">⏰ 下次自動抓取</div>
            <div class="value warn-text">{next_time} (台灣時間)</div>
        </div>""", unsafe_allow_html=True)

    # ── 策略說明 ──
    st.markdown("""
    <div class="strategy-info">
        🎯 <strong>策略核心：</strong>在多頭趨勢中，篩選已有強勢動能、正在拉回整理、出現量縮止跌轉折訊號的個股。<br>
        📌 <strong>①長線多頭</strong>（MA50>MA200，Close>MA200）→
        <strong>②動能記憶</strong>（近期曾創新高）→
        <strong>③波段拉回</strong>（Close≈MA20）→
        <strong>④量縮洗盤</strong>（近3日量&lt;20日量×門檻）→
        <strong>⑤止跌轉折</strong>（今收>昨高）
    </div>
    """, unsafe_allow_html=True)

    # ═════════════════════════════════════════════════════════════════════
    # ── SIDEBAR ──
    # ═════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("### ⚙️ 策略參數")

        st.markdown("**① 長線多頭**")
        st.caption("MA50 > MA200 且 Close > MA200（固定）")
        st.divider()

        st.markdown("**② 動能記憶**")
        momentum_days = st.slider("回看天數 N", 5, 60, 25, 5,
                                  help="過去 N 個交易日內需曾觸及近期高點")
        high_window   = st.slider("新高窗口 M（天）", 20, 120, 60, 5)
        st.divider()

        st.markdown("**③ 波段拉回幅度**")
        pullback_pct  = st.slider("Close 與 MA20 距離 ±%", 0.5, 8.0, 2.5, 0.5)
        st.divider()

        st.markdown("**④ 量縮比例**")
        vol_ratio     = st.slider("近3日量 < 20日量 × Y", 0.3, 1.0, 0.75, 0.05)
        st.divider()

        st.markdown("**⑤ 最低損益比**")
        min_rr        = st.slider("RR 門檻", 1.0, 5.0, 2.0, 0.5)
        st.divider()

        # ── 股票池編輯 ──
        st.markdown("### 📋 股票池")
        default_codes_str = "\n".join(DEFAULT_STOCK_IDS)
        user_input = st.text_area(
            "股號清單（每行一個）",
            value=default_codes_str,
            height=180,
            help="4~5 位數股號，每行一個",
        )
        user_ids = re.findall(r'\b(\d{4,5})\b', user_input, re.ASCII)
        # 去重保持順序
        seen_ids: set[str] = set()
        unique_ids: list[str] = []
        for uid in user_ids:
            if uid not in seen_ids:
                seen_ids.add(uid)
                unique_ids.append(uid)
        user_stock_ids = unique_ids

        st.caption(f"已設定 **{len(user_stock_ids)}** 檔股票")
        st.divider()

        # ── 掃描模式 ──
        st.markdown("### 🔄 模式")
        scan_mode = st.radio(
            "選擇",
            ["手動掃描（重新抓取資料）", "即時篩選（使用已載入資料）"],
            index=0,
        )

        # ── 手動掃描按鈕 ──
        run_btn = st.button("🚀 立即掃描", type="primary", use_container_width=True)

        # ── FinMind 資料說明 ──
        st.divider()
        st.markdown("### ℹ️ 資料來源")
        st.caption("FinMind TaiwanStockPrice\nToken 已安全存於 Streamlit Secrets")
        st.caption(f"免費方案上限：600 calls/hr\n掃描 {len(user_stock_ids)} 檔需約 {len(user_stock_ids)} calls")
        remaining = max(0, 600 - len(user_stock_ids))
        st.progress(
            min(len(user_stock_ids) / 600, 1.0),
            text=f"預估使用 {len(user_stock_ids)}/600 calls",
        )

    # ═════════════════════════════════════════════════════════════════════
    # ── 主頁面邏輯
    # ═════════════════════════════════════════════════════════════════════

    params = {
        "momentum_days": momentum_days,
        "high_window":   high_window,
        "pullback_pct":  pullback_pct,
        "vol_ratio":     vol_ratio,
        "min_rr":        min_rr,
    }

    # 觸發條件：手動按鈕 或 即時篩選模式（已有資料）
    should_scan = (
        run_btn or
        (scan_mode == "即時篩選（使用已載入資料）" and has_data)
    )

    if should_scan:
        # ── 資料抓取或沿用快取 ──
        if run_btn or not has_data:
            progress_bar = st.progress(0, text="⏳ 正在從 FinMind 抓取資料（約 1~2 分鐘）...")
            with st.spinner(""):
                data_dict, success_cnt, skip_cnt = do_fetch(user_stock_ids, token)
            progress_bar.progress(70, text="✅ 資料抓取完成，套用選股策略中...")
        else:
            data_dict   = st.session_state["data_dict"]
            success_cnt = st.session_state["success_cnt"]
            skip_cnt    = st.session_state["skip_cnt"]
            progress_bar = st.empty()

        # ── 套用策略篩選 ──
        with st.spinner("🔍 篩選中..."):
            result_df = filter_pullback_stocks(data_dict, params)

        try:
            progress_bar.empty()
        except Exception:
            pass

        # ── 指標卡片 ──
        m1, m2, m3, m4 = st.columns(4)
        with m1: st.metric("📊 掃描股票", f"{len(data_dict):,} 檔")
        with m2: st.metric("✅ 成功載入", f"{success_cnt:,} 檔")
        with m3: st.metric("⏭️ 無資料",   f"{skip_cnt:,} 檔")
        with m4: st.metric("🎯 符合條件", f"{len(result_df):,} 檔",
                            delta=f"RR ≥ {min_rr}" if len(result_df) > 0 else None)

        st.divider()

        # ── 結果表格 ──
        if result_df.empty:
            st.warning("⚠️ 目前沒有符合所有條件的個股，請嘗試放寬參數。")
        else:
            st.markdown(f"### 📋 篩選結果 — 共 {len(result_df)} 檔（依損益比降序）")

            disp_cols = ["代號", "收盤價", "漲跌幅(%)", "拉回深度(%)",
                         "量縮比", "停損價", "目標價", "損益比(RR)", "首波拉回"]
            st.dataframe(
                result_df[disp_cols],
                use_container_width=True,
                height=min(600, 45 + 38 * len(result_df)),
                column_config={
                    "代號":        st.column_config.TextColumn("代號", width="small"),
                    "收盤價":      st.column_config.NumberColumn("收盤價", format="%.2f"),
                    "漲跌幅(%)":   st.column_config.NumberColumn("漲跌幅", format="%.2f%%"),
                    "拉回深度(%)": st.column_config.NumberColumn("拉回深度", format="%.2f%%"),
                    "量縮比":      st.column_config.ProgressColumn(
                                        "量縮比", min_value=0, max_value=1, format="%.2f"),
                    "停損價":      st.column_config.NumberColumn("停損", format="%.2f"),
                    "目標價":      st.column_config.NumberColumn("目標", format="%.2f"),
                    "損益比(RR)":  st.column_config.NumberColumn("RR", format="%.2f"),
                    "首波拉回":    st.column_config.TextColumn("首波", width="small"),
                },
                hide_index=True,
            )

            # ── CSV 下載 ──
            buf = io.StringIO()
            result_df.to_csv(buf, index=False, encoding="utf-8-sig")
            st.download_button(
                "⬇️ 下載 CSV",
                data=buf.getvalue(),
                file_name=f"pullback_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )

            st.divider()

            # ── K 線圖 ──
            st.markdown("### 📈 個股 K 線圖")
            label_opts = [
                f"{row['代號']}  RR={row['損益比(RR)']}  收={row['收盤價']}"
                for _, row in result_df.iterrows()
            ]
            sel_label = st.selectbox("選擇個股", label_opts, index=0)
            sel_idx   = label_opts.index(sel_label)
            sel_id    = result_df.iloc[sel_idx]["代號"]

            if sel_id in data_dict:
                fig = plot_candlestick(data_dict[sel_id], sel_id)
                st.plotly_chart(fig, use_container_width=True)

                row = result_df.iloc[sel_idx]
                ka, kb, kc, kd = st.columns(4)
                with ka: st.metric("收盤價",  f"${row['收盤價']:.2f}",
                                   delta=f"{row['漲跌幅(%)']:.2f}%")
                with kb: st.metric("建議停損", f"${row['停損價']:.2f}")
                with kc: st.metric("預估目標", f"${row['目標價']:.2f}")
                with kd: st.metric("損益比 RR", f"{row['損益比(RR)']:.2f}x")

    else:
        # ── 未掃描時的歡迎畫面 ──
        if has_data:
            last = st.session_state.get("last_fetch_time", "")
            st.info(f"📦 已有快取資料（{last}），可選擇「即時篩選」模式直接使用，或按「立即掃描」重新抓取。")
        else:
            st.info("👈 請點擊左側「🚀 立即掃描」開始抓取資料並篩選個股。\n\n每日 18:00（台灣時間）也會自動抓取最新資料。")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            | 參數 | 值 |
            |---|---|
            | 動能回看 N | **{momentum_days}** 天 |
            | 新高窗口 M | **{high_window}** 天 |
            | 拉回幅度 | **±{pullback_pct}%** |
            """)
        with c2:
            st.markdown(f"""
            | 參數 | 值 |
            |---|---|
            | 量縮比 Y | **{vol_ratio}** |
            | 最低 RR | **{min_rr}x** |
            | 股票池 | **{len(user_stock_ids)}** 檔 |
            """)

    # ── 風險提醒 ──
    st.markdown("""
    <div class="risk-warning">
        ⚠️ <strong>風險提醒：</strong>本系統僅供技術分析參考，不構成任何投資建議。
        股市投資有風險，過去績效不代表未來表現。請依個人風險承受能力自行判斷，並嚴格執行停損紀律。
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# ── 11. 程式進入點
# ==============================================================================
if __name__ == "__main__":
    main()


# ==============================================================================
# ── APPENDIX：部署說明
# ==============================================================================
#
# ── requirements.txt ──
#   streamlit>=1.35.0
#   pandas>=2.1.0
#   numpy>=1.26.0
#   plotly>=5.20.0
#   requests>=2.31.0
#   (不需要 yfinance)
#
# ── Streamlit Secrets 設定（最重要！）──
#   在 Streamlit Cloud → 你的 App → Settings → Secrets 貼上：
#
#   [finmind]
#   token = "你的 FinMind Token"
#
#   本地測試則建立 .streamlit/secrets.toml 檔案：
#   [finmind]
#   token = "你的 FinMind Token"
#
#   FinMind Token 取得：https://finmindtrade.com/ 註冊後登入即可
#
# ── 自動排程說明 ──
#   Streamlit Cloud 的 App 在有人開啟瀏覽器時才會「活著」。
#   因此「排程」是：使用者開啟頁面時，
#   若當天 18:00 後且尚未抓取，就自動觸發一次抓取。
#   若需要無人值守的真正排程，可搭配：
#     - GitHub Actions（每天定時 trigger 一個 HTTP 請求喚醒 App）
#     - UptimeRobot 定時 ping（保持 App 存活）
#
# ==============================================================================
