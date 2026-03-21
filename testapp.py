import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

# [필수] 최상단 설정
st.set_page_config(page_title="Family Portfolio", layout="wide")

# 1. 데이터 로드 함수 (파일명: my_assets.csv)
def load_data():
    target_file = 'my_assets.csv' 
    try:
        df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})
    
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)
    df['매수평단'] = pd.to_numeric(df['매수평단'], errors='coerce').fillna(0)
    if '자산군' not in df.columns: df['자산군'] = df['약식종목명']
    return df

# 스타일 및 포맷팅 설정
st.markdown("""<style>
    html, body, [class*="css"] { font-size: 12px !important; }
    h1 { font-size: 1.1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.0rem !important; }
    .stDataFrame div { font-size: 11px !important; }
    </style>""", unsafe_allow_html=True)

def safe_format(val):
    try: return f"{float(val):,.0f}"
    except: return val

def get_styled_df(target_df, cols_to_show):
    available_cols = [c for c in cols_to_show if c in target_df.columns]
    df_view = target_df[available_cols].copy().astype(object)
    if '종목코드' in target_df.columns:
        is_cash = target_df['종목코드'].str.upper() == 'CASH'
        for c in ['보유수량', '매수평단', '현재가']:
            if c in df_view.columns: df_view.loc[is_cash, c] = "-"
    rename_map = {'계좌명':'계좌', '약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}
    df_view = df_view.rename(columns=rename_map)
    format_rules = {'평가액': '{:,.0f}', '수익률': '{:.2f}%', '비중': '{:.1f}%', '목표': '{:.1f}%', '차이': '{:+.1f}%'}
    for col in ['수량', '평단', '현재가']:
        if col in df_view.columns: format_rules[col] = lambda x: safe_format(x)
    return df_view.style.format(format_rules)

try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- 📍 [TARGET_SETTING] 목표 설정 및 종목 매핑 ---
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "국내 ETF": 10.0, "금": 5.0, "현금": 15.0}
    cat_targets = {
        "세액공제 O": {"나스닥100": 40.0, "S&P500": 40.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0},
        "세액공제 X": {"나스닥100": 50.0, "S&P500": 50.0},
        "ISA": {"다우존스": 50.0, "S&P500": 30.0, "현금": 20.0} # 📍 수정됨
    }
    code_map = {
        "S&P500": {"노출": "360750", "헤지": "448290"},
        "나스닥100": {"노출": "133690", "헤지": "448300"},
        "다우존스": {"노출": "458730", "헤지": "452250"} # 📍 수정됨
    }
    # -------------------------------------------------------

    with st.spinner('실시간 데이터 업데이트 중...'):
        unique_codes = asset_df['종목코드'].unique()
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금','NAN',''] else 1.0) for code in unique_codes}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval = asset_df['평가금액'].sum()
    total_seed = (seed_df['보유수량'] * seed_df['매수평단']).sum()
    total_profit = total_eval - total_seed

class PortfolioRebalancer:
    def __init__(self, target_weights, safe_assets):
        self.target_weights = target_weights  # 예: {'S&P500': 0.45, '나스닥100': 0.25, ...}
        self.safe_assets = safe_assets        # IRP용 안전자산 리스트

    def run(self, df):
        # 실시간 잔액 및 가격 정보 추출
        account_balances = df.groupby('계좌명')['평가금액'].sum().to_dict()
        total_assets = sum(account_balances.values())
        current_prices = df.set_index('약식종목명')['현재가'].to_dict()
        
        # 전체 통합 목표 금액 설정
        overall_targets = {t: total_assets * w for t, w in self.target_weights.items()}
        allocation = {acc: {t: 0 for t in self.target_weights} for acc in account_balances}
        remaining_targets = overall_targets.copy()

        # [단계 1] IRP 안전자산 30% 우선 할당 (성과급 변동 대응 핵심)
        irp_accs = [a for a in account_balances if 'IRP' in a]
        for acc in irp_accs:
            req_safe = account_balances[acc] * 0.3
            allocated = 0
            # 안전자산 중 목표 비중이 높은 순서대로 IRP에 먼저 채움
            for t in sorted(self.safe_assets, key=lambda x: self.target_weights.get(x, 0), reverse=True):
                if allocated >= req_safe: break
                fill = min(remaining_targets.get(t, 0), req_safe - allocated)
                allocation[acc][t] = fill
                allocated += fill
                remaining_targets[t] -= fill

        # [단계 2] 나머지 잔액을 가중평균으로 배분 (전체 비중 유지)
        for acc, bal in account_balances.items():
            avail = bal - sum(allocation[acc].values())
            rem_total = sum(remaining_targets.values())
            if rem_total > 0:
                for t in self.target_weights:
                    if remaining_targets[t] > 0:
                        share = remaining_targets[t] / rem_total
                        add = min(remaining_targets[t], avail * share)
                        
                        # IRP 위험자산 70% 캡(Cap) 재검증
                        if 'IRP' in acc and t not in self.safe_assets:
                            limit = (bal * 0.7) - sum(v for k, v in allocation[acc].items() if k not in self.safe_assets)
                            add = min(add, max(0, limit))
                            
                        allocation[acc][t] += add
                        remaining_targets[t] -= add

        return allocation, current_prices

    # 상단 대시보드
    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit/total_seed*100) if total_seed > 0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    tabs = st.tabs(["📊 종목 상세", "🍩 전체 비중", "🏦 카테고리 분석", "💼 계좌별", "🌎 환율관리", "⚖️ 리밸런싱"])

    # --- 1. 종목 상세 ---
    with tabs[0]:
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['매수평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['수익률'] = (sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액'] * 100
        st.dataframe(get_styled_df(sum_df.sort_values('평가금액', ascending=False), ['약식종목명', '자산군', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)
        
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        st.dataframe(get_styled_df(detail_df[detail_df['보유수량']>0], ['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)
        
        if not detail_df.empty:
            code = detail_df['종목코드'].iloc[0]
            if code.upper() != "CASH":
                try:
                    hist_data = fdr.DataReader(code).tail(120)
                    fig = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
                    avg_p = detail_df['매수금액'].sum() / detail_df['보유수량'].sum() if detail_df['보유수량'].sum() > 0 else 0
                    if avg_p > 0:
                        fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text=f"내 평단: {avg_p:,.0f}", annotation_position="top left")
                    fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True, key=f"candle_{code}")
                except: st.info("차트 데이터를 불러올 수 없습니다.")

    # --- 2. 전체 비중 ---
    with tabs[1]:
        st.subheader("📊 전체 포트폴리오 상태")
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        grp_df['차이'] = grp_df['비중'] - grp_df['목표']
        
        if len(grp_df[abs(grp_df['차이']) >= 5]) >= 3:
            st.error("🚨 **종합 리밸런싱 필요**: 목표 비중 이탈 자산군이 3개 이상입니다.")
        
        c1, c2 = st.columns(2)
        c1.plotly_chart(px.pie(grp_df, values='비중', names='자산군', title="현재(As-Is)", hole=0.5).update_layout(height=300), use_container_width=True, key="p2_is")
        c2.plotly_chart(px.pie(grp_df, values='목표', names='자산군', title="목표(Target)", hole=0.5).update_layout(height=300), use_container_width=True, key="p2_to")
        st.dataframe(get_styled_df(grp_df.sort_values('비중', ascending=False), ['자산군', '평가금액', '비중', '목표', '차이']), use_container_width=True, hide_index=True)

    # --- 3. 카테고리 분석 ---
    with tabs[2]:
        for cat_name in ["세액공제 O", "세액공제 X", "ISA"]:
            sub_df = asset_df[asset_df['계좌카테고리'] == cat_name].copy()
            if not sub_df.empty:
                st.subheader(f"🏦 {cat_name} 분석 및 매수 가이드")
                cat_eval = sub_df['평가금액'].sum()
                sub_grp = sub_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
                sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100
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
                st.dataframe(get_styled_df(sub_df.assign(비중=(sub_df['평가금액']/cat_eval)*100).sort_values('비중', ascending=False), ['계좌명', '약식종목명', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)
                st.markdown("---")

    # --- 4. 계좌별 ---
    with tabs[3]:
        for acc in asset_df['계좌명'].unique():
            a_df = asset_df[asset_df['계좌명'] == acc].copy()
            st.markdown(f"### 🏦 {acc}")
            a_df['비중'] = (a_df['평가금액'] / a_df['평가금액'].sum()) * 100
            st.dataframe(get_styled_df(a_df.sort_values('비중', ascending=False), ['약식종목명', '보유수량', '현재가', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)

    # --- 5. 환율관리 (📍 자산군 이름 '다우존스'로 수정됨) ---
    with tabs[4]:
        st.subheader(f"🌎 실시간 환율: {current_fx:,.2f}원")
        t_fx = {"노출": 30, "헤지": 70} if current_fx > 1400 else ({"노출": 80, "헤지": 20} if current_fx < 1330 else {"노출": 50, "헤지": 50})
        
        fx_config = {
            "세액공제 O": ["S&P500", "나스닥100"],
            "세액공제 X": ["S&P500", "나스닥100"],
            "ISA": ["다우존스", "S&P500"] # 📍 수정됨
        }
        
        for cat_name, targets in fx_config.items():
            st.markdown(f"### 🏦 {cat_name}")
            for target_asset in targets:
                fx_sub = asset_df[(asset_df['계좌카테고리'] == cat_name) & (asset_df['자산군'] == target_asset)].copy()
                if not fx_sub.empty:
                    st.write(f"#### 📊 {target_asset} (As-Is vs To-Be)")
                    fx_sub['구분'] = fx_sub['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    asis_grp = fx_sub.groupby('구분')['평가금액'].sum().reset_index()
                    c1, c2 = st.columns(2)
                    with c1: st.plotly_chart(px.pie(asis_grp, values='평가금액', names='구분', title="현재", hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}).update_layout(height=230, margin=dict(t=30, b=10)), use_container_width=True, key=f"fx_asis_{cat_name}_{target_asset}")
                    with c2: st.plotly_chart(px.pie(pd.DataFrame([{"구분":"환노출", "값":t_fx['노출']}, {"구분":"환헤지", "값":t_fx['헤지']}]), values='값', names='구분', title="목표", hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}).update_layout(height=230, margin=dict(t=30, b=10)), use_container_width=True, key=f"fx_tobe_{cat_name}_{target_asset}")
            st.markdown("---")
    
    
    # --- 6. 리밸런싱
    with tabs[5]:
        st.subheader("⚖️ 통합 목표 기반 리밸런싱")
        
        # 1. 사용자 정의 통합 목표 (수치 수정 가능)
        # S&P500 45%, 나스닥 25%, 금 15%, 국채 10%, 현금 5%
        target_weights = {
            'S&P500': 0.45, '나스닥100': 0.25, 
            '금': 0.15, '미국국채': 0.10, 'KOFR': 0.05
        }
        safe_assets = ['금', '미국국채', 'KOFR'] # IRP 안전자산 인정 종목

        # 2. 리밸런싱 계산 엔진
        def run_rebalance(df, targets, safes):
            # 계좌별 잔액 합산
            acc_balances = df.groupby('계좌명')['평가금액'].sum().to_dict()
            total_val = sum(acc_balances.values())
            
            # 전체 자산 대비 종목별 목표 금액 (가중평균 기준)
            overall_targets = {t: total_val * w for t, w in targets.items()}
            allocation = {acc: {t: 0 for t in targets} for acc in acc_balances}
            rem_targets = overall_targets.copy()

            # [Step A] IRP 안전자산 30% 우선 할당 (성과급 변동 대응)
            irp_accs = [a for a in acc_balances if 'IRP' in a]
            for acc in irp_accs:
                req_safe = acc_balances[acc] * 0.3
                allocated = 0
                for t in sorted(safes, key=lambda x: targets.get(x, 0), reverse=True):
                    if allocated >= req_safe: break
                    fill = min(rem_targets.get(t, 0), req_safe - allocated)
                    allocation[acc][t] = fill
                    allocated += fill
                    rem_targets[t] -= fill

            # [Step B] 나머지 잔액 배분
            for acc, bal in acc_balances.items():
                avail = bal - sum(allocation[acc].values())
                rem_total = sum(rem_targets.values())
                if rem_total > 0:
                    for t in targets:
                        if rem_targets[t] > 0:
                            share = rem_targets[t] / rem_total
                            add = min(rem_targets[t], avail * share)
                            # IRP 70% 위험자산 캡 체크
                            if 'IRP' in acc and t not in safes:
                                limit = (bal * 0.7) - sum(v for k, v in allocation[acc].items() if k not in safes)
                                add = min(add, max(0, limit))
                            allocation[acc][t] += add
                            rem_targets[t] -= add
            return allocation

        # 3. UI 및 결과 출력
        col_t1, col_t2 = st.columns([1, 2])
        col_t1.write("**🎯 통합 목표 비중**")
        col_t1.json(target_weights)
        col_t2.info(f"**🛡️ IRP 안전자산 가이드**\n대상: {', '.join(safes)}\n(계좌 잔액의 30% 우선 할당)")

        if st.button("🔄 리밸런싱 수량 계산"):
            alloc_result = run_rebalance(asset_df, target_weights, safe_assets)
            
            rebal_rows = []
            for acc, assets in alloc_result.items():
                for t, target_amt in assets.items():
                    # 현재가 및 보유량 매칭
                    row = asset_df[(asset_df['계좌명'] == acc) & (asset_df['약식종목명'] == t)]
                    curr_price = row['현재가'].iloc[0] if not row.empty else price_map.get(t, 0)
                    curr_val = row['평가금액'].sum()
                    
                    if curr_price > 0:
                        diff_qty = int((target_amt - curr_val) // curr_price)
                        if diff_qty != 0:
                            rebal_rows.append({
                                '계좌': acc, '종목': t, '현재가': curr_price,
                                '목표금액': target_amt, '조정수량': diff_qty, '예상주문': diff_qty * curr_price
                            })
            
            if rebal_rows:
                st.dataframe(pd.DataFrame(rebal_rows).style.applymap(
                    lambda x: 'color: #d32f2f' if x > 0 else 'color: #1976d2', subset=['조정수량']
                ).format({'목표금액': '{:,.0f}', '현재가': '{:,.0f}', '예상주문': '{:,.0f}'}), 
                use_container_width=True, hide_index=True)
            else:
                st.success("현재 비중이 완벽합니다!")

# --- 최하단 마감 (반드시 이 구조여야 함) ---
except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
