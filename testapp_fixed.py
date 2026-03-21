import streamlit as st
import pandas as pd

# -----------------------------
# 공통 표시 필터
# 기본값: 수량 0 / 평가액 0 / 비중 0.1% 이하 자동 제거
# 토글을 켜면 전체 행을 다시 볼 수 있음
# -----------------------------
DISPLAY_WEIGHT_THRESHOLD = 0.1

def _first_existing_col(df, candidates):
    for c in candidates:
        if c in df.columns:
            return c
    return None

def filter_display_rows(df, show_all=False, min_weight=DISPLAY_WEIGHT_THRESHOLD):
    if df is None:
            return df
    if show_all:
            return df.copy()

    out = df.copy()

    qty_col = _first_existing_col(out, ['보유수량', '수량', 'quantity', 'qty'])
    if qty_col is not None:
        qty_num = pd.to_numeric(out[qty_col], errors='coerce').fillna(0)
        out = out[qty_num > 0].copy()

    value_col = _first_existing_col(out, ['평가금액', '평가액'])
    if value_col is not None:
        value_num = pd.to_numeric(out[value_col], errors='coerce').fillna(0)
        out = out[value_num > 0].copy()

    weight_col = _first_existing_col(out, ['비중'])
    if weight_col is not None:
        weight_num = pd.to_numeric(out[weight_col], errors='coerce').fillna(0)
        out = out[weight_num.abs() >= float(min_weight)].copy()

    return out

def filter_zero_quantity(df):
    # 하위 호환용 이름 유지
    return filter_display_rows(df, show_all=False, min_weight=DISPLAY_WEIGHT_THRESHOLD)

import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Family Portfolio", layout="wide")


# -----------------------------
# 설정값
# -----------------------------
DISPLAY_TO_CANONICAL = {
    '현금성 (KOFR)': '금리',
    '미국 국채': '미국채',
}
CANONICAL_TO_DISPLAY = {
    '금리': '현금성 (KOFR)',
    '미국채': '미국 국채',
    '현금': '현금',
}

CATEGORY_TARGETS = {
    '세액공제 O': {
        'S&P500': 0.45,
        '나스닥100': 0.25,
        '금': 0.15,
        '미국채': 0.10,
        '금리': 0.05,
    },
    '세액공제 X': {
        'S&P500': 0.45,
        '나스닥100': 0.25,
        '금': 0.15,
        '미국채': 0.10,
        '금리': 0.05,
    },
    'ISA': {
        '다우존스': 0.50,
        'S&P500': 0.20,
        '금리': 0.30,
    },
}

CATEGORY_ORDER = ['세액공제 O', '세액공제 X', 'ISA']
CATEGORY_ORDER_MAP = {name: idx for idx, name in enumerate(CATEGORY_ORDER)}

IRP_SAFE_ASSETS = {'금', '미국채', '금리'}
CODE_MAP = {
    'S&P500': {'노출': '360750', '헤지': '448290'},
    '나스닥100': {'노출': '133690', '헤지': '448300'},
    '다우존스': {'노출': '458730', '헤지': '452360'},
    '금': {'기본': '411060'},
    '미국채': {'기본': '305080'},
    '금리': {'기본': '423160'},
}


DONUT_OUTER_OPACITY = 0.5  # 바깥(Target) 도넛 투명도: 0.0~1.0
DONUT_OVERALL_HEIGHT = 420  # 전체/카테고리 도넛 차트 높이
DONUT_FX_HEIGHT = 320  # 환율 도넛 차트 높이

# -----------------------------
# 도넛 차트 스케일 조절값
# 숫자를 직접 바꿔가면서 보기 좋게 맞추면 됨
# 값이 작아질수록 더 바깥으로 커지고, 값이 커질수록 더 안쪽으로 작아짐
# -----------------------------
DONUT_CURRENT_DOMAIN = {'x': [0.16, 0.84], 'y': [0.16, 0.84]}  # 현재 비중(안쪽 도넛)
DONUT_TARGET_DOMAIN = {'x': [0.03, 0.97], 'y': [0.03, 0.97]}   # 목표 비중(바깥 도넛)

DONUT_FX_CURRENT_DOMAIN = {'x': [0.18, 0.82], 'y': [0.18, 0.82]}  # 환율 탭 현재 비중
DONUT_FX_TARGET_DOMAIN = {'x': [0.05, 0.95], 'y': [0.05, 0.95]}   # 환율 탭 목표 비중


def get_target_order_map(targets_dict):
    if not targets_dict:
            return {}
    return {asset: idx for idx, (asset, _) in enumerate(sorted(targets_dict.items(), key=lambda x: (-x[1], display_asset_group(x[0]))))}


def add_sort_columns(df, asset_col='자산군', amount_col='평가금액', targets_dict=None):
    out = df.copy()
    order_map = get_target_order_map(targets_dict or {})
    out['_asset_order'] = out[asset_col].map(order_map).fillna(999).astype(int)
    if amount_col in out.columns:
        out['_amount_sort'] = pd.to_numeric(out[amount_col], errors='coerce').fillna(0)
    else:
        out['_amount_sort'] = 0
    return out


def make_dual_donut(current_df, current_value_col, current_name_col, target_map, title, height=DONUT_OVERALL_HEIGHT):
    names = list(dict.fromkeys(list(current_df[current_name_col].dropna()) + [display_asset_group(k) for k in target_map.keys()]))
    current_map = current_df.groupby(current_name_col)[current_value_col].sum().to_dict()
    target_display_map = {display_asset_group(k): v for k, v in target_map.items()}
    current_vals = [current_map.get(name, 0) for name in names]
    target_vals = [target_display_map.get(name, 0) for name in names]

    fig = go.Figure()
    fig.add_trace(go.Pie(
        labels=names,
        values=current_vals,
        hole=0.48,
        sort=False,
        direction='clockwise',
        textinfo='label+percent',
        domain={'x': [0.12, 0.88], 'y': [0.12, 0.88]},
        marker=dict(line=dict(color='white', width=1)),
        name='현재'
    ))
    fig.add_trace(go.Pie(
        labels=names,
        values=target_vals,
        hole=0.72,
        sort=False,
        direction='clockwise',
        textinfo='none',
        opacity=DONUT_OUTER_OPACITY,
        domain={'x': [0.0, 1.0], 'y': [0.0, 1.0]},
        marker=dict(line=dict(color='white', width=1)),
        hovertemplate='<b>%{label}</b><br>목표: %{value:.1f}%<extra></extra>',
        name='목표'
    ))
    fig.update_layout(
        title=title,
        height=height,
        margin=dict(l=10, r=10, t=50, b=10),
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
    )
    return fig


# -----------------------------
# 데이터 로드 / 전처리
# -----------------------------
def normalize_asset_group(value):
    raw = '' if pd.isna(value) else str(value).strip()
    if raw in DISPLAY_TO_CANONICAL:
            return DISPLAY_TO_CANONICAL[raw]
    return raw


def display_asset_group(value):
    return CANONICAL_TO_DISPLAY.get(value, value)


def load_data():
    target_file = 'my_assets.csv'
df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except Exception:
df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})

    required_defaults = {
        '종목코드': 'CASH',
        '보유수량': 0,
        '매수평단': 0,
        '약식종목명': '',
        '종목명': '',
        '계좌명': '',
        '계좌카테고리': '기타',
        '자산군': None,
    }
    for col, default in required_defaults.items():
        if col not in df.columns:
        df[col] = default

    df['종목코드'] = df['종목코드'].fillna('CASH').astype(str).str.strip()
    df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)
    df['매수평단'] = pd.to_numeric(df['매수평단'], errors='coerce').fillna(0)
    df['자산군'] = df['자산군'].fillna(df['약식종목명'])
    df['자산군'] = df['자산군'].apply(normalize_asset_group)
    return df


st.markdown(
    """<style>
    html, body, [class*="css"] { font-size: 12px !important; }
    h1 { font-size: 1.1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.0rem !important; }
    .stDataFrame div { font-size: 11px !important; }
    </style>""",
    unsafe_allow_html=True,
)


def safe_format(val):
        return f"{float(val):,.0f}"
    except Exception:
        return val


FORMAT_RULES = {
    '평가액': '{:,.0f}',
    '평가금액': '{:,.0f}',
    '매수금액': '{:,.0f}',
    '수익률': '{:.2f}%',
    '비중': '{:.1f}%',
    '목표': '{:.1f}%',
    '차이': '{:+.1f}%',
    '현재가': lambda x: safe_format(x),
    '수량': lambda x: safe_format(x),
    '보유수량': lambda x: safe_format(x),
    '평단': lambda x: safe_format(x),
    '매수평단': lambda x: safe_format(x),
    '목표금액': '{:,.0f}',
    '현재금액': '{:,.0f}',
    '예상주문': '{:,.0f}',
    '조정수량': '{:+,.0f}',
    '부족 안전자산': '{:,.1f}%',
}


def get_styled_df(target_df, cols_to_show):
    available_cols = [c for c in cols_to_show if c in target_df.columns]
    df_view = target_df[available_cols].copy().astype(object)

    if '종목코드' in target_df.columns:
        is_cash = target_df['종목코드'].astype(str).str.upper().isin(['CASH', '현금'])
        for c in ['보유수량', '매수평단', '현재가']:
        if c in df_view.columns:
        df_view.loc[is_cash, c] = '-'

    rename_map = {
        '계좌명': '계좌',
        '약식종목명': '종목',
        '보유수량': '수량',
        '매수평단': '평단',
        '평가금액': '평가액',
        '자산군_표시': '자산군',
        '목표_표시': '목표 자산군',
    }
    df_view = df_view.rename(columns=rename_map)

    rules = {}
    for col in df_view.columns:
        if col in FORMAT_RULES:
        rules[col] = FORMAT_RULES[col]

    return df_view.style.format(rules)


@st.cache_data(ttl=300, show_spinner=False)
def get_price_data(codes_tuple):
    price_map = {}
    for code in codes_tuple:
        code_str = str(code).strip()
        if code_str.upper() in ['CASH', '현금', 'NAN', '']:
        price_map[code] = 1.0
        continue
        hist = fdr.DataReader(code_str)
        price_map[code] = float(hist.tail(1)['Close'].iloc[-1]) if not hist.empty else 0.0
        except Exception:
        price_map[code] = 0.0
    return price_map


@st.cache_data(ttl=300, show_spinner=False)
def get_usdkrw():
        return float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])
    except Exception:
        return 0.0


def calc_return(eval_amt, buy_amt):
    if buy_amt and buy_amt != 0:
            return (eval_amt - buy_amt) / buy_amt * 100
    return 0.0


def build_overall_target_mix(asset_df):
    total_val = asset_df['평가금액'].sum()
    if total_val <= 0:
            return {}

    overall_amt = {}
    for cat_name, targets in CATEGORY_TARGETS.items():
        cat_total = asset_df.loc[asset_df['계좌카테고리'] == cat_name, '평가금액'].sum()
        for asset, weight in targets.items():
        overall_amt[asset] = overall_amt.get(asset, 0) + cat_total * weight

    return {asset: (amt / total_val) * 100 for asset, amt in overall_amt.items()}


def get_rebalance_base_df(category_df):
    return category_df[category_df['자산군'] != '현금'].copy()


# -----------------------------
# 리밸런싱 엔진
# -----------------------------
def allocate_amounts_by_capacity(accounts, amount):
    """accounts: [{'name':..., 'capacity':...}]"""
    remaining = max(float(amount), 0.0)
    allocation = {acc['name']: 0.0 for acc in accounts}
    capacities = {acc['name']: max(float(acc.get('capacity', 0)), 0.0) for acc in accounts}

    while remaining > 1 and sum(capacities.values()) > 0:
        total_cap = sum(capacities.values())
        progress = 0.0
        for name, cap in list(capacities.items()):
        if cap <= 0:
        continue
        share = remaining * (cap / total_cap)
        add = min(cap, share)
        if add > 0:
        allocation[name] += add
        capacities[name] -= add
        progress += add
        remaining -= progress
        if progress <= 1e-9:
        break

    if remaining > 1 and sum(capacities.values()) > 0:
        for name, cap in sorted(capacities.items(), key=lambda x: x[1], reverse=True):
        if remaining <= 1:
        break
        add = min(cap, remaining)
        allocation[name] += add
        capacities[name] -= add
        remaining -= add

    return allocation, remaining


def build_virtual_order_row(target_asset):
    code_info = CODE_MAP.get(target_asset, {})
    if target_asset in {'S&P500', '나스닥100', '다우존스'}:
        current_fx = get_usdkrw()
        prefer_hedged = current_fx > 1380
        code = code_info.get('헤지' if prefer_hedged else '노출')
        name_suffix = '(H)' if prefer_hedged else ''
        short_name = f"{display_asset_group(target_asset)} {name_suffix}".strip()
    else:
        code = code_info.get('기본')
        short_name = display_asset_group(target_asset)

    if not code:
            return None

    curr_price = price_map.get(code, 0.0) if 'price_map' in globals() else 0.0
    return pd.Series({
        '자산군': target_asset,
        '약식종목명': short_name,
        '종목코드': code,
        '현재가': curr_price,
        '보유수량': 0,
        '평가금액': 0.0,
    })


def choose_order_row(acc_df, target_asset):
    candidates = acc_df[acc_df['자산군'] == target_asset].copy()
    if candidates.empty:
            return build_virtual_order_row(target_asset)

    if target_asset in {'S&P500', '나스닥100', '다우존스'}:
        current_fx = get_usdkrw()
        prefer_hedged = current_fx > 1380
        if prefer_hedged:
        hedged = candidates[candidates['약식종목명'].astype(str).str.contains(r'\(H\)', regex=True, na=False)]
        if not hedged.empty:
        candidates = hedged
        else:
        unhedged = candidates[~candidates['약식종목명'].astype(str).str.contains(r'\(H\)', regex=True, na=False)]
        if not unhedged.empty:
        candidates = unhedged

    positive_price = candidates[candidates['현재가'] > 0]
    if not positive_price.empty:
        positive_holding = positive_price[positive_price['보유수량'] > 0]
        if not positive_holding.empty:
            return positive_holding.sort_values(['보유수량', '평가금액'], ascending=False).iloc[0]
        return positive_price.iloc[0]
    return candidates.iloc[0]


def build_category_rebalance_plan(category_df, category_name):
    targets = CATEGORY_TARGETS.get(category_name, {})
    rebalance_df = get_rebalance_base_df(category_df)
    category_total = float(rebalance_df['평가금액'].sum())
    if category_total <= 0 or not targets:
            return [], [], {}

    account_balances = rebalance_df.groupby('계좌명')['평가금액'].sum().to_dict()
    irp_accounts = [acc for acc in account_balances if 'IRP' in str(acc).upper()]
    non_irp_accounts = [acc for acc in account_balances if acc not in irp_accounts]

    target_amounts = {asset: category_total * w for asset, w in targets.items()}
    current_amounts = rebalance_df.groupby('자산군')['평가금액'].sum().to_dict()
    allocation = {acc: {asset: 0.0 for asset in targets} for acc in account_balances}
    warnings = []

    safe_assets = [asset for asset in targets if asset in IRP_SAFE_ASSETS]
    risky_assets = [asset for asset in targets if asset not in IRP_SAFE_ASSETS]

    # 1) 안전자산은 가능한 한 IRP에 몰아서 배치
    if safe_assets:
        safe_total = sum(target_amounts[a] for a in safe_assets)
        irp_accounts_with_capacity = [{'name': acc, 'capacity': account_balances[acc]} for acc in irp_accounts]
        safe_by_account, safe_left = allocate_amounts_by_capacity(irp_accounts_with_capacity, safe_total)
        if safe_left > 1:
        warnings.append(f"{category_name}: IRP 잔액이 부족해 안전자산 {safe_left:,.0f}원이 비IRP 계좌로 넘어갑니다.")
        overflow_accounts = [{'name': acc, 'capacity': account_balances[acc]} for acc in non_irp_accounts]
        extra_alloc, extra_left = allocate_amounts_by_capacity(overflow_accounts, safe_left)
        for acc, amt in extra_alloc.items():
        safe_by_account[acc] = safe_by_account.get(acc, 0.0) + amt
        if extra_left > 1:
        warnings.append(f"{category_name}: 전체 배분 용량이 부족해 {extra_left:,.0f}원이 미배정 상태입니다.")
        safe_target_total = safe_total if safe_total > 0 else 1.0
        for asset in safe_assets:
        ratio = target_amounts[asset] / safe_target_total
        for acc, acc_safe_amt in safe_by_account.items():
        if acc not in allocation:
        allocation[acc] = {a: 0.0 for a in targets}
        allocation[acc][asset] = acc_safe_amt * ratio
        # IRP 30% 룰 체크
        for acc in irp_accounts:
        safe_alloc = sum(allocation[acc].get(asset, 0.0) for asset in safe_assets)
        req_safe = account_balances[acc] * 0.30
        if safe_alloc + 1 >= req_safe:
        continue
        shortage = req_safe - safe_alloc
        donor_assets = sorted(risky_assets, key=lambda a: allocation[acc].get(a, 0.0), reverse=True)
        for donor in donor_assets:
        if shortage <= 1:
        break
        donor_amt = allocation[acc].get(donor, 0.0)
        take = min(donor_amt, shortage)
        allocation[acc][donor] -= take
        # 부족분은 금리로 우선 전환
        if '금리' in targets:
        allocation[acc]['금리'] = allocation[acc].get('금리', 0.0) + take
        elif safe_assets:
        allocation[acc][safe_assets[0]] = allocation[acc].get(safe_assets[0], 0.0) + take
        shortage -= take
        if shortage > 1:
        warnings.append(f"{category_name}: {acc}의 IRP 안전자산 30% 룰을 목표 비중만으로는 완전히 충족하기 어렵습니다. 부족분 {shortage:,.0f}원")

    # 2) 위험자산은 남은 계좌 용량 기준으로 배치
    remaining_capacity = {}
    for acc, bal in account_balances.items():
        used = sum(allocation[acc].values())
        remaining_capacity[acc] = max(bal - used, 0.0)

    for asset in risky_assets:
        amount = target_amounts[asset]
        alloc, leftover = allocate_amounts_by_capacity(
        [{'name': acc, 'capacity': remaining_capacity[acc]} for acc in account_balances],
        amount,
        )
        for acc, amt in alloc.items():
        allocation[acc][asset] += amt
        remaining_capacity[acc] = max(remaining_capacity[acc] - amt, 0.0)
        if leftover > 1:
        warnings.append(f"{category_name}: {display_asset_group(asset)} {leftover:,.0f}원이 계좌 용량 부족으로 미배정되었습니다.")

    # 3) 결과 테이블 구성
    plan_rows = []
    for acc, per_asset in allocation.items():
        acc_df = rebalance_df[rebalance_df['계좌명'] == acc].copy()
        for asset, target_amt in per_asset.items():
        if target_amt <= 0:
        continue
        curr_val = float(acc_df.loc[acc_df['자산군'] == asset, '평가금액'].sum())
        row = choose_order_row(acc_df, asset)
        if row is None:
        continue
        curr_price = float(row['현재가']) if pd.notna(row['현재가']) else 0.0
        diff_amt = target_amt - curr_val
        diff_qty = 0
        if curr_price > 0:
        diff_qty = int(diff_amt / curr_price)
        plan_rows.append({
        '계좌카테고리': category_name,
        '계좌명': acc,
        '자산군': asset,
        '자산군_표시': display_asset_group(asset),
        '목표_표시': display_asset_group(asset),
        '약식종목명': row['약식종목명'],
        '종목코드': row['종목코드'],
        '현재가': curr_price,
        '현재금액': curr_val,
        '목표금액': target_amt,
        '차액': diff_amt,
        '조정수량': diff_qty,
        '예상주문': diff_qty * curr_price,
        })

    rule_rows = []
    for acc in irp_accounts:
        safe_now = rebalance_df[(rebalance_df['계좌명'] == acc) & (rebalance_df['자산군'].isin(IRP_SAFE_ASSETS))]['평가금액'].sum()
        safe_target = sum(allocation[acc].get(asset, 0.0) for asset in safe_assets)
        acc_total = account_balances[acc]
        rule_rows.append({
        '계좌명': acc,
        '현재 안전자산 비중': (safe_now / acc_total * 100) if acc_total > 0 else 0,
        '목표 안전자산 비중': (safe_target / acc_total * 100) if acc_total > 0 else 0,
        '부족 안전자산': max(30 - ((safe_target / acc_total * 100) if acc_total > 0 else 0), 0),
        })

    meta = {
        'category_total': category_total,
        'target_amounts': target_amounts,
        'current_amounts': current_amounts,
        'allocation': allocation,
        'account_balances': account_balances,
    }
    return plan_rows, rule_rows, {'warnings': warnings, 'meta': meta}


# -----------------------------
# 메인 앱
# -----------------------------
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'].astype(str).str.upper() == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'].astype(str).str.upper() != 'SEED'].copy()

    with st.spinner('실시간 데이터 업데이트 중...'):
        unique_codes = tuple(asset_df['종목코드'].dropna().astype(str).unique())
        price_map = get_price_data(unique_codes)
        current_fx = get_usdkrw()

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(
        lambda x: x['보유수량'] if str(x['종목코드']).upper() == 'CASH' else x['보유수량'] * x['매수평단'],
        axis=1,
    )
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    asset_df['수익률'] = asset_df.apply(lambda x: calc_return(x['평가금액'], x['매수금액']), axis=1)

    total_eval = asset_df['평가금액'].sum()
    total_seed = (seed_df['보유수량'] * seed_df['매수평단']).sum()
    if total_seed == 0:
        total_seed = asset_df['매수금액'].sum()
    total_profit = total_eval - total_seed

    total_target = build_overall_target_mix(asset_df)

    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit / total_seed * 100) if total_seed > 0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    st.caption("기본값으로 수량 0 / 평가액 0 / 비중 0.1% 이하 행은 자동으로 숨김 처리됩니다.")
col_filter1, col_filter2 = st.columns([1, 1])
with col_filter1:
    show_all_rows = st.toggle("숨김 행 포함해서 보기", value=False, help="켜면 수량 0, 평가액 0, 비중 0.1% 이하 행도 다시 표시합니다.")
with col_filter2:
    display_weight_threshold = st.number_input("비중 표시 최소값(%)", min_value=0.0, value=float(DISPLAY_WEIGHT_THRESHOLD), step=0.1, help="이 값 미만의 비중 행은 기본적으로 숨깁니다.")

tabs = st.tabs(["📊 종목 상세", "🍩 전체 비중", "🏦 카테고리 분석", "💼 계좌별", "🌎 환율관리", "⚖️ 리밸런싱"])

    # 1. 종목 상세
    with tabs[0]:
        sum_df = (
        asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명'], dropna=False)
        .agg({'보유수량': 'sum', '매수금액': 'sum', '평가금액': 'sum'})
        .reset_index()
        )
        sum_df['자산군_표시'] = sum_df['자산군'].apply(display_asset_group)
        sum_df['매수평단'] = sum_df.apply(
        lambda x: x['매수금액'] / x['보유수량'] if x['보유수량'] > 0 else 0,
        axis=1,
        )
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['수익률'] = sum_df.apply(lambda x: calc_return(x['평가금액'], x['매수금액']), axis=1)
        sum_df = add_sort_columns(sum_df, asset_col='자산군', amount_col='평가금액', targets_dict=total_target)
        sum_df = sum_df.sort_values(['_asset_order', '평가금액', '약식종목명'], ascending=[True, False, True])
        st.dataframe(
        get_styled_df(
        sum_df,
        ['자산군_표시', '약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률'],
        show_all=show_all_rows,
        min_weight=display_weight_threshold,
        ),
        use_container_width=True,
        hide_index=True,
        )
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].fillna('').unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        st.dataframe(
        get_styled_df(
        detail_df,
        ['계좌명', '종목코드', '보유수량', '매수평단', '현재가', '평가금액', '수익률'],
        show_all=show_all_rows,
        min_weight=display_weight_threshold,
        ),
        use_container_width=True,
        hide_index=True,
        )
        if not detail_df.empty:
        code = str(detail_df['종목코드'].iloc[0])
        if code.upper() not in ['CASH', '현금']:
        hist_data = fdr.DataReader(code).tail(120)
        if not hist_data.empty:
        fig = go.Figure(
        data=[
        go.Candlestick(
        x=hist_data.index,
        open=hist_data['Open'],
        high=hist_data['High'],
        low=hist_data['Low'],
        close=hist_data['Close'],
        increasing_line_color='#d32f2f',
        decreasing_line_color='#1976d2',
        )
        ]
        )
        qty_sum = detail_df['보유수량'].sum()
        avg_p = detail_df['매수금액'].sum() / qty_sum if qty_sum > 0 else 0
        if avg_p > 0:
        fig.add_hline(
        y=avg_p,
        line_dash='dash',
        line_color='red',
        annotation_text=f"내 평단: {avg_p:,.0f}",
        annotation_position='top left',
        )
        fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True, key=f"candle_{code}")
        else:
        st.info("차트 데이터를 불러올 수 없습니다.")
        except Exception:
        st.info("차트 데이터를 불러올 수 없습니다.")

    # 2. 전체 비중
    with tabs[1]:
        st.subheader("📊 전체 포트폴리오 상태")
        grp_df = asset_df.groupby('자산군', dropna=False).agg({'평가금액': 'sum'}).reset_index()
        grp_df['자산군_표시'] = grp_df['자산군'].apply(display_asset_group)
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100 if total_eval > 0 else 0
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        grp_df['차이'] = grp_df['비중'] - grp_df['목표']
        st.plotly_chart(
        make_dual_donut(
        grp_df,
        current_value_col='비중',
        current_name_col='자산군_표시',
        target_map={k: v for k, v in total_target.items()},
        title="현재 비중 vs 목표 비중",
        height=DONUT_OVERALL_HEIGHT,  # ← 전체 차트 크기 조절
        current_domain=DONUT_CURRENT_DOMAIN,  # ← 현재 도넛 스케일
        target_domain=DONUT_TARGET_DOMAIN,    # ← 목표 도넛 스케일
        ),
        use_container_width=True,
        key="p2_dual",
        )
        grp_df = add_sort_columns(grp_df, asset_col='자산군', amount_col='평가금액', targets_dict=total_target)
        grp_df = grp_df.sort_values(['_asset_order', '평가금액', '자산군_표시'], ascending=[True, False, True])
        st.dataframe(get_styled_df(grp_df, ['자산군_표시', '평가금액', '비중', '목표', '차이'], show_all=show_all_rows, min_weight=display_weight_threshold), use_container_width=True, hide_index=True)

    # 3. 카테고리 분석
    with tabs[2]:
        for cat_name in ["세액공제 O", "세액공제 X", "ISA"]:
        sub_df = asset_df[asset_df['계좌카테고리'] == cat_name].copy()
        if sub_df.empty:
        continue
        st.subheader(f"🏦 {cat_name} 분석 및 매수 가이드")
        cat_eval = sub_df['평가금액'].sum()
        sub_grp = sub_df.groupby('자산군', dropna=False).agg({'평가금액': 'sum'}).reset_index()
        sub_grp['자산군_표시'] = sub_grp['자산군'].apply(display_asset_group)
        sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100 if cat_eval > 0 else 0
        sub_grp['목표'] = sub_grp['자산군'].map({k: v * 100 for k, v in CATEGORY_TARGETS.get(cat_name, {}).items()}).fillna(0)
        sub_grp['차이'] = sub_grp['비중'] - sub_grp['목표']
        recom_type = "헤지" if current_fx > 1380 else "노출"
        for _, row in sub_grp.iterrows():
        if row['차이'] <= -3.0 and row['자산군'] in CODE_MAP and row['자산군'] in {'S&P500', '나스닥100', '다우존스'}:
        rec_code = CODE_MAP[row['자산군']][recom_type]
        st.info(f"💡 **{display_asset_group(row['자산군'])} 부족**: 현재 환율({current_fx:,.0f}원) 기준, **환{recom_type}형 ({rec_code})** 추가 매수를 권장합니다.")
        st.plotly_chart(
        make_dual_donut(
        sub_grp,
        current_value_col='비중',
        current_name_col='자산군_표시',
        target_map={k: v * 100 for k, v in CATEGORY_TARGETS.get(cat_name, {}).items()},
        title=f"{cat_name} 현재 비중 vs 목표 비중",
        height=DONUT_OVERALL_HEIGHT,  # ← 카테고리 차트 크기 조절
        current_domain=DONUT_CURRENT_DOMAIN,
        target_domain=DONUT_TARGET_DOMAIN,
        ),
        use_container_width=True,
        key=f"cat_dual_{cat_name}",
        )
        detail_cat_df = sub_df.assign(
        비중=(sub_df['평가금액'] / cat_eval) * 100 if cat_eval > 0 else 0,
        자산군_표시=sub_df['자산군'].apply(display_asset_group),
        )
        account_order = detail_cat_df.groupby('계좌명')['평가금액'].sum().sort_values(ascending=False)
        detail_cat_df['_account_order'] = detail_cat_df['계좌명'].map({name: idx for idx, name in enumerate(account_order.index)})
        detail_cat_df = add_sort_columns(detail_cat_df, asset_col='자산군', amount_col='평가금액', targets_dict=CATEGORY_TARGETS.get(cat_name, {}))
        detail_cat_df = detail_cat_df.sort_values(['_account_order', '_asset_order', '평가금액', '약식종목명'], ascending=[True, True, False, True])
        st.dataframe(
        get_styled_df(detail_cat_df, ['계좌명', '자산군_표시', '약식종목명', '평가금액', '비중', '수익률'], show_all=show_all_rows, min_weight=display_weight_threshold),
        use_container_width=True,
        hide_index=True,
        )
        st.markdown("---")

    # 4. 계좌별
    with tabs[3]:
        for acc in asset_df['계좌명'].dropna().unique():
        a_df = asset_df[asset_df['계좌명'] == acc].copy()
        st.markdown(f"### 🏦 {acc}")
        acc_total = a_df['평가금액'].sum()
        a_df['비중'] = (a_df['평가금액'] / acc_total) * 100 if acc_total > 0 else 0
        a_df['자산군_표시'] = a_df['자산군'].apply(display_asset_group)
        acc_category = a_df['계좌카테고리'].mode().iloc[0] if not a_df['계좌카테고리'].mode().empty else None
        a_df = add_sort_columns(a_df, asset_col='자산군', amount_col='평가금액', targets_dict=CATEGORY_TARGETS.get(acc_category, {}))
        a_df = a_df.sort_values(['_asset_order', '평가금액', '약식종목명'], ascending=[True, False, True])
        st.dataframe(
        get_styled_df(a_df, ['자산군_표시', '약식종목명', '보유수량', '현재가', '평가금액', '비중', '수익률'], show_all=show_all_rows, min_weight=display_weight_threshold),
        use_container_width=True,
        hide_index=True,
        )

    # 5. 환율관리
    with tabs[4]:
        st.subheader(f"🌎 실시간 환율: {current_fx:,.2f}원")
        t_fx = {"노출": 30, "헤지": 70} if current_fx > 1400 else ({"노출": 80, "헤지": 20} if current_fx < 1330 else {"노출": 50, "헤지": 50})
        fx_config = {
        "세액공제 O": ["S&P500", "나스닥100"],
        "세액공제 X": ["S&P500", "나스닥100"],
        "ISA": ["다우존스", "S&P500"],
        }
        for cat_name, targets in fx_config.items():
        st.markdown(f"### 🏦 {cat_name}")
        for target_asset in targets:
        fx_sub = asset_df[(asset_df['계좌카테고리'] == cat_name) & (asset_df['자산군'] == target_asset)].copy()
        if fx_sub.empty:
        continue
        st.write(f"#### 📊 {display_asset_group(target_asset)} (As-Is vs To-Be)")
        fx_sub['구분'] = fx_sub['약식종목명'].astype(str).apply(lambda x: '환헤지' if '(H)' in x else '환노출')
        asis_grp = fx_sub.groupby('구분')['평가금액'].sum().reset_index()
        fx_total = asis_grp['평가금액'].sum()
        asis_grp['비중'] = (asis_grp['평가금액'] / fx_total) * 100 if fx_total > 0 else 0
        st.plotly_chart(
        make_dual_donut(
        asis_grp,
        current_value_col='비중',
        current_name_col='구분',
        target_map={'환노출': t_fx['노출'], '환헤지': t_fx['헤지']},
        title=f"{cat_name} - {display_asset_group(target_asset)} 환노출/헤지",
        height=DONUT_FX_HEIGHT,  # ← 환율 차트 크기 조절
        current_domain=DONUT_FX_CURRENT_DOMAIN,
        target_domain=DONUT_FX_TARGET_DOMAIN,
        ),
        use_container_width=True,
        key=f"fx_dual_{cat_name}_{target_asset}",
        )
        st.markdown("---")

    # 6. 리밸런싱
    with tabs[5]:
        st.subheader("⚖️ 카테고리별 리밸런싱")
        st.info("세액공제 O / X는 계좌 카테고리 총액 기준으로 목표 비중을 계산하고, 계좌별 금액 비중을 반영해 배분합니다. IRP가 있는 카테고리는 금·미국채·KOFR를 우선 IRP에 배치해 IRP 30% 안전자산 룰을 최대한 맞춥니다. CSV의 '현금'은 실제 현금으로 간주하며 KOFR와 별개로 보아 리밸런싱 대상에서 제외합니다.")
        target_view = []
        for cat_name in CATEGORY_ORDER:
        targets = CATEGORY_TARGETS.get(cat_name, {})
        for asset, weight in targets.items():
        target_view.append({'카테고리': cat_name, '자산군': display_asset_group(asset), '목표 비중': weight * 100})
        st.dataframe(filter_display_rows(pd.DataFrame(target_view), show_all=show_all_rows, min_weight=display_weight_threshold), use_container_width=True, hide_index=True)
        if st.button("🔄 리밸런싱 수량 계산"):
        plan_frames = []
        rule_frames = []
        all_warnings = []
        for cat_name in ['세액공제 O', '세액공제 X', 'ISA']:
        cat_df = asset_df[asset_df['계좌카테고리'] == cat_name].copy()
        if cat_df.empty:
        continue
        plan_rows, rule_rows, extra = build_category_rebalance_plan(cat_df, cat_name)
        if plan_rows:
        plan_frames.append(pd.DataFrame(plan_rows))
        if rule_rows:
        rule_frames.append(pd.DataFrame(rule_rows))
        all_warnings.extend(extra.get('warnings', []))
        if all_warnings:
        for msg in all_warnings:
        st.warning(msg)
        if plan_frames:
        result_df = pd.concat(plan_frames, ignore_index=True)
        result_df = result_df[result_df['현재가'] > 0].copy()
        result_df['_category_order'] = result_df['계좌카테고리'].map(CATEGORY_ORDER_MAP).fillna(999).astype(int)
        result_df['_asset_order'] = result_df['계좌카테고리'].map(lambda x: CATEGORY_TARGETS.get(x, {})).combine(result_df['자산군'], lambda tgt, asset: get_target_order_map(tgt).get(asset, 999) if isinstance(tgt, dict) else 999)
        result_df = result_df.sort_values(['_category_order', '계좌명', '_asset_order', '예상주문'], ascending=[True, True, True, False])
        for cat_name in CATEGORY_ORDER:
        st.markdown(f"### {cat_name}")
        sub = result_df[result_df['계좌카테고리'] == cat_name].copy()
        if not show_all_rows:
        sub = sub[pd.to_numeric(sub['현재금액'], errors='coerce').fillna(0) > 0].copy()
        if sub.empty:
        continue
        st.dataframe(
        sub.style.applymap(
        lambda x: 'color: #d32f2f' if x > 0 else 'color: #1976d2',
        subset=['조정수량'],
        ).format({
        '현재가': '{:,.0f}',
        '현재금액': '{:,.0f}',
        '목표금액': '{:,.0f}',
        '차액': '{:+,.0f}',
        '예상주문': '{:+,.0f}',
        '조정수량': '{:+,.0f}',
        }),
        use_container_width=True,
        hide_index=True,
        )
        else:
        st.success("현재 비중이 목표와 거의 같거나, 리밸런싱 가능한 매핑 종목이 없습니다.")
        if rule_frames:
        st.markdown("### IRP 안전자산 30% 점검")
        rule_df = pd.concat(rule_frames, ignore_index=True)
        rule_df = filter_display_rows(rule_df, show_all=show_all_rows, min_weight=display_weight_threshold)
        st.dataframe(
        rule_df.style.format({
        '현재 안전자산 비중': '{:.1f}%',
        '목표 안전자산 비중': '{:.1f}%',
        '부족 안전자산': '{:.1f}%'
        }),
        use_container_width=True,
        hide_index=True,
        )

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
