import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go

st.set_page_config(page_title="Family Portfolio", layout="wide")

# -----------------------------
# 설정
# -----------------------------
DISPLAY_TO_CANONICAL = {
    "현금성 (KOFR)": "금리",
    "미국 국채": "미국채",
}
CANONICAL_TO_DISPLAY = {
    "금리": "현금성 (KOFR)",
    "미국채": "미국 국채",
    "현금": "현금",
}

CATEGORY_TARGETS = {
    "세액공제 O": {
        "S&P500": 0.45,
        "나스닥100": 0.25,
        "금": 0.15,
        "미국채": 0.10,
        "금리": 0.05,
    },
    "세액공제 X": {
        "S&P500": 0.45,
        "나스닥100": 0.25,
        "금": 0.15,
        "미국채": 0.10,
        "금리": 0.05,
    },
    "ISA": {
        "다우존스": 0.50,
        "S&P500": 0.20,
        "금리": 0.30,
    },
}
CATEGORY_ORDER = ["세액공제 O", "세액공제 X", "ISA"]
CATEGORY_ORDER_MAP = {name: i for i, name in enumerate(CATEGORY_ORDER)}

IRP_SAFE_ASSETS = {"금", "미국채", "금리"}
FX_TARGETS_HIGH = {"환노출": 30, "환헤지": 70}
FX_TARGETS_MID = {"환노출": 50, "환헤지": 50}
FX_TARGETS_LOW = {"환노출": 80, "환헤지": 20}

# 수동 조절용
DONUT_OUTER_OPACITY = 0.40
DONUT_OVERALL_HEIGHT = 550  # 전체/카테고리 도넛 높이
DONUT_FX_HEIGHT = 550        # 환율 도넛 높이

# 모바일 겹침 완화용 여백/범례 설정
MOBILE_DONUT_TOP_MARGIN = -20
MOBILE_DONUT_BOTTOM_MARGIN = -20
MOBILE_LEGEND_Y = 0.1

# 도넛 크기 조절
# 숫자를 바깥쪽으로 넓히면 도넛이 커지고, 안쪽으로 좁히면 도넛이 작아짐
DONUT_CURRENT_DOMAIN = {"x": [0.20, 0.80], "y": [0.20, 0.80]}   # 현재 도넛
DONUT_TARGET_DOMAIN = {"x": [0.06, 0.94], "y": [0.06, 0.94]}     # 목표 도넛
DONUT_FX_CURRENT_DOMAIN = {"x": [0.22, 0.78], "y": [0.22, 0.78]} # 환율 현재 도넛
DONUT_FX_TARGET_DOMAIN = {"x": [0.08, 0.92], "y": [0.08, 0.92]}  # 환율 목표 도넛

# 환율관리 탭 도넛 색상
FX_COLOR_MAP = {
    "환노출": "#ff7f0e",  # 주황색 계열
    "환헤지": "#1f77b4",  # 파랑색 계열
}

DISPLAY_WEIGHT_THRESHOLD = 0.1

CODE_MAP = {
    "S&P500": {"노출": "360750", "헤지": "448290", "label": "S&P500"},
    "나스닥100": {"노출": "133690", "헤지": "448300", "label": "나스닥100"},
    "다우존스": {"노출": "458730", "헤지": "452360", "label": "다우존스"},
    "금": {"기본": "411060", "label": "금"},
    "미국채": {"기본": "305080", "label": "미국채"},
    "금리": {"기본": "423160", "label": "한국금리"},
}

st.markdown(
    """
    <style>
    html, body, [class*="css"] { font-size: 12px !important; }
    .stApp {
        background: linear-gradient(180deg, #07101f 0%, #0b1220 100%);
    }
    h1, h2, h3 { letter-spacing: -0.02em !important; }
    h1 { font-size: 1.25rem !important; margin-bottom: 0.35rem !important; }
    h2 { font-size: 1.10rem !important; }
    h3 { font-size: 1.00rem !important; }

    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 1.5rem !important;
        max-width: 980px !important;
    }

    .stDataFrame div { font-size: 11px !important; }

    div[data-testid="stTabs"] { margin-top: 0.65rem !important; }
    div[data-testid="stTabs"] button {
        padding-top: 0.55rem !important;
        padding-bottom: 0.55rem !important;
        border-radius: 10px 10px 0 0 !important;
    }

    div[data-testid="stMetric"] {
        background: rgba(17, 24, 39, 0.88);
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 16px;
        padding: 14px 14px 10px 14px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.16);
    }
    div[data-testid="stMetricLabel"] { color: #94a3b8 !important; }
    div[data-testid="stMetricValue"] { font-weight: 750 !important; }

    div[data-testid="stExpander"] {
        border: 1px solid rgba(148,163,184,0.12) !important;
        border-radius: 14px !important;
        background: rgba(15,23,42,0.75) !important;
    }

    .app-card {
        background: rgba(15, 23, 42, 0.76);
        border: 1px solid rgba(148, 163, 184, 0.10);
        border-radius: 18px;
        padding: 14px 14px 10px 14px;
        margin: 10px 0 14px 0;
        box-shadow: 0 10px 24px rgba(0,0,0,0.14);
        overflow: hidden !important;
    }
    .app-card-title {
        font-size: 1rem;
        font-weight: 700;
        margin-bottom: 2px;
    }
    .app-card-caption {
        color: #94a3b8;
        font-size: 0.82rem;
        margin-bottom: 8px;
    }
    .app-hero {
        background: linear-gradient(135deg, rgba(30,41,59,0.96), rgba(15,23,42,0.96));
        border: 1px solid rgba(148,163,184,0.12);
        border-radius: 20px;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 14px 30px rgba(0,0,0,0.16);
    }
    .app-hero-title { color: #94a3b8; font-size: 0.82rem; margin-bottom: 4px; }
    .app-hero-value {
        font-size: 1.9rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        margin-bottom: 2px;
    }
    .app-hero-sub { color: #cbd5e1; font-size: 0.86rem; }

    .js-plotly-plot { margin-bottom: 6px !important; overflow: hidden !important; }
    [data-testid="stPlotlyChart"] {
        padding-top: 0 !important;
        padding-bottom: 0 !important;
        overflow: hidden !important;
    }
    [data-testid="stPlotlyChart"] > div {
        overflow: hidden !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# -----------------------------
# 유틸
# -----------------------------
def open_card(title=None, caption=None):
    title_html = f'<div class="app-card-title">{title}</div>' if title else ""
    caption_html = f'<div class="app-card-caption">{caption}</div>' if caption else ""
    st.markdown(f'<div class="app-card">{title_html}{caption_html}', unsafe_allow_html=True)

def close_card():
    st.markdown("</div>", unsafe_allow_html=True)

def normalize_asset_group(value):
    raw = "" if pd.isna(value) else str(value).strip()
    return DISPLAY_TO_CANONICAL.get(raw, raw)


def display_asset_group(value):
    return CANONICAL_TO_DISPLAY.get(value, value)


def safe_format(val):
    try:
        return f"{float(val):,.0f}"
    except Exception:
        return val


FORMAT_RULES = {
    "평가액": "{:,.0f}",
    "평가금액": "{:,.0f}",
    "매수금액": "{:,.0f}",
    "현재가": lambda x: safe_format(x),
    "수량": lambda x: safe_format(x),
    "보유수량": lambda x: safe_format(x),
    "평단": lambda x: safe_format(x),
    "매수평단": lambda x: safe_format(x),
    "수익률": "{:.2f}%",
    "비중": "{:.1f}%",
    "목표": "{:.1f}%",
    "차이": "{:+.1f}%",
    "목표금액": "{:,.0f}",
    "현재금액": "{:,.0f}",
    "차액": "{:+,.0f}",
    "예상주문": "{:+,.0f}",
    "조정수량": "{:+,.0f}",
    "현재 안전자산 비중": "{:.1f}%",
    "목표 안전자산 비중": "{:.1f}%",
    "부족 안전자산": "{:.1f}%",
}


def get_target_order_map(targets_dict):
    if not targets_dict:
        return {}
    sorted_items = sorted(targets_dict.items(), key=lambda x: (-float(x[1]), display_asset_group(x[0])))
    return {asset: idx for idx, (asset, _) in enumerate(sorted_items)}


def add_sort_columns(df, asset_col="자산군", amount_col="평가금액", targets_dict=None):
    out = df.copy()
    order_map = get_target_order_map(targets_dict or {})
    out["_asset_order"] = out[asset_col].map(order_map).fillna(999).astype(int)
    out["_amount_sort"] = pd.to_numeric(out.get(amount_col, 0), errors="coerce").fillna(0)
    return out


def filter_display_rows(df, show_all=False, min_weight=DISPLAY_WEIGHT_THRESHOLD):
    if df is None:
        return df
    out = df.copy()
    if show_all:
        return out

    qty_col = "보유수량" if "보유수량" in out.columns else ("수량" if "수량" in out.columns else None)
    if qty_col:
        qty = pd.to_numeric(out[qty_col], errors="coerce").fillna(0)
        out = out[qty > 0].copy()

    value_col = "평가금액" if "평가금액" in out.columns else ("평가액" if "평가액" in out.columns else None)
    if value_col:
        val = pd.to_numeric(out[value_col], errors="coerce").fillna(0)
        out = out[val > 0].copy()

    if "비중" in out.columns:
        wt = pd.to_numeric(out["비중"], errors="coerce").fillna(0)
        out = out[wt.abs() >= float(min_weight)].copy()

    return out


def style_table(df, cols, show_all=False, min_weight=DISPLAY_WEIGHT_THRESHOLD):
    filtered = filter_display_rows(df, show_all=show_all, min_weight=min_weight)
    cols = [c for c in cols if c in filtered.columns]
    view = filtered[cols].copy().astype(object)

    cash_mask = None
    if "종목코드" in filtered.columns:
        cash_mask = filtered["종목코드"].astype(str).str.upper().eq("CASH")
    elif "자산군" in filtered.columns:
        cash_mask = filtered["자산군"].astype(str).eq("현금")

    if cash_mask is not None:
        for col in ["보유수량", "매수평단", "현재가"]:
            if col in view.columns:
                view.loc[cash_mask, col] = "-"

    rename_map = {
        "계좌명": "계좌",
        "약식종목명": "종목",
        "자산군_표시": "자산군",
        "보유수량": "수량",
        "매수평단": "평단",
        "평가금액": "평가액",
    }
    view = view.rename(columns=rename_map)
    format_rules = {k: v for k, v in FORMAT_RULES.items() if k in view.columns}
    return view.style.format(format_rules)


def highlight_underweight_rows(row):
    if "비중" in row.index and "목표" in row.index:
        try:
            current_weight = float(row["비중"])
            target_weight = float(row["목표"])
            if current_weight < target_weight:
                return ["color: #d32f2f; font-weight: 600"] * len(row)
        except Exception:
            pass
    return [""] * len(row)


def make_dual_donut(
    current_df,
    current_value_col,
    current_name_col,
    target_map,
    title,
    height,
    current_domain,
    target_domain,
    current_hole=0.48,
    target_hole=0.72,
    current_color_map=None,
    target_color_map=None,
):
    current_names = [str(x) for x in current_df[current_name_col].fillna("").tolist()]
    target_names = [display_asset_group(k) for k in target_map.keys()]
    names = list(dict.fromkeys(current_names + target_names))

    current_map = current_df.groupby(current_name_col)[current_value_col].sum().to_dict()
    current_vals = [float(current_map.get(name, 0)) for name in names]
    target_display_map = {display_asset_group(k): float(v) for k, v in target_map.items()}
    target_vals = [target_display_map.get(name, 0.0) for name in names]

    fig = go.Figure()
    current_colors = [current_color_map.get(name) for name in names] if current_color_map else None
    target_colors = [target_color_map.get(name) for name in names] if target_color_map else None

    fig.add_trace(
        go.Pie(
            labels=names,
            values=current_vals,
            hole=current_hole,
            sort=False,
            direction="clockwise",
            textinfo="label+percent",
            domain=current_domain,
            marker=dict(colors=current_colors, line=dict(color="white", width=1)),
            name="현재",
        )
    )
    fig.add_trace(
        go.Pie(
            labels=names,
            values=target_vals,
            hole=target_hole,
            sort=False,
            direction="clockwise",
            textinfo="none",
            opacity=DONUT_OUTER_OPACITY,
            domain=target_domain,
            marker=dict(colors=target_colors, line=dict(color="white", width=1)),
            hovertemplate="<b>%{label}</b><br>목표: %{value:.1f}%<extra></extra>",
            name="목표",
        )
    )
    fig.update_layout(
        title=dict(text=title, y=0.98) if title else None,
        height=height,
        margin=dict(
            l=6,
            r=6,
            t=0 if not title else max(MOBILE_DONUT_TOP_MARGIN, 0),
            b=0 if not title else max(MOBILE_DONUT_BOTTOM_MARGIN, 0),
        ),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=MOBILE_LEGEND_Y,
            xanchor="center",
            x=0.5,
            tracegroupgap=6,
        ),
    )
    return fig


def calc_return(eval_amt, buy_amt):
    if pd.isna(buy_amt) or float(buy_amt) == 0:
        return 0.0
    return (float(eval_amt) - float(buy_amt)) / float(buy_amt) * 100.0


# -----------------------------
# 데이터 로드
# -----------------------------
def load_data():
    file_name = "my_assets.csv"
    try:
        df = pd.read_csv(file_name, encoding="utf-8-sig", dtype={"종목코드": str})
    except Exception:
        df = pd.read_csv(file_name, encoding="cp949", dtype={"종목코드": str})

    required_defaults = {
        "계좌명": "",
        "종목명": "",
        "종목코드": "CASH",
        "보유수량": 0,
        "매수평단": 0,
        "약식종목명": "",
        "계좌카테고리": "기타",
        "자산군": None,
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
            df[col] = default

    df["종목코드"] = df["종목코드"].fillna("CASH").astype(str).str.strip()
    df["보유수량"] = pd.to_numeric(df["보유수량"], errors="coerce").fillna(0)
    df["매수평단"] = pd.to_numeric(df["매수평단"], errors="coerce").fillna(0)
    df["자산군"] = df["자산군"].fillna(df["약식종목명"]).apply(normalize_asset_group)

    # 현금은 진짜 현금. KOFR와 별개로 유지
    is_cash = df["종목코드"].str.upper().eq("CASH") | df["약식종목명"].astype(str).eq("현금")
    df.loc[is_cash, "자산군"] = "현금"

    return df


@st.cache_data(ttl=300, show_spinner=False)
def get_price_data(codes):
    price_map = {}
    for code in codes:
        code = str(code).strip()
        if code.upper() in {"", "NAN", "CASH", "SEED"}:
            price_map[code] = 1.0
            continue
        try:
            hist = fdr.DataReader(code)
            price_map[code] = float(hist["Close"].iloc[-1]) if not hist.empty else 0.0
        except Exception:
            price_map[code] = 0.0
    return price_map


@st.cache_data(ttl=300, show_spinner=False)
def get_usdkrw():
    try:
        hist = fdr.DataReader("USD/KRW")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 1360.0


@st.cache_data(ttl=300, show_spinner=False)
def get_history_data(code, days=120):
    code = str(code).strip()
    if code.upper() in {"", "NAN", "CASH", "SEED"}:
        return pd.DataFrame()
    try:
        hist = fdr.DataReader(code)
        if hist is None or hist.empty:
            return pd.DataFrame()
        hist = hist.tail(days).copy()
        hist.index = pd.to_datetime(hist.index)
        return hist
    except Exception:
        return pd.DataFrame()


def get_daily_change_info(code):
    hist = get_history_data(code, days=5)
    if hist is None or hist.empty or "Close" not in hist.columns or len(hist) < 2:
        return None, None, None
    latest_close = float(hist["Close"].iloc[-1])
    prev_close = float(hist["Close"].iloc[-2])
    if prev_close == 0:
        return latest_close, prev_close, None
    pct = (latest_close - prev_close) / prev_close * 100.0
    return latest_close, prev_close, pct


def build_daily_alerts(asset_df, drop_threshold=-2.5):
    alerts = []
    unique_rows = (
        asset_df[["종목코드", "약식종목명"]]
        .dropna()
        .drop_duplicates()
        .to_dict("records")
    )
    for row in unique_rows:
        code = str(row["종목코드"]).strip()
        if code.upper() in {"", "NAN", "CASH", "SEED"}:
            continue
        _, _, pct = get_daily_change_info(code)
        if pct is not None and pct <= drop_threshold:
            alerts.append((row["약식종목명"], code, pct))
    return alerts


def make_price_chart(hist_df, avg_price=None, title="최근 120일 차트"):
    chart_df = hist_df.copy()
    if chart_df is None or chart_df.empty:
        return go.Figure()

    for col in ["Open", "High", "Low", "Close"]:
        if col not in chart_df.columns:
            return go.Figure()

    chart_df["MA20"] = chart_df["Close"].rolling(20).mean()
    chart_df["MA60"] = chart_df["Close"].rolling(60).mean()

    fig = go.Figure()

    # 한국 주식앱 느낌에 맞춰 상승=빨강, 하락=파랑
    fig.add_trace(
        go.Candlestick(
            x=chart_df.index,
            open=chart_df["Open"],
            high=chart_df["High"],
            low=chart_df["Low"],
            close=chart_df["Close"],
            increasing_line_color="#d32f2f",
            increasing_fillcolor="#d32f2f",
            decreasing_line_color="#1976d2",
            decreasing_fillcolor="#1976d2",
            name="일봉",
        )
    )

    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["MA20"],
            mode="lines",
            name="20일선",
            line=dict(color="#f4b400", width=1.8),
        )
    )

    fig.add_trace(
        go.Scatter(
            x=chart_df.index,
            y=chart_df["MA60"],
            mode="lines",
            name="60일선",
            line=dict(color="#34a853", width=1.8),
        )
    )

    if avg_price is not None and float(avg_price) > 0:
        fig.add_hline(
            y=float(avg_price),
            line_dash="dash",
            line_color="#6a1b9a",
            annotation_text=f"내 평단 {float(avg_price):,.0f}",
            annotation_position="top left",
        )

    fig.update_layout(
        title=dict(text=title, y=0.96),
        height=420,
        margin=dict(l=20, r=20, t=70, b=20),
        xaxis_title="날짜",
        yaxis_title="가격",
        xaxis_rangeslider_visible=False,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def prepare_asset_df(df_raw):
    seed_df = df_raw[df_raw["종목코드"].str.upper() == "SEED"].copy()
    asset_df = df_raw[df_raw["종목코드"].str.upper() != "SEED"].copy()

    codes = tuple(asset_df["종목코드"].dropna().astype(str).unique())
    price_map = get_price_data(codes)
    current_fx = get_usdkrw()

    asset_df["현재가"] = asset_df["종목코드"].map(price_map).fillna(0.0)
    asset_df["매수금액"] = asset_df.apply(
        lambda x: float(x["보유수량"]) if str(x["종목코드"]).upper() == "CASH" else float(x["보유수량"]) * float(x["매수평단"]),
        axis=1,
    )
    asset_df["평가금액"] = asset_df.apply(
        lambda x: float(x["보유수량"]) if str(x["종목코드"]).upper() == "CASH" else float(x["보유수량"]) * float(x["현재가"]),
        axis=1,
    )
    asset_df["수익률"] = asset_df.apply(lambda x: calc_return(x["평가금액"], x["매수금액"]), axis=1)

    return seed_df, asset_df, current_fx


def build_overall_target_mix(asset_df):
    investable_df = asset_df[asset_df["자산군"] != "현금"].copy()
    total_val = float(investable_df["평가금액"].sum())
    if total_val <= 0:
        return {}

    overall_amt = {}
    for cat_name, targets in CATEGORY_TARGETS.items():
        cat_total = float(investable_df.loc[investable_df["계좌카테고리"] == cat_name, "평가금액"].sum())
        for asset, weight in targets.items():
            overall_amt[asset] = overall_amt.get(asset, 0.0) + cat_total * float(weight)

    return {asset: (amt / total_val) * 100.0 for asset, amt in overall_amt.items()}


# -----------------------------
# 리밸런싱
# -----------------------------
def allocate_amounts_by_capacity(accounts, amount):
    remaining = max(float(amount), 0.0)
    allocation = {acc["name"]: 0.0 for acc in accounts}
    capacities = {acc["name"]: max(float(acc.get("capacity", 0)), 0.0) for acc in accounts}

    while remaining > 1 and sum(capacities.values()) > 0:
        total_cap = sum(capacities.values())
        progressed = 0.0
        for name, cap in list(capacities.items()):
            if cap <= 0:
                continue
            share = remaining * (cap / total_cap)
            add = min(cap, share)
            if add > 0:
                allocation[name] += add
                capacities[name] -= add
                progressed += add
        if progressed <= 1e-9:
            break
        remaining -= progressed

    return allocation, remaining


def choose_fx_side(asset, current_fx):
    if asset in {"S&P500", "나스닥100", "다우존스"}:
        return "헤지" if current_fx > 1380 else "노출"
    return "기본"


def get_fx_target_mix(current_fx):
    if current_fx > 1400:
        return FX_TARGETS_HIGH
    if current_fx < 1330:
        return FX_TARGETS_LOW
    return FX_TARGETS_MID


def choose_order_row(account_df, asset, current_fx):
    candidates = account_df[account_df["자산군"] == asset].copy()
    if not candidates.empty:
        if asset in {"S&P500", "나스닥100", "다우존스"}:
            prefer_hedged = current_fx > 1380
            hedged_mask = candidates["약식종목명"].astype(str).str.contains(r"\(H\)", regex=True, na=False)
            preferred = candidates[hedged_mask] if prefer_hedged else candidates[~hedged_mask]
            if not preferred.empty:
                candidates = preferred
        positive = candidates[candidates["현재가"] > 0]
        if not positive.empty:
            return positive.sort_values(["보유수량", "평가금액"], ascending=False).iloc[0].to_dict()
        return candidates.iloc[0].to_dict()

    meta = CODE_MAP.get(asset, {})
    side = choose_fx_side(asset, current_fx)
    code = meta.get(side) or meta.get("기본")
    if not code:
        return None
    return {
        "약식종목명": meta.get("label", asset) + ("(H)" if side == "헤지" else ""),
        "종목코드": code,
        "현재가": 0.0,
    }


def build_category_rebalance_plan(category_df, category_name, current_fx):
    # 현금은 집행 대기 자금으로 보고, 리밸런싱 목표자산 계산 대상에서 제외
    investable_df = category_df[category_df["자산군"] != "현금"].copy()
    targets = CATEGORY_TARGETS.get(category_name, {})
    category_total = float(investable_df["평가금액"].sum())
    if category_total <= 0 or not targets:
        return [], [], []

    account_balances = category_df.groupby("계좌명")["평가금액"].sum().to_dict()
    irp_accounts = [acc for acc in account_balances if "IRP" in str(acc).upper()]
    non_irp_accounts = [acc for acc in account_balances if acc not in irp_accounts]
    target_amounts = {asset: category_total * weight for asset, weight in targets.items()}
    allocation = {acc: {asset: 0.0 for asset in targets} for acc in account_balances}
    warnings = []

    safe_assets = [a for a in targets if a in IRP_SAFE_ASSETS]
    risky_assets = [a for a in targets if a not in IRP_SAFE_ASSETS]

    if safe_assets:
        safe_total = sum(target_amounts[a] for a in safe_assets)
        safe_alloc, safe_left = allocate_amounts_by_capacity(
            [{"name": acc, "capacity": account_balances[acc]} for acc in irp_accounts],
            safe_total,
        )

        if safe_left > 1 and non_irp_accounts:
            extra_alloc, safe_left = allocate_amounts_by_capacity(
                [{"name": acc, "capacity": account_balances[acc]} for acc in non_irp_accounts],
                safe_left,
            )
            for acc, amt in extra_alloc.items():
                safe_alloc[acc] = safe_alloc.get(acc, 0.0) + amt
        if safe_left > 1:
            warnings.append(f"{category_name}: 안전자산 {safe_left:,.0f}원이 계좌 용량 부족으로 미배정되었습니다.")

        safe_total_amt = safe_total if safe_total > 0 else 1.0
        for asset in safe_assets:
            ratio = target_amounts[asset] / safe_total_amt
            for acc, acc_amt in safe_alloc.items():
                allocation.setdefault(acc, {a: 0.0 for a in targets})
                allocation[acc][asset] += acc_amt * ratio

        for acc in irp_accounts:
            allocated_safe = sum(allocation[acc].get(asset, 0.0) for asset in safe_assets)
            required_safe = account_balances[acc] * 0.30
            if allocated_safe + 1 < required_safe:
                shortage = required_safe - allocated_safe
                # 안전자산 부족분은 KOFR 쪽으로 보강
                if "금리" in allocation[acc]:
                    allocation[acc]["금리"] += shortage
                elif safe_assets:
                    allocation[acc][safe_assets[0]] += shortage
                warnings.append(f"{category_name}: {acc}의 IRP 30% 안전자산 룰 부족분 {shortage:,.0f}원을 안전자산으로 보강했습니다.")

    remaining_capacity = {}
    for acc, total_amt in account_balances.items():
        used = sum(allocation[acc].values())
        remaining_capacity[acc] = max(total_amt - used, 0.0)

    for asset in risky_assets:
        alloc, left = allocate_amounts_by_capacity(
            [{"name": acc, "capacity": remaining_capacity[acc]} for acc in account_balances],
            target_amounts[asset],
        )
        for acc, amt in alloc.items():
            allocation[acc][asset] += amt
            remaining_capacity[acc] = max(remaining_capacity[acc] - amt, 0.0)
        if left > 1:
            warnings.append(f"{category_name}: {display_asset_group(asset)} {left:,.0f}원이 미배정되었습니다.")

    plan_rows = []
    for acc in account_balances:
        acc_df = category_df[category_df["계좌명"] == acc].copy()
        for asset, target_amt in allocation[acc].items():
            if target_amt <= 0:
                continue
            current_amt = float(acc_df.loc[acc_df["자산군"] == asset, "평가금액"].sum())
            diff_amt = target_amt - current_amt
            row = choose_order_row(acc_df, asset, current_fx)
            if row is None:
                continue
            price = float(row.get("현재가", 0) or 0)
            if price <= 0:
                code = str(row.get("종목코드", ""))
                price = float(get_price_data((code,)).get(code, 0) or 0)
            qty = int(diff_amt / price) if price > 0 else 0
            plan_rows.append(
                {
                    "계좌카테고리": category_name,
                    "_category_order": CATEGORY_ORDER_MAP.get(category_name, 999),
                    "계좌명": acc,
                    "자산군": asset,
                    "자산군_표시": display_asset_group(asset),
                    "약식종목명": row.get("약식종목명", asset),
                    "종목코드": row.get("종목코드", ""),
                    "현재가": price,
                    "현재금액": current_amt,
                    "목표금액": target_amt,
                    "차액": diff_amt,
                    "조정수량": qty,
                    "예상주문": qty * price,
                }
            )

    rule_rows = []
    for acc in irp_accounts:
        acc_total = account_balances[acc]
        if acc_total <= 0:
            continue
        current_safe = category_df[(category_df["계좌명"] == acc) & (category_df["자산군"].isin(IRP_SAFE_ASSETS))]["평가금액"].sum()
        target_safe = sum(allocation[acc].get(asset, 0.0) for asset in safe_assets)
        rule_rows.append(
            {
                "계좌명": acc,
                "현재 안전자산 비중": current_safe / acc_total * 100.0,
                "목표 안전자산 비중": target_safe / acc_total * 100.0,
                "부족 안전자산": max(30.0 - target_safe / acc_total * 100.0, 0.0),
            }
        )

    return plan_rows, rule_rows, warnings


# -----------------------------
# 메인
# -----------------------------
try:
    df_raw = load_data()
    with st.spinner("실시간 데이터 업데이트 중..."):
        seed_df, asset_df, current_fx = prepare_asset_df(df_raw)

    total_eval = float(asset_df["평가금액"].sum())
    total_seed = float((seed_df["보유수량"] * seed_df["매수평단"]).sum())
    if total_seed <= 0:
        total_seed = float(asset_df["매수금액"].sum())
    total_profit = total_eval - total_seed
    total_target = build_overall_target_mix(asset_df)

    st.title("💰 Family Portfolio")
    st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
    hero_pct = (total_profit / total_seed * 100) if total_seed > 0 else 0
    hero_delta_color = "#4ade80" if total_profit >= 0 else "#60a5fa"
    st.markdown(
        f"""
        <div class="app-hero">
            <div class="app-hero-title">누적 수익</div>
            <div class="app-hero-value">{hero_pct:.2f}%</div>
            <div class="app-hero-sub" style="color:{hero_delta_color};">{total_profit:+,.0f}원</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")

    daily_alerts = build_daily_alerts(asset_df, drop_threshold=-2.5)
    if daily_alerts:
        lines = [f"- {name} ({code}): {pct:.2f}%" for name, code, pct in sorted(daily_alerts, key=lambda x: x[2])]
        st.warning("전일 대비 2.5% 이상 하락한 종목이 있습니다.\n" + "\n".join(lines))

    st.caption("기본값으로 수량 0 / 평가액 0 / 비중 0.1% 이하 행은 자동으로 숨김 처리됩니다.")
    f1, f2 = st.columns([1, 1])
    with f1:
        show_all_rows = st.toggle("숨김 행 포함해서 보기", value=False)
    with f2:
        display_weight_threshold = st.number_input("비중 표시 최소값(%)", min_value=0.0, value=float(DISPLAY_WEIGHT_THRESHOLD), step=0.1)

    st.markdown("<div style='margin-top:10px;'></div>", unsafe_allow_html=True)
    tabs = st.tabs(["📊 종목 상세", "🍩 전체 비중", "🏦 카테고리", "💼 계좌별", "🌎 환율관리", "⚖️ 리밸런싱"])

    # 1. 종목 상세
    with tabs[0]:
        open_card("📊 종목 상세", "보유 종목 요약과 선택 종목 차트")
        sum_df = (
            asset_df.groupby(["자산군", "약식종목명", "종목코드", "종목명"], dropna=False)
            .agg({"보유수량": "sum", "매수금액": "sum", "평가금액": "sum"})
            .reset_index()
        )
        sum_df["자산군_표시"] = sum_df["자산군"].apply(display_asset_group)
        sum_df["매수평단"] = sum_df.apply(lambda x: x["매수금액"] / x["보유수량"] if x["보유수량"] > 0 else 0, axis=1)
        sum_df["현재가"] = sum_df.apply(lambda x: x["평가금액"] / x["보유수량"] if x["보유수량"] > 0 else 0, axis=1)
        sum_df["수익률"] = sum_df.apply(lambda x: calc_return(x["평가금액"], x["매수금액"]), axis=1)

        sort_targets = total_target.copy()
        sort_targets["현금"] = -1
        sum_df = add_sort_columns(sum_df, asset_col="자산군", amount_col="평가금액", targets_dict=sort_targets)
        sum_df = sum_df.sort_values(["_asset_order", "평가금액", "약식종목명"], ascending=[True, False, True])

        st.dataframe(
            style_table(
                sum_df,
                ["자산군_표시", "약식종목명", "보유수량", "매수평단", "현재가", "평가금액", "수익률"],
                show_all=show_all_rows,
                min_weight=display_weight_threshold,
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        selectable = sum_df["종목명"].fillna("").unique().tolist()
        selected_name = st.selectbox("종목 선택", selectable)
        detail_df = asset_df[asset_df["종목명"] == selected_name].copy()

        if not detail_df.empty:
            rep_row = detail_df.sort_values(["평가금액", "보유수량"], ascending=False).iloc[0]
            sel_code = str(rep_row["종목코드"]).strip()
            avg_price = 0.0
            total_qty = float(pd.to_numeric(detail_df["보유수량"], errors="coerce").fillna(0).sum())
            total_buy_amt = float(pd.to_numeric(detail_df["매수금액"], errors="coerce").fillna(0).sum())
            if total_qty > 0:
                avg_price = total_buy_amt / total_qty

            latest_close, prev_close, daily_pct = get_daily_change_info(sel_code)
            if daily_pct is not None:
                color = "#d32f2f" if daily_pct > 0 else "#1976d2"
                sign = "+" if daily_pct > 0 else ""
                st.markdown(
                    f"<div style='font-size:16px; font-weight:700; color:{color};'>전일 대비 {sign}{daily_pct:.2f}%</div>",
                    unsafe_allow_html=True,
                )
            else:
                st.caption("전일 대비 데이터를 불러오지 못했습니다.")

            hist_df = get_history_data(sel_code, days=120)
            if hist_df is not None and not hist_df.empty:
                st.plotly_chart(
                    make_price_chart(hist_df, avg_price=avg_price, title=f"{selected_name} 최근 120일 차트"),
                    use_container_width=True,
                    key=f"price_chart_{sel_code}_{selected_name}",
                    config={"displayModeBar": False, "scrollZoom": False},
                )
            else:
                st.info("120일 가격 차트를 불러오지 못했습니다.")

        with st.expander("계좌별 상세 보기", expanded=False):
            st.dataframe(
                style_table(
                    detail_df,
                    ["계좌명", "종목코드", "보유수량", "매수평단", "현재가", "평가금액", "수익률"],
                    show_all=show_all_rows,
                    min_weight=display_weight_threshold,
                ),
                use_container_width=True,
                hide_index=True,
            )
        close_card()

    # 2. 전체 비중
    with tabs[1]:
        open_card("📊 전체 포트폴리오 상태", "현재 비중과 목표 비중을 비교")
        grp_df = asset_df.groupby("자산군", dropna=False)["평가금액"].sum().reset_index()
        grp_df["자산군_표시"] = grp_df["자산군"].apply(display_asset_group)
        grp_df["비중"] = grp_df["평가금액"] / total_eval * 100.0 if total_eval > 0 else 0.0
        grp_df["목표"] = grp_df["자산군"].map(total_target).fillna(0.0)
        grp_df["차이"] = grp_df["비중"] - grp_df["목표"]

        st.plotly_chart(
            make_dual_donut(
                grp_df,
                "비중",
                "자산군_표시",
                total_target,
                "",
                DONUT_OVERALL_HEIGHT,
                DONUT_CURRENT_DOMAIN,
                DONUT_TARGET_DOMAIN,
            ),
            use_container_width=True,
            key="overall_dual_donut",
            config={"displayModeBar": False, "scrollZoom": False},
        )

        sort_targets = total_target.copy()
        sort_targets["현금"] = -1
        grp_df = add_sort_columns(grp_df, asset_col="자산군", amount_col="평가금액", targets_dict=sort_targets)
        grp_df = grp_df.sort_values(["_asset_order", "평가금액", "자산군_표시"], ascending=[True, False, True])

        st.dataframe(
            style_table(
                grp_df,
                ["자산군_표시", "평가금액", "비중", "목표", "차이"],
                show_all=show_all_rows,
                min_weight=display_weight_threshold,
            ),
            use_container_width=True,
            hide_index=True,
        )
        close_card()

    # 3. 카테고리 분석
    with tabs[2]:
        for cat_name in CATEGORY_ORDER:
            cat_df = asset_df[asset_df["계좌카테고리"] == cat_name].copy()
            if cat_df.empty:
                continue

            open_card(f"🏦 {cat_name}", "현재 비중, 목표 비중, 계좌별 상세")
            cat_total = float(cat_df["평가금액"].sum())
            cat_grp = cat_df.groupby("자산군", dropna=False)["평가금액"].sum().reset_index()
            cat_grp["자산군_표시"] = cat_grp["자산군"].apply(display_asset_group)
            cat_grp["비중"] = cat_grp["평가금액"] / cat_total * 100.0 if cat_total > 0 else 0.0
            cat_grp["목표"] = cat_grp["자산군"].map({k: v * 100 for k, v in CATEGORY_TARGETS[cat_name].items()}).fillna(0.0)
            cat_grp["차이"] = cat_grp["비중"] - cat_grp["목표"]

            st.plotly_chart(
                make_dual_donut(
                    cat_grp,
                    "비중",
                    "자산군_표시",
                    {k: v * 100 for k, v in CATEGORY_TARGETS[cat_name].items()},
                    "",
                    DONUT_OVERALL_HEIGHT,
                    DONUT_CURRENT_DOMAIN,
                    DONUT_TARGET_DOMAIN,
                ),
                use_container_width=True,
                key=f"category_dual_donut_{cat_name}",
                config={"displayModeBar": False, "scrollZoom": False},
            )

            detail = cat_df.copy()
            detail["자산군_표시"] = detail["자산군"].apply(display_asset_group)
            detail["비중"] = detail["평가금액"] / cat_total * 100.0 if cat_total > 0 else 0.0
            detail["목표"] = detail["자산군"].map({k: v * 100 for k, v in CATEGORY_TARGETS[cat_name].items()}).fillna(0.0)
            acc_order = detail.groupby("계좌명")["평가금액"].sum().sort_values(ascending=False)
            detail["_account_order"] = detail["계좌명"].map({k: i for i, k in enumerate(acc_order.index)})
            detail = detail.sort_values(["_account_order", "목표", "평가금액", "약식종목명"], ascending=[True, False, False, True])

            styled_detail = style_table(
                detail,
                ["계좌명", "자산군_표시", "약식종목명", "평가금액", "비중", "목표", "수익률"],
                show_all=show_all_rows,
                min_weight=display_weight_threshold,
            ).apply(highlight_underweight_rows, axis=1)

            st.dataframe(
                styled_detail,
                use_container_width=True,
                hide_index=True,
            )
            close_card()
            st.markdown("---")

    # 4. 계좌별
    with tabs[3]:
        for acc_name in asset_df["계좌명"].dropna().unique():
            acc_df = asset_df[asset_df["계좌명"] == acc_name].copy()
            if acc_df.empty:
                continue
            open_card(f"🏦 {acc_name}", "계좌별 보유 자산 상세")
            acc_total = float(acc_df["평가금액"].sum())
            acc_df["비중"] = acc_df["평가금액"] / acc_total * 100.0 if acc_total > 0 else 0.0
            acc_df["자산군_표시"] = acc_df["자산군"].apply(display_asset_group)
            cat_name = acc_df["계좌카테고리"].mode().iloc[0]
            sort_targets = CATEGORY_TARGETS.get(cat_name, {}).copy()
            sort_targets["현금"] = 999
            acc_df = add_sort_columns(acc_df, asset_col="자산군", amount_col="평가금액", targets_dict=sort_targets)
            acc_df = acc_df.sort_values(["_asset_order", "평가금액", "약식종목명"], ascending=[True, False, True])

            st.dataframe(
                style_table(
                    acc_df,
                    ["자산군_표시", "약식종목명", "보유수량", "현재가", "평가금액", "비중", "수익률"],
                    show_all=show_all_rows,
                    min_weight=display_weight_threshold,
                ),
                use_container_width=True,
                hide_index=True,
            )
            close_card()

    # 5. 환율관리
    with tabs[4]:
        open_card(f"🌎 실시간 환율: {current_fx:,.2f}원", "현재 환율 구간과 대응 원칙")
        fx_target = FX_TARGETS_HIGH if current_fx > 1400 else (FX_TARGETS_LOW if current_fx < 1330 else FX_TARGETS_MID)

        fx_logic_df = pd.DataFrame([
            {"환율 범위": "1400 초과", "대응 방안": f"환노출 {FX_TARGETS_HIGH['환노출']:.0f}% / 환헤지 {FX_TARGETS_HIGH['환헤지']:.0f}%"},
            {"환율 범위": "1330 이상 ~ 1400 이하", "대응 방안": f"환노출 {FX_TARGETS_MID['환노출']:.0f}% / 환헤지 {FX_TARGETS_MID['환헤지']:.0f}%"},
            {"환율 범위": "1330 미만", "대응 방안": f"환노출 {FX_TARGETS_LOW['환노출']:.0f}% / 환헤지 {FX_TARGETS_LOW['환헤지']:.0f}%"},
        ])

        def highlight_current_fx_rule(row):
            label = str(row["환율 범위"])
            active = (
                (current_fx > 1400 and label == "1400 초과")
                or (1330 <= current_fx <= 1400 and label == "1330 이상 ~ 1400 이하")
                or (current_fx < 1330 and label == "1330 미만")
            )
            if active:
                return ["color: #1976d2; font-weight: 700"] * len(row)
            return [""] * len(row)

        st.dataframe(
            fx_logic_df.style.apply(highlight_current_fx_rule, axis=1),
            use_container_width=True,
            hide_index=True,
        )
        close_card()

        fx_config = {
            "세액공제 O": ["S&P500", "나스닥100"],
            "세액공제 X": ["S&P500", "나스닥100"],
            "ISA": ["다우존스", "S&P500"],
        }

        for cat_name in CATEGORY_ORDER:
            open_card(f"🏦 {cat_name}", "자산별 환노출 / 환헤지 비중 확인")
            for target_asset in fx_config.get(cat_name, []):
                fx_df = asset_df[(asset_df["계좌카테고리"] == cat_name) & (asset_df["자산군"] == target_asset)].copy()
                if fx_df.empty:
                    continue
                fx_df["구분"] = fx_df["약식종목명"].astype(str).apply(lambda x: "환헤지" if "(H)" in x else "환노출")
                fx_grp = fx_df.groupby("구분")["평가금액"].sum().reset_index()
                fx_total = float(fx_grp["평가금액"].sum())
                fx_grp["비중"] = fx_grp["평가금액"] / fx_total * 100.0 if fx_total > 0 else 0.0

                st.plotly_chart(
                    make_dual_donut(
                        fx_grp,
                        "비중",
                        "구분",
                        fx_target,
                        "",
                        DONUT_FX_HEIGHT,
                        DONUT_FX_CURRENT_DOMAIN,
                        DONUT_FX_TARGET_DOMAIN,
                        current_color_map=FX_COLOR_MAP,
                        target_color_map=FX_COLOR_MAP,
                    ),
                    use_container_width=True,
                    key=f"fx_dual_donut_{cat_name}_{target_asset}",
                    config={"displayModeBar": False, "scrollZoom": False},
                )
            close_card()
            st.markdown("---")

    # 6. 리밸런싱
    with tabs[5]:
        open_card("⚖️ 카테고리별 리밸런싱", "목표 비중과 현재 비중을 기준으로 조정 수량 계산")
        st.info("즉 현금은 집행 대기 자금이며 리밸런싱 목표 비중의 일부로 보지 않고, 기존 보유 종목의 리밸런싱을 진행합니다.")
        st.caption(f"현재 환율 {current_fx:,.2f}원 기준으로 주식형 해외자산(S&P500/나스닥100/다우존스)은 환노출 {fx_target['환노출']:.0f}% / 환헤지 {fx_target['환헤지']:.0f}% 권장 비율을 리밸런싱 계산에 반영합니다.")

        target_rows = []
        for cat_name in CATEGORY_ORDER:
            for asset, weight in CATEGORY_TARGETS[cat_name].items():
                target_rows.append({"카테고리": cat_name, "자산군": display_asset_group(asset), "목표 비중": weight * 100.0})
        target_df = pd.DataFrame(target_rows)
        st.dataframe(target_df.style.format({"목표 비중": "{:.1f}%"}), use_container_width=True, hide_index=True)

        if st.button("🔄 리밸런싱 수량 계산"):
            all_plan_frames = []
            all_rule_frames = []
            all_warnings = []

            for cat_name in CATEGORY_ORDER:
                cat_df = asset_df[asset_df["계좌카테고리"] == cat_name].copy()
                if cat_df.empty:
                    continue
                plan_rows, rule_rows, warnings = build_category_rebalance_plan(cat_df, cat_name, current_fx)
                if plan_rows:
                    all_plan_frames.append(pd.DataFrame(plan_rows))
                if rule_rows:
                    all_rule_frames.append(pd.DataFrame(rule_rows))
                all_warnings.extend(warnings)

            for msg in all_warnings:
                st.warning(msg)

            if all_plan_frames:
                st.caption("권장환형태: 현재 환율 기준으로 각 해외주식형 자산에 대해 환노출/환헤지 중 어느 형태를 우선 매수·조정할지 보여줍니다.")
                plan_df = pd.concat(all_plan_frames, ignore_index=True)
                plan_df = plan_df.sort_values(["_category_order", "계좌명", "자산군_표시", "목표금액"], ascending=[True, True, True, False])
                for cat_name in CATEGORY_ORDER:
                    sub = plan_df[plan_df["계좌카테고리"] == cat_name].copy()
                    if sub.empty:
                        continue
                    st.markdown(f"### {cat_name}")
                    display_cols = ["계좌명", "자산군_표시", "약식종목명", "종목코드", "목표금액", "현재금액", "현재가", "조정수량"]
                    st.dataframe(
                        sub[[c for c in display_cols if c in sub.columns]].style.applymap(
                            lambda x: "color: #d32f2f" if pd.notna(x) and isinstance(x, (int, float)) and x > 0 else "color: #1976d2",
                            subset=["조정수량"],
                        ).format({
                            "목표금액": "{:,.0f}",
                            "현재금액": "{:,.0f}",
                            "현재가": "{:,.0f}",
                            "조정수량": "{:+,.0f}",
                        }),
                        use_container_width=True,
                        hide_index=True,
                    )
            else:
                st.success("현재 리밸런싱 가능한 결과가 없습니다.")

            if all_rule_frames:
                st.markdown("### IRP 안전자산 30% 점검")
                rule_df = pd.concat(all_rule_frames, ignore_index=True)
                st.dataframe(
                    rule_df.style.format({
                        "현재 안전자산 비중": "{:.1f}%",
                        "목표 안전자산 비중": "{:.1f}%",
                        "부족 안전자산": "{:.1f}%",
                    }),
                    use_container_width=True,
                    hide_index=True,
                )
        close_card()

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")

