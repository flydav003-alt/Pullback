# ==============================================================================
# 台股波段拉回選股工具 - 專注半導體/AI/衛星供應鏈
# Taiwan Stock Pullback Scanner - Semiconductor / AI / Satellite Supply Chain
# 作者：量化交易系統架構師
# 版本：2.0 (2024)
# ==============================================================================

import re
import time
import warnings
import io
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import yfinance as yf

warnings.filterwarnings("ignore")

# ==============================================================================
# ── 0. 頁面設定（必須在最前面）
# ==============================================================================
st.set_page_config(
    page_title="台股波段拉回選股",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ==============================================================================
# ── 1. 自訂 CSS 樣式（台股色系：紅漲綠跌）
# ==============================================================================
st.markdown("""
<style>
/* ── 全域字體與背景 ── */
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Noto Sans TC', sans-serif;
}

/* ── 主背景 ── */
.stApp {
    background: linear-gradient(135deg, #0a0e1a 0%, #0d1526 50%, #0a1020 100%);
    color: #e2e8f0;
}

/* ── 精美標題區塊 ── */
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
.hero-header::after {
    content: '';
    position: absolute;
    bottom: -40px; left: 20%;
    width: 300px; height: 100px;
    background: radial-gradient(ellipse, rgba(239,68,68,0.08) 0%, transparent 70%);
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
.hero-subtitle {
    color: #94a3b8;
    font-size: 0.95rem;
    margin: 0;
    font-weight: 400;
}

/* ── 指標卡片 ── */
[data-testid="stMetric"] {
    background: linear-gradient(135deg, #1e2d4a 0%, #162038 100%);
    border: 1px solid rgba(59,130,246,0.2);
    border-radius: 12px;
    padding: 16px 20px !important;
}
[data-testid="stMetric"] label {
    color: #64748b !important;
    font-size: 0.8rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
[data-testid="stMetricValue"] {
    color: #f1f5f9 !important;
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

/* ── 側邊欄 ── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1829 0%, #0a1020 100%);
    border-right: 1px solid rgba(59,130,246,0.15);
}
[data-testid="stSidebar"] .stMarkdown h3 {
    color: #60a5fa;
    font-size: 0.9rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border-bottom: 1px solid rgba(59,130,246,0.2);
    padding-bottom: 6px;
}

/* ── 資訊框 ── */
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

/* ── 表格漲跌色 ── */
.positive { color: #ef4444 !important; font-weight: 600; }   /* 台股紅=漲 */
.negative { color: #22c55e !important; font-weight: 600; }   /* 台股綠=跌 */

/* ── 風險提醒 ── */
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

/* ── 按鈕美化 ── */
.stButton > button {
    background: linear-gradient(135deg, #1d4ed8 0%, #1e40af 100%);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.95rem;
    padding: 10px 24px;
    width: 100%;
    transition: all 0.2s ease;
}
.stButton > button:hover {
    background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%);
    transform: translateY(-1px);
    box-shadow: 0 4px 15px rgba(59,130,246,0.4);
}

/* ── 分隔線 ── */
hr { border-color: rgba(59,130,246,0.15) !important; }

/* ── dataframe 背景 ── */
[data-testid="stDataFrame"] {
    border: 1px solid rgba(59,130,246,0.15);
    border-radius: 10px;
    overflow: hidden;
}
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# ── 2. 完整 371 檔股票字串
# ==============================================================================
STOCK_STRING = """
2454聯發科3035智原3443創意3661世芯-KY6526達發5269祥碩3529力旺5274信驊6643M316533晶心科2379瑞昱4919新唐2401凌陽3041揚智2363矽統8227巨有科技2388威盛3014聯陽3094聯傑3122笙泉3135凌航3169亞信3228金麗科3259鑫創4952凌通4968立積5272笙科5471松翰6103合邦6104創惟6129普誠6202盛群6229研通6233旺玖6237驊訊6243迅杰6462神盾6494九齊6679鈺太6693廣閎科6716應廣6756威鋒電子6909創控7556意德士6568宏觀2330台積電2303聯電5347世界6770力積電2344華邦電2481強茂8261富鼎3707漢磊5425台半6435大中3675德微5299杰力6719#N/A2302麗正2329華泰2340光磊2342茂矽3105穩懋3686達能4923力士6552易華電6937天虹7712博盛半導體8086宏捷科8162微矽電子1560中砂3583辛耘6187萬潤6640均華3131弘塑3551世禾3413京鼎8028昇陽半導體4770上品3016嘉晶5536聖暉5543崇佑-KY3663鑫科6953家碩2338光罩3374精材3467台灣精材6261久元6548長科*6854錼創科技3711日月光投控2449京元電子6239力成6147頎邦3264欣銓6510精測6223旺矽6515穎崴2360致茂6271同欣電8150南茂6257矽格8110華東8131福懋科3265台星科6683雍智科技6788華景電7734印能科技2351順德2369菱生2434統懋2441超豐3178公準3372典範3581博磊5302太欣5344立衛6208日揚6411晶焱6423億而得6525捷敏-KY7768頌勝科技7822倍利科8383千附3030德律5285界霖2337旺宏2408南亞科3006晶豪科2451創見4967十銓8271宇瞻8299群聯3260威剛6531愛普8088品安3268海德威6732昇佳電子4973廣穎5351鈺創8040九暘6485點序8054安國8277商丞2436偉詮電3257虹冠電3317尼克森3438類比科3588通嘉6138茂達6291沛亨6415矽力-KY6651全宇昕6799來頡6996力領科技8081致新6488環球晶3532台勝科6182合晶5483中美晶3680家登4749新應材6532瑞耘8091翔名3029零壹3150鈺寶3555重鵬3567逸昌4951精拓科5443均豪6573虹揚-KY6720久昌6823濾能6829千附精密6895宏碩系統6921嘉雨思7704明遠精密7749意騰-KY7751竑騰7769鴻勁7810捷創科技8024佑華8102傑霖科技2404漢唐6139亞翔6196帆宣6215和椿6438迅得6691洋基工程6698旭暉應材7730暉盛7828創新服務3037欣興8046南電3189景碩2383台光電2368金像電6274台燿4958臻鼎-KY6269台郡2313華通6191精成科5469瀚宇博2367燿華3044健鼎3645達邁3715定穎投控6213聯茂6672騰輝電子-KY8039台虹8213志超6108競國6153嘉聯益2317鴻海3231緯創2382廣達6669緯穎2356英業達3706神達4938和碩8210勤誠3013晟銘電2395研華6414樺漢6166凌華3088艾訊8050廣積3022威強電3416融程電2324仁寶2353宏碁2354鴻準2357華碩2376技嘉2377微星2385群光3515華擎6117迎廣6933AMAX-KY7711永擎2059川湖3017奇鋐3324雙鴻2421建準3653健策4931新盛力6230超眾6831邁科6805富世達2308台達電6409旭隼6412群電6282康舒6121新普3211順達2301光寶科2420新巨2457飛宏3015全漢3617碩天6781AES-KY4979華星光3163波若威6451訊芯-KY4908前鼎6442光聖3450聯鈞3596智易3363上詮3081聯亞5222全訊5487通泰7770君曜7772耀穎2345智邦5388中磊6285啟碁4906正文2455全新3047訊舟3380明泰3704合勤控4977眾達-KY6416瑞祺電通5468凱鈺2409友達3008大立光3019亞光3362先進光3406玉晶光3454晶睿3481群創3504揚明光3630新鉅科4976佳凌6209今國光6789采鈺2458義隆3034聯詠3141晶宏3227原相3527聚積3530晶相光3545敦泰3556禾瑞亞3592瑞鼎4961天鈺5236凌陽創新6684安格6695芯鼎6962奕力-KY8016矽創3023信邦3665貿聯-KY6279胡連6205詮欣3217優群3376新日興2392正崴2462良得電3533嘉澤6133金橋6197佳必琪6272驊陞6715嘉基8103瀚荃3491昇達科7717萊德光電2485兆赫3138耀登3062建漢2314台揚2312金寶2419仲琦2355敬鵬4916事欣科6443元晶2327國巨3624光頡6207雷科2478大毅8042金山電3117年程3026禾伸堂2472立隆電8043蜜望實6173信昌電6127九豪2492華新科3236千如6155鈞寶6834天二科技6204艾華6862三集瑞-KY3090日電貿2375凱美6449鈺邦6432今展科2428興勤6224聚鼎3191和進4760勤凱6175立敦6284佳邦5328華容3357臺慶科8121越峰5228鈺鎧7912新聿科3042晶技
"""


def extract_tickers(stock_str: str) -> list[str]:
    """
    使用正則表達式從股票字串中提取所有 4~5 位數的股號。

    ⚠️ 重要：Python 3 的 re 模組預設 Unicode 模式，
    中文字符也屬於 \\w（word character），導致 \\b 在
    「數字↔中文」交界處無法識別為 word boundary。
    加上 re.ASCII 旗標後，\\w 只匹配 ASCII [a-zA-Z0-9_]，
    中文變成 \\W，\\b 才能正確在數字與中文之間觸發。
    """
    codes = re.findall(r'\b(\d{4,5})\b', stock_str, re.ASCII)
    # 去重並保持原始順序
    seen: set[str] = set()
    unique_codes: list[str] = []
    for c in codes:
        if c not in seen:
            seen.add(c)
            unique_codes.append(c)
    return [f"{c}.TW" for c in unique_codes]


# ── 建立預設 ticker 清單
DEFAULT_TICKERS = extract_tickers(STOCK_STRING)

# ==============================================================================
# ── 3. 資料下載核心函式（帶快取）
# ==============================================================================

@st.cache_data(ttl=3600, show_spinner=False)
def load_raw_data(ticker_tuple: tuple, period: str = "1y") -> tuple:
    """
    批量下載股票資料，含 .TW/.TWO 智慧切換機制。

    yfinance group_by='ticker' 下載後的 MultiIndex 結構：
        columns = MultiIndex[(ticker, 'Close'), (ticker, 'High'), ...]
        即 level-0 = ticker，level-1 = OHLCV 欄位名稱

    參數：
        ticker_tuple : tuple of str  (用 tuple 讓 st.cache_data 可正確 hash)
        period       : 保留參數，目前以 start/end 控制

    回傳：
        (data_dict, success_count, skip_count)
        data_dict : dict[str → pd.DataFrame]  key = ticker(.TW 或 .TWO)
    """
    ticker_list   = list(ticker_tuple)
    data_dict     : dict[str, pd.DataFrame] = {}
    failed_tickers: list[str] = []   # 第一輪失敗，待 .TWO 補救
    success_count = 0
    skip_count    = 0

    BATCH_SIZE = 60       # 每批最多 60 檔，避免 Yahoo Finance 限流
    MIN_ROWS   = 100      # 最少有效資料筆數門檻
    END_DATE   = datetime.now()
    START_DATE = END_DATE - timedelta(days=420)  # 多抓 420 天確保 MA200 足夠

    # ════════════════════════════════════════════════════════════════════
    # 內部輔助：從 yf.download 原始輸出解析出各 ticker 的 DataFrame
    # ════════════════════════════════════════════════════════════════════
    def _parse_batch(raw: pd.DataFrame, batch: list[str]) -> tuple[dict, list]:
        """
        解析 yf.download 的批量結果（MultiIndex 或單層 columns）。
        回傳 (成功 dict, 失敗 ticker list)。

        yfinance ≥ 0.2 使用 group_by='ticker' 時：
            MultiIndex level-0 = ticker，level-1 = 欄位 (Close / High / …)
        """
        ok: dict[str, pd.DataFrame] = {}
        fail: list[str] = []

        if raw is None or raw.empty:
            fail.extend(batch)
            return ok, fail

        if isinstance(raw.columns, pd.MultiIndex):
            # ── 多 ticker 批量下載 ──
            # level_0_values 可能是 ticker（新版）或欄位名（舊版），
            # 根據第一個 batch ticker 是否在 level-0 來判斷方向。
            lv0 = set(raw.columns.get_level_values(0))
            lv1 = set(raw.columns.get_level_values(1))
            ticker_in_lv0 = any(t in lv0 for t in batch)

            for ticker in batch:
                try:
                    if ticker_in_lv0 and ticker in lv0:
                        # 正常情況：level-0 = ticker
                        df = raw[ticker].copy()
                    elif not ticker_in_lv0 and ticker in lv1:
                        # 舊版或特殊情況：level-1 = ticker
                        df = raw.xs(ticker, axis=1, level=1).copy()
                    else:
                        fail.append(ticker)
                        continue

                    # 確保 columns 是標準欄位名稱（有時會有多餘層）
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.droplevel(0)

                    df.index = pd.to_datetime(df.index)
                    df = df.dropna(subset=["Close"])

                    if len(df) < MIN_ROWS:
                        fail.append(ticker)
                    else:
                        ok[ticker] = df
                except Exception:
                    fail.append(ticker)

        else:
            # ── 單一 ticker（batch 長度 == 1）或 columns 已是平坦結構 ──
            if len(batch) == 1:
                ticker = batch[0]
                df = raw.copy()
                df.index = pd.to_datetime(df.index)
                df = df.dropna(subset=["Close"])
                if len(df) >= MIN_ROWS:
                    ok[ticker] = df
                else:
                    fail.append(ticker)
            else:
                # 批量下載卻拿到平坦 columns — 無法對應 ticker，全部標記失敗
                fail.extend(batch)

        return ok, fail

    # ════════════════════════════════════════════════════════════════════
    # 第一輪：批量下載 .TW
    # ════════════════════════════════════════════════════════════════════
    batches_tw = [ticker_list[i:i+BATCH_SIZE]
                  for i in range(0, len(ticker_list), BATCH_SIZE)]

    for batch in batches_tw:
        try:
            raw = yf.download(
                batch,
                start=START_DATE.strftime("%Y-%m-%d"),
                end=END_DATE.strftime("%Y-%m-%d"),
                group_by="ticker",
                threads=True,
                progress=False,
                auto_adjust=True,
            )
        except Exception:
            failed_tickers.extend(batch)
            continue

        ok, fail = _parse_batch(raw, batch)
        data_dict.update(ok)
        success_count += len(ok)
        failed_tickers.extend(fail)

    # ════════════════════════════════════════════════════════════════════
    # 第二輪：失敗的改用 .TWO 補救（只針對少數失敗股號，效率高）
    # ════════════════════════════════════════════════════════════════════
    if failed_tickers:
        # .TW → .TWO 對應表
        two_map: dict[str, str] = {}   # key=.TWO ticker, value=原 .TW ticker
        two_tickers: list[str] = []
        for t in failed_tickers:
            t_two = t.replace(".TW", ".TWO") if ".TW" in t else t + ".TWO"
            # 避免重複（同一股號出現兩次）
            if t_two not in two_map:
                two_map[t_two] = t
                two_tickers.append(t_two)

        batches_two = [two_tickers[i:i+BATCH_SIZE]
                       for i in range(0, len(two_tickers), BATCH_SIZE)]

        for batch in batches_two:
            try:
                raw2 = yf.download(
                    batch,
                    start=START_DATE.strftime("%Y-%m-%d"),
                    end=END_DATE.strftime("%Y-%m-%d"),
                    group_by="ticker",
                    threads=True,
                    progress=False,
                    auto_adjust=True,
                )
            except Exception:
                skip_count += len(batch)
                continue

            ok2, fail2 = _parse_batch(raw2, batch)

            for t_two, df in ok2.items():
                # 以 .TWO 為 key 存入 data_dict（K 線圖 lookup 也用同一 key）
                data_dict[t_two] = df
                success_count += 1

            skip_count += len(fail2)

    return data_dict, success_count, skip_count


# ==============================================================================
# ── 4. 技術指標計算工具函式
# ==============================================================================

def calc_ma(series: pd.Series, window: int) -> pd.Series:
    """計算簡單移動平均線"""
    return series.rolling(window=window, min_periods=window).mean()


def calc_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """計算 ATR（平均真實振幅）"""
    high = df["High"]
    low  = df["Low"]
    close = df["Close"]
    tr = pd.concat([
        high - low,
        (high - close.shift(1)).abs(),
        (low  - close.shift(1)).abs(),
    ], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()


# ==============================================================================
# ── 5. 核心篩選策略（不加快取，讓 Sidebar 參數即時生效）
# ==============================================================================

def filter_pullback_stocks(data_dict: dict, params: dict) -> pd.DataFrame:
    """
    依據多空量化策略篩選「波段拉回止跌轉折」個股。
    
    策略條件（全部可透過 params 調整）：
        1. 長線多頭：MA50 > MA200 且 Close > MA200
        2. 動能記憶：過去 N 天內曾創近 M 天新高
        3. 波段拉回：Close 與 MA20 距離在 ±X%
        4. 量縮洗盤：近 3 日均量 < 20 日均量 × Y
        5. 止跌轉折：今日 Close > 昨日 High
    """
    results = []

    for ticker, df in data_dict.items():
        try:
            if len(df) < 210:   # 資料不足，跳過
                continue

            df = df.copy().sort_index()

            close  = df["Close"]
            high   = df["High"]
            low    = df["Low"]
            volume = df["Volume"]

            # ── 均線計算 ──
            ma20  = calc_ma(close, 20)
            ma50  = calc_ma(close, 50)
            ma200 = calc_ma(close, 200)
            atr14 = calc_atr(df, 14)

            # ── 取最後一日有效資料 ──
            last_idx = -1
            c0  = close.iloc[last_idx]     # 今日收盤
            c1  = close.iloc[-2]           # 昨日收盤
            h1  = high.iloc[-2]            # 昨日最高
            ma20_0  = ma20.iloc[last_idx]
            ma50_0  = ma50.iloc[last_idx]
            ma200_0 = ma200.iloc[last_idx]
            atr_0   = atr14.iloc[last_idx]

            if any(pd.isna([c0, c1, h1, ma20_0, ma50_0, ma200_0, atr_0])):
                continue

            # ── 條件 1：長線多頭過濾 ──
            if not (ma50_0 > ma200_0 and c0 > ma200_0):
                continue

            # ── 條件 2：動能記憶（過去 N 天曾創 M 天新高）──
            n_days    = params["momentum_days"]     # 25
            m_window  = params["high_window"]       # 60
            look_back = close.iloc[-(n_days + 1):-1]
            rolling_high = high.rolling(m_window).max()
            recent_high_series = rolling_high.iloc[-(n_days + 1):-1]
            had_breakout = (look_back >= recent_high_series).any()
            if not had_breakout:
                continue

            # ── 條件 3：波段拉回（Close ≈ MA20 ± X%）──
            pullback_pct = params["pullback_pct"]   # 2.5
            distance_pct = (c0 - ma20_0) / ma20_0 * 100
            if abs(distance_pct) > pullback_pct:
                continue

            # ── 條件 4：量縮洗盤 ──
            vol_ratio = params["vol_ratio"]         # 0.75
            vol3  = volume.iloc[-4:-1].mean()       # 近 3 日均量（不含今日）
            vol20 = volume.iloc[-21:-1].mean()      # 近 20 日均量
            if pd.isna(vol3) or pd.isna(vol20) or vol20 == 0:
                continue
            vol_shrink = vol3 / vol20
            if vol_shrink >= vol_ratio:
                continue

            # ── 條件 5：止跌轉折 ──
            if c0 <= h1:
                continue

            # ── 優先第一波拉回篩選（過去 10 天內觸發次數少者優先）──
            trigger_window = 10
            triggers_in_window = 0
            for i in range(2, trigger_window + 2):
                if i + 1 > len(close):
                    break
                ci  = close.iloc[-i]
                hi1 = high.iloc[-(i+1)] if i+1 <= len(high) else np.nan
                ma20_i = ma20.iloc[-i]
                if pd.isna([ci, hi1, ma20_i]).any():
                    continue
                dist_i = abs((ci - ma20_i) / ma20_i * 100)
                if dist_i <= pullback_pct and ci > hi1:
                    triggers_in_window += 1
            is_first_pullback = (triggers_in_window <= 1)

            # ── 風險收益計算 ──
            # 停損：近兩日最低點下方 2% 或 ATR 擇大
            recent_low = min(low.iloc[-1], low.iloc[-2])
            stop_loss_atr   = c0 - 1.5 * atr_0
            stop_loss_pct   = recent_low * 0.98
            stop_loss       = max(stop_loss_atr, stop_loss_pct)   # 較嚴的那個
            stop_loss       = min(stop_loss, c0 * 0.95)            # 至少 5% 空間

            # 目標價：進場 +20% 或前波高點
            prev_high = high.iloc[-m_window:].max()
            target1   = c0 * 1.20
            target2   = prev_high * 1.02
            target    = max(target1, target2)

            # 損益比
            risk   = c0 - stop_loss
            reward = target - c0
            rr     = reward / risk if risk > 0 else 0

            if rr < params["min_rr"]:   # 最低損益比門檻
                continue

            # ── 漲跌幅 ──
            chg_pct = (c0 - c1) / c1 * 100 if c1 != 0 else 0

            # ── 代號整理（去掉 .TW / .TWO 後綴）──
            code = ticker.replace(".TWO", "").replace(".TW", "")

            results.append({
                "代號":       code,
                "Ticker":    ticker,
                "收盤價":     round(c0, 2),
                "漲跌幅(%)":  round(chg_pct, 2),
                "拉回深度(%)": round(distance_pct, 2),
                "量縮比":     round(vol_shrink, 2),
                "停損價":     round(stop_loss, 2),
                "目標價":     round(target, 2),
                "損益比(RR)": round(rr, 2),
                "第一波拉回": "✅" if is_first_pullback else "—",
                "MA20":       round(ma20_0, 2),
                "MA50":       round(ma50_0, 2),
                "MA200":      round(ma200_0, 2),
            })

        except Exception:
            continue

    if not results:
        return pd.DataFrame()

    result_df = pd.DataFrame(results)
    result_df = result_df.sort_values("損益比(RR)", ascending=False).reset_index(drop=True)
    return result_df


# ==============================================================================
# ── 6. K 線圖繪製（Plotly）
# ==============================================================================

def plot_candlestick(df: pd.DataFrame, ticker: str) -> go.Figure:
    """
    繪製精美 Plotly K 線圖，含：
    - Candlestick（台股紅漲綠跌）
    - MA20（橙）、MA50（藍）、MA200（紅）
    - Volume 子圖（漲紅跌綠）
    - Rangeslider
    """
    df = df.copy().sort_index().tail(250)  # 只取最近 250 個交易日

    # ── 均線計算 ──
    df["MA20"]  = calc_ma(df["Close"], 20)
    df["MA50"]  = calc_ma(df["Close"], 50)
    df["MA200"] = calc_ma(df["Close"], 200)

    # ── K 棒顏色 ──
    colors = ["#ef4444" if c >= o else "#22c55e"
              for c, o in zip(df["Close"], df["Open"])]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.72, 0.28],
        subplot_titles=(
            f"{ticker.replace('.TWO','').replace('.TW','')} — K 線與均線",
            "成交量"
        )
    )

    # ── K 線 ──
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"], high=df["High"],
            low=df["Low"],   close=df["Close"],
            increasing_line_color="#ef4444",
            decreasing_line_color="#22c55e",
            increasing_fillcolor="#ef4444",
            decreasing_fillcolor="#22c55e",
            name="K線",
            line=dict(width=1),
        ),
        row=1, col=1,
    )

    # ── MA20 橙線 ──
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MA20"],
                   line=dict(color="#fb923c", width=1.5),
                   name="MA20", opacity=0.9),
        row=1, col=1,
    )
    # ── MA50 藍線 ──
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MA50"],
                   line=dict(color="#60a5fa", width=1.8),
                   name="MA50", opacity=0.9),
        row=1, col=1,
    )
    # ── MA200 紅線 ──
    fig.add_trace(
        go.Scatter(x=df.index, y=df["MA200"],
                   line=dict(color="#f43f5e", width=2, dash="dot"),
                   name="MA200", opacity=0.85),
        row=1, col=1,
    )

    # ── 成交量長條 ──
    fig.add_trace(
        go.Bar(
            x=df.index, y=df["Volume"],
            marker_color=colors,
            name="成交量",
            opacity=0.75,
        ),
        row=2, col=1,
    )

    # ── 外觀設定 ──
    fig.update_layout(
        height=600,
        paper_bgcolor="#0d1526",
        plot_bgcolor="#0d1526",
        font=dict(color="#94a3b8", size=11, family="Noto Sans TC"),
        legend=dict(
            orientation="h",
            yanchor="bottom", y=1.02,
            xanchor="right", x=1,
            bgcolor="rgba(13,21,38,0.8)",
            font=dict(size=11),
        ),
        xaxis_rangeslider_visible=True,
        xaxis_rangeslider=dict(
            bgcolor="#0a0e1a",
            bordercolor="rgba(59,130,246,0.2)",
            thickness=0.04,
        ),
        margin=dict(l=10, r=10, t=40, b=10),
    )
    fig.update_xaxes(
        gridcolor="rgba(59,130,246,0.08)",
        linecolor="rgba(59,130,246,0.2)",
        tickfont=dict(size=10),
    )
    fig.update_yaxes(
        gridcolor="rgba(59,130,246,0.08)",
        linecolor="rgba(59,130,246,0.2)",
        tickfont=dict(size=10),
    )

    # ── 子圖標題顏色 ──
    for ann in fig.layout.annotations:
        ann.font.color = "#64748b"
        ann.font.size  = 11

    return fig


# ==============================================================================
# ── 7. Streamlit UI 主程式
# ==============================================================================

def main():
    # ── 精美標題 ──────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="hero-header">
        <p class="hero-title">📡 台股波段拉回選股系統</p>
        <p class="hero-subtitle">
            半導體 · AI · 衛星通訊完整供應鏈｜多頭趨勢下高損益比強勢股篩選｜量縮止跌轉折策略
        </p>
    </div>
    """, unsafe_allow_html=True)

    # ── 策略說明 ───────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="strategy-info">
        🎯 <strong>策略核心：</strong>在多頭趨勢中，篩選已有強勢動能、正在拉回整理、
        出現量縮止跌轉折訊號的個股。<br>
        📌 <strong>條件組合：</strong>
        <strong>① 長線多頭</strong>（MA50 > MA200，Close > MA200）→
        <strong>② 動能記憶</strong>（近期曾創新高）→
        <strong>③ 波段拉回</strong>（Close ≈ MA20）→
        <strong>④ 量縮洗盤</strong>（近 3 日量 < 20 日量 × 門檻）→
        <strong>⑤ 止跌轉折</strong>（今收 > 昨高）。
    </div>
    """, unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ── SIDEBAR ───────────────────────────────────────────────────────────────
    # ══════════════════════════════════════════════════════════════════════════
    with st.sidebar:
        st.markdown("### ⚙️ 策略參數設定")

        # ── 長線多頭（固定條件，顯示說明）──
        st.markdown("**① 長線多頭過濾**")
        st.caption("MA50 > MA200 且 Close > MA200（固定條件）")

        st.divider()

        # ── 動能記憶 ──
        st.markdown("**② 動能記憶**")
        momentum_days = st.slider("回看天數 N（近 N 天內曾創新高）", 5, 60, 25, 5,
                                  help="過去幾個交易日內，需曾觸及近期高點")
        high_window   = st.slider("新高判定窗口 M（近 M 天最高）", 20, 120, 60, 5,
                                  help="判斷「新高」所用的回顧天數")

        st.divider()

        # ── 波段拉回 ──
        st.markdown("**③ 波段拉回幅度**")
        pullback_pct = st.slider("Close 與 MA20 距離 ±X%", 0.5, 8.0, 2.5, 0.5,
                                 help="收盤與 MA20 的偏離幅度，越小越嚴格")

        st.divider()

        # ── 量縮洗盤 ──
        st.markdown("**④ 量縮洗盤比例**")
        vol_ratio = st.slider("近 3 日均量 < 20 日均量 × Y", 0.3, 1.0, 0.75, 0.05,
                              help="量縮比例越小表示量縮越明顯，更嚴格")

        st.divider()

        # ── 損益比門檻 ──
        st.markdown("**⑤ 損益比門檻**")
        min_rr = st.slider("最低損益比 (RR)", 1.0, 5.0, 2.0, 0.5,
                           help="低於此值的個股不列入結果")

        st.divider()

        # ── 股票清單編輯區 ──
        st.markdown("### 📋 股票池編輯")
        default_codes = "\n".join([t.replace(".TW", "") for t in DEFAULT_TICKERS])
        user_input = st.text_area(
            "股號清單（每行一個，4~5 位數）",
            value=default_codes,
            height=200,
            help="可自訂篩選股票池，系統自動判斷上市(.TW) 或 上櫃(.TWO)"
        )
        # 解析使用者輸入（同樣加 re.ASCII，避免中文干擾 \b 邊界判斷）
        user_codes = re.findall(r'\b(\d{4,5})\b', user_input, re.ASCII)
        user_tickers = list({f"{c}.TW" for c in user_codes})  # 去重

        st.caption(f"已設定 {len(user_tickers)} 檔股票")

        st.divider()

        # ── 模式切換 ──
        st.markdown("### 🔄 掃描模式")
        scan_mode = st.radio(
            "選擇模式",
            ["手動掃描", "調整參數即時篩選（需已載入資料）"],
            index=0,
        )

        # ── 執行按鈕 ──
        run_btn = st.button("🚀 開始掃描", type="primary", use_container_width=True)

    # ══════════════════════════════════════════════════════════════════════════
    # ── 主頁面邏輯
    # ══════════════════════════════════════════════════════════════════════════

    params = {
        "momentum_days": momentum_days,
        "high_window":   high_window,
        "pullback_pct":  pullback_pct,
        "vol_ratio":     vol_ratio,
        "min_rr":        min_rr,
    }

    # ── 觸發掃描條件 ──
    should_scan = (
        run_btn or
        (scan_mode == "調整參數即時篩選（需已載入資料）" and "data_dict" in st.session_state)
    )

    if should_scan:
        # ════════════════════════════════════════════════════════════════
        # ── 資料下載或使用快取 ──
        # ════════════════════════════════════════════════════════════════
        if run_btn or "data_dict" not in st.session_state:
            # 首次或手動重新掃描：顯示進度條並執行下載
            progress_bar = st.progress(0, text="⏳ 正在下載股票資料，請稍候（首次約 1~3 分鐘）...")
            ticker_tuple = tuple(user_tickers)

            with st.spinner("下載中..."):
                data_dict, success_cnt, skip_cnt = load_raw_data(ticker_tuple)

            # 將結果存入 session_state，供「即時篩選」模式重複使用
            st.session_state["data_dict"]   = data_dict
            st.session_state["success_cnt"] = success_cnt
            st.session_state["skip_cnt"]    = skip_cnt

            progress_bar.progress(60, text="✅ 資料下載完成，正在套用選股策略...")

        else:
            # 使用已快取的資料，跳過下載直接篩選
            data_dict   = st.session_state["data_dict"]
            success_cnt = st.session_state["success_cnt"]
            skip_cnt    = st.session_state["skip_cnt"]
            # 建立一個空佔位元件，確保後續 .empty() 不會 NameError
            progress_bar = st.empty()

        # ── 套用選股策略（不帶快取，讓 Sidebar 參數即時生效）──
        with st.spinner("🔍 正在套用選股策略..."):
            result_df = filter_pullback_stocks(data_dict, params)

        # 清除進度條
        try:
            progress_bar.empty()
        except Exception:
            pass

        # ── 指標卡片 ──
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("📊 掃描股票總數", f"{len(data_dict):,} 檔")
        with col2:
            st.metric("✅ 成功下載", f"{success_cnt:,} 檔")
        with col3:
            st.metric("⏭️ 跳過 / 失敗", f"{skip_cnt:,} 檔")
        with col4:
            st.metric("🎯 符合條件", f"{len(result_df):,} 檔",
                      delta=f"損益比 ≥ {min_rr}" if len(result_df) > 0 else None)

        st.divider()

        # ── 結果表格 ──
        if result_df.empty:
            st.warning("⚠️ 目前市況下，沒有符合所有條件的個股。建議放寬參數後重新掃描。")
        else:
            st.markdown(f"### 📋 篩選結果（共 {len(result_df)} 檔，依損益比降序排列）")

            # ── 顯示表格（含美化）──
            display_df = result_df[[
                "代號", "收盤價", "漲跌幅(%)", "拉回深度(%)",
                "量縮比", "停損價", "目標價", "損益比(RR)", "第一波拉回"
            ]].copy()

            st.dataframe(
                display_df,
                use_container_width=True,
                height=min(600, 45 + 38 * len(display_df)),
                column_config={
                    "代號":        st.column_config.TextColumn("代號", width="small"),
                    "收盤價":      st.column_config.NumberColumn("收盤價", format="%.2f"),
                    "漲跌幅(%)":   st.column_config.NumberColumn(
                        "漲跌幅(%)",
                        format="%.2f%%",
                        help="台股：紅=漲、綠=跌",
                    ),
                    "拉回深度(%)": st.column_config.NumberColumn(
                        "拉回深度(%)", format="%.2f%%"
                    ),
                    "量縮比":      st.column_config.ProgressColumn(
                        "量縮比", min_value=0, max_value=1, format="%.2f"
                    ),
                    "停損價":      st.column_config.NumberColumn("停損價", format="%.2f"),
                    "目標價":      st.column_config.NumberColumn("目標價", format="%.2f"),
                    "損益比(RR)":  st.column_config.NumberColumn(
                        "損益比 RR", format="%.2f",
                        help="(目標價−收盤) / (收盤−停損)"
                    ),
                    "第一波拉回":  st.column_config.TextColumn("首波拉回", width="small"),
                },
                hide_index=True,
            )

            # ── CSV 下載 ──
            csv_buf = io.StringIO()
            result_df.to_csv(csv_buf, index=False, encoding="utf-8-sig")
            st.download_button(
                label="⬇️ 下載完整結果 CSV",
                data=csv_buf.getvalue(),
                file_name=f"pullback_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime="text/csv",
            )

            st.divider()

            # ── K 線圖區塊 ──
            st.markdown("### 📈 個股 K 線圖")
            ticker_options = result_df["Ticker"].tolist()
            label_options  = [
                f"{row['代號']} (RR={row['損益比(RR)']})"
                for _, row in result_df.iterrows()
            ]

            selected_label = st.selectbox(
                "選擇個股查看 K 線圖",
                options=label_options,
                index=0,
            )
            selected_idx    = label_options.index(selected_label)
            selected_ticker = ticker_options[selected_idx]

            if selected_ticker in data_dict:
                df_chart = data_dict[selected_ticker]
                fig = plot_candlestick(df_chart, selected_ticker)
                st.plotly_chart(fig, use_container_width=True)

                # ── 個股資訊面板 ──
                row_data = result_df[result_df["Ticker"] == selected_ticker].iloc[0]
                c1, c2, c3, c4 = st.columns(4)
                with c1:
                    st.metric("收盤價",  f"${row_data['收盤價']:.2f}",
                              delta=f"{row_data['漲跌幅(%)']:.2f}%")
                with c2:
                    st.metric("建議停損", f"${row_data['停損價']:.2f}")
                with c3:
                    st.metric("預估目標", f"${row_data['目標價']:.2f}")
                with c4:
                    st.metric("損益比 RR", f"{row_data['損益比(RR)']:.2f}x")

    else:
        # ── 尚未執行掃描時的提示 ──
        st.info("👈 請在左側 Sidebar 調整策略參數後，點擊「🚀 開始掃描」啟動選股引擎。")

        # ── 參數預覽 ──
        st.markdown("### 📐 目前策略參數預覽")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"""
            | 參數 | 設定值 |
            |------|--------|
            | 動能回看天數 N | **{momentum_days}** 天 |
            | 新高判定窗口 M | **{high_window}** 天 |
            | 拉回深度 ±X% | **{pullback_pct}%** |
            """)
        with col2:
            st.markdown(f"""
            | 參數 | 設定值 |
            |------|--------|
            | 量縮比 Y | **{vol_ratio}** |
            | 最低損益比 | **{min_rr}x** |
            | 股票池規模 | **{len(user_tickers)}** 檔 |
            """)

    # ── 風險提醒 ──
    st.markdown("""
    <div class="risk-warning">
        ⚠️ <strong>風險提醒：</strong>
        本系統僅供技術分析參考，不構成任何投資建議。
        股市投資有風險，過去績效不代表未來表現。請依個人風險承受能力自行判斷，並嚴格執行停損紀律。
    </div>
    """, unsafe_allow_html=True)


# ==============================================================================
# ── 8. 程式進入點
# ==============================================================================
if __name__ == "__main__":
    main()


# ==============================================================================
# ── APPENDIX：requirements.txt 與部署說明
# ==============================================================================
#
# ── requirements.txt（請另存為 requirements.txt，與 app.py 同目錄）──
#
#   streamlit>=1.35.0
#   yfinance>=0.2.40
#   pandas>=2.1.0
#   numpy>=1.26.0
#   plotly>=5.20.0
#
# ── 本地端執行（Mac / Linux / Windows）──
#
#   Step 1：建立虛擬環境（可選）
#     python -m venv venv
#     source venv/bin/activate          # Mac / Linux
#     venv/Scripts/activate             # Windows (Git Bash)
#
#   Step 2：安裝依賴
#     pip install -r requirements.txt
#
#   Step 3：啟動應用
#     streamlit run app.py
#     → 瀏覽器開啟 http://localhost:8501
#
# ── GitHub + Streamlit Cloud 部署步驟 ──
#
#   1. 在 GitHub 建立新 Repo（例如 taiwan-stock-scanner）
#   2. 上傳 app.py 與 requirements.txt（及可選的 .gitignore）到 Repo 根目錄
#   3. 前往 https://share.streamlit.io/ → New app
#   4. 選擇 GitHub Repo、分支（main）、Main file path = app.py
#   5. 點擊 Deploy! → 等待約 2~3 分鐘自動安裝依賴並啟動
#
# ── 注意事項 ──
#   · Streamlit Cloud 免費版記憶體約 1 GB，首次載入 371 檔約需 1~3 分鐘
#   · 快取 ttl=3600（1 小時），減少重複下載
#   · 若 Yahoo Finance 有時段性限流，稍後重試或縮減股票池規模
# ==============================================================================
