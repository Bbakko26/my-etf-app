import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Family Portfolio", layout="wide")


# -----------------------------
# 데이터 로드 / 전처리
# -----------------------------
def load_data():
    target_file = 'my_assets.csv'
    try:
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
    try:
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
    '예상주문': '{:,.0f}',
    '조정수량': '{:+,.0f}',
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
        try:
            hist = fdr.DataReader(code_str)
            price_map[code] = float(hist.tail(1)['Close'].iloc[-1]) if not hist.empty else 0.0
        except Exception:
            price_map[code] = 0.0
    return price_map


@st.cache_data(ttl=300, show_spinner=False)
def get_usdkrw():
    try:
        return float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])
    except Exception:
        return 0.0


def calc_return(eval_amt, buy_amt):
    if buy_amt and buy_amt != 0:
        return (eval_amt - buy_amt) / buy_amt * 100
    return 0.0


# -----------------------------
# 리밸런싱 엔진
# -----------------------------
def run_rebalance(df, targets, safes):
    acc_balances = df.groupby('계좌명')['평가금액'].sum().to_dict()
    total_val = sum(acc_balances.values())

    overall_targets = {t: total_val * w for t, w in targets.items()}
    allocation = {acc: {t: 0 for t in targets} for acc in acc_balances}
    rem_targets = overall_targets.copy()

    irp_accs = [a for a in acc_balances if 'IRP' in str(a)]
    for acc in irp_accs:
        req_safe = acc_balances[acc] * 0.3
        allocated = 0
        for t in sorted(safes, key=lambda x: targets.get(x, 0), reverse=True):
            if allocated >= req_safe:
                break
            fill = min(rem_targets.get(t, 0), req_safe - allocated)
            allocation[acc][t] = fill
            allocated += fill
            rem_targets[t] -= fill

    for acc, bal in acc_balances.items():
        avail = bal - sum(allocation[acc].values())
        rem_total = sum(max(v, 0) for v in rem_targets.values())
        if rem_total <= 0:
            continue

        for t in targets:
            if rem_targets[t] <= 0:
                continue
            share = rem_targets[t] / rem_total
            add = min(rem_targets[t], avail * share)
            if 'IRP' in str(acc) and t not in safes:
                current_risky = sum(v for k, v in allocation[acc].items() if k not in safes)
                limit = (bal * 0.7) - current_risky
                add = min(add, max(0, limit))
            allocation[acc][t] += add
            rem_targets[t] -= add

    return allocation


# -----------------------------
# 메인 앱
# -----------------------------
try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'].astype(str).str.upper() == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'].astype(str).str.upper() != 'SEED'].copy()

    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "국내 ETF": 10.0, "금": 5.0, "현금": 15.0}
    cat_targets = {
        "세액공제 O": {"나스닥100": 40.0, "S&P500": 40.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0},
        "세액공제 X": {"나스닥100": 50.0, "S&P500": 50.0},
        "ISA": {"다우존스": 50.0, "S&P500": 30.0, "현금": 20.0},
    }
    code_map = {
        "S&P500": {"노출": "360750", "헤지": "448290"},
        "나스닥100": {"노출": "133690", "헤지": "448300"},
        "다우존스": {"노출": "458730", "헤지": "452250"},
    }

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

    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit / total_seed * 100) if total_seed > 0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    tabs = st.tabs(["📊 종목 상세", "🍩 전체 비중", "🏦 카테고리 분석", "💼 계좌별", "🌎 환율관리", "⚖️ 리밸런싱"])

    # 1. 종목 상세
    with tabs[0]:
        sum_df = (
            asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명'], dropna=False)
            .agg({'보유수량': 'sum', '매수금액': 'sum', '평가금액': 'sum'})
            .reset_index()
        )
        sum_df['매수평단'] = sum_df.apply(
            lambda x: x['매수금액'] / x['보유수량'] if x['보유수량'] > 0 else 0,
            axis=1,
        )
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['수익률'] = sum_df.apply(lambda x: calc_return(x['평가금액'], x['매수금액']), axis=1)

        st.dataframe(
            get_styled_df(
                sum_df.sort_values('평가금액', ascending=False),
                ['약식종목명', '자산군', '보유수량', '매수평단', '현재가', '평가금액', '수익률'],
            ),
            use_container_width=True,
            hide_index=True,
        )

        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].fillna('').unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        st.dataframe(
            get_styled_df(
                detail_df[detail_df['보유수량'] > 0],
                ['계좌명', '종목코드', '보유수량', '매수평단', '현재가', '평가금액', '수익률'],
            ),
            use_container_width=True,
            hide_index=True,
        )

        if not detail_df.empty:
            code = str(detail_df['종목코드'].iloc[0])
            if code.upper() not in ['CASH', '현금']:
                try:
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
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100 if total_eval > 0 else 0
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        grp_df['차이'] = grp_df['비중'] - grp_df['목표']

        if len(grp_df[abs(grp_df['차이']) >= 5]) >= 3:
            st.error("🚨 **종합 리밸런싱 필요**: 목표 비중 이탈 자산군이 3개 이상입니다.")

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.pie(grp_df, values='비중', names='자산군', title="현재(As-Is)", hole=0.5).update_layout(height=300), use_container_width=True, key="p2_is")
        c2.plotly_chart(px.pie(grp_df, values='목표', names='자산군', title="목표(Target)", hole=0.5).update_layout(height=300), use_container_width=True, key="p2_to")
        st.dataframe(get_styled_df(grp_df.sort_values('비중', ascending=False), ['자산군', '평가금액', '비중', '목표', '차이']), use_container_width=True, hide_index=True)

    # 3. 카테고리 분석
    with tabs[2]:
        for cat_name in ["세액공제 O", "세액공제 X", "ISA"]:
            sub_df = asset_df[asset_df['계좌카테고리'] == cat_name].copy()
            if sub_df.empty:
                continue

            st.subheader(f"🏦 {cat_name} 분석 및 매수 가이드")
            cat_eval = sub_df['평가금액'].sum()
            sub_grp = sub_df.groupby('자산군', dropna=False).agg({'평가금액': 'sum'}).reset_index()
            sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100 if cat_eval > 0 else 0
            sub_grp['목표'] = sub_grp['자산군'].map(cat_targets.get(cat_name, {})).fillna(0)
            sub_grp['차이'] = sub_grp['비중'] - sub_grp['목표']

            recom_type = "헤지" if current_fx > 1380 else "노출"
            for _, row in sub_grp.iterrows():
                if row['차이'] <= -3.0 and row['자산군'] in code_map:
                    rec_code = code_map[row['자산군']][recom_type]
                    st.info(f"💡 **{row['자산군']} 부족**: 현재 환율({current_fx:,.0f}원) 기준, **환{recom_type}형 ({rec_code})** 추가 매수를 권장합니다.")

            c1, c2 = st.columns(2)
            c1.plotly_chart(px.pie(sub_grp, values='비중', names='자산군', title="현재", hole=0.5).update_layout(height=280), use_container_width=True, key=f"cat_is_{cat_name}")
            c2.plotly_chart(px.pie(sub_grp, values='목표', names='자산군', title="목표", hole=0.5).update_layout(height=280), use_container_width=True, key=f"cat_to_{cat_name}")
            detail_cat_df = sub_df.assign(비중=(sub_df['평가금액'] / cat_eval) * 100 if cat_eval > 0 else 0)
            st.dataframe(
                get_styled_df(detail_cat_df.sort_values('비중', ascending=False), ['계좌명', '약식종목명', '평가금액', '비중', '수익률']),
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
            st.dataframe(
                get_styled_df(a_df.sort_values('비중', ascending=False), ['약식종목명', '보유수량', '현재가', '평가금액', '비중', '수익률']),
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
                st.write(f"#### 📊 {target_asset} (As-Is vs To-Be)")
                fx_sub['구분'] = fx_sub['약식종목명'].astype(str).apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                asis_grp = fx_sub.groupby('구분')['평가금액'].sum().reset_index()
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(
                        px.pie(
                            asis_grp,
                            values='평가금액',
                            names='구분',
                            title='현재',
                            hole=0.5,
                            color='구분',
                            color_discrete_map={'환노출': '#EF553B', '환헤지': '#636EFA'},
                        ).update_layout(height=230, margin=dict(t=30, b=10)),
                        use_container_width=True,
                        key=f"fx_asis_{cat_name}_{target_asset}",
                    )
                with c2:
                    st.plotly_chart(
                        px.pie(
                            pd.DataFrame([{'구분': '환노출', '값': t_fx['노출']}, {'구분': '환헤지', '값': t_fx['헤지']}]),
                            values='값',
                            names='구분',
                            title='목표',
                            hole=0.5,
                            color='구분',
                            color_discrete_map={'환노출': '#EF553B', '환헤지': '#636EFA'},
                        ).update_layout(height=230, margin=dict(t=30, b=10)),
                        use_container_width=True,
                        key=f"fx_tobe_{cat_name}_{target_asset}",
                    )
            st.markdown("---")

    # 6. 리밸런싱
    with tabs[5]:
        st.subheader("⚖️ 통합 목표 기반 리밸런싱")
        target_weights = {
            'S&P500': 0.45,
            '나스닥100': 0.25,
            '금': 0.15,
            '미국국채': 0.10,
            'KOFR': 0.05,
        }
        safe_assets = ['금', '미국국채', 'KOFR']

        col_t1, col_t2 = st.columns([1, 2])
        col_t1.write("**🎯 통합 목표 비중**")
        col_t1.json(target_weights)
        col_t2.info(f"**🛡️ IRP 안전자산 가이드**\n대상: {', '.join(safe_assets)}\n(계좌 잔액의 30% 우선 할당)")

        if st.button("🔄 리밸런싱 수량 계산"):
            alloc_result = run_rebalance(asset_df, target_weights, safe_assets)
            rebal_rows = []

            for acc, assets in alloc_result.items():
                for target_asset, target_amt in assets.items():
                    row = asset_df[(asset_df['계좌명'] == acc) & (asset_df['자산군'] == target_asset)]
                    curr_val = row['평가금액'].sum()

                    curr_price = 0
                    if not row.empty:
                        non_cash_prices = row.loc[row['현재가'] > 0, '현재가']
                        if not non_cash_prices.empty:
                            curr_price = float(non_cash_prices.iloc[0])

                    if curr_price <= 0:
                        continue

                    diff_qty = int((target_amt - curr_val) // curr_price)
                    if diff_qty != 0:
                        rebal_rows.append(
                            {
                                '계좌': acc,
                                '종목': target_asset,
                                '현재가': curr_price,
                                '목표금액': target_amt,
                                '조정수량': diff_qty,
                                '예상주문': diff_qty * curr_price,
                            }
                        )

            if rebal_rows:
                result_df = pd.DataFrame(rebal_rows)
                st.dataframe(
                    result_df.style.applymap(
                        lambda x: 'color: #d32f2f' if x > 0 else 'color: #1976d2',
                        subset=['조정수량'],
                    ).format({'목표금액': '{:,.0f}', '현재가': '{:,.0f}', '예상주문': '{:,.0f}', '조정수량': '{:+,.0f}'}),
                    use_container_width=True,
                    hide_index=True,
                )
            else:
                st.success("현재 비중이 완벽하거나, 리밸런싱 가능한 매핑 종목이 없습니다.")

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
