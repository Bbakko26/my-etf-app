import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

# [필수] 최상단 설정
st.set_page_config(page_title="Family Portfolio", layout="wide")

# 1. 데이터 로드 및 전처리
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

# 📍 [NEW] 시뮬레이션 제거, 잔상(Overlay) 전용 차트 함수
def create_static_overlay_pie(labels, current_vals, target_vals, title):
    colors = px.colors.qualitative.Pastel
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}

    fig = go.Figure(
        data=[
            # [뒤쪽 레이어] 목표 비중 (잔상: 투명도 30%, 더 큰 외경)
            go.Pie(labels=labels, values=target_vals, hole=0.6, sort=False, opacity=0.3,
                   marker=dict(colors=[color_map[l] for l in labels]),
                   hoverinfo="label+percent", name="목표(Target)"),
            # [앞쪽 레이어] 현재 비중 (메인: 불투명, 표준 외경)
            go.Pie(labels=labels, values=current_vals, hole=0.5, sort=False,
                   marker=dict(colors=[color_map[l] for l in labels], line=dict(color='#FFFFFF', width=2)),
                   hoverinfo="label+percent", name="현재(As-Is)")
        ]
    )
    fig.update_layout(height=350, margin=dict(t=40, b=10, l=10, r=10), showlegend=True, 
                      legend=dict(orientation="h", y=-0.1), title=dict(text=title, font=dict(size=14)))
    return fig

# 스타일 설정
st.markdown("<style>html,body,[class*='css']{font-size:12px!important;}h1{font-size:1.1rem!important;}[data-testid='stMetricValue']{font-size:1rem!important;}.stDataFrame div{font-size:11px!important;}</style>", unsafe_allow_html=True)

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
    
    # --- 📍 [TARGET_SETTING] ---
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "다우존스": 10.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0}
    group_targets = {
        "세액공제 계좌": {"나스닥100": 40.0, "S&P500": 40.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0},
        "ISA": {"다우존스": 50.0, "S&P500": 30.0, "현금": 20.0}
    }
    code_map = {"S&P500": {"노출": "360750", "헤지": "448290"}, "나스닥100": {"노출": "133690", "헤지": "448300"}, "다우존스": {"노출": "458730", "헤지": "452250"}}
    # --------------------------

    with st.spinner('실시간 데이터 업데이트 중...'):
        unique_codes = asset_df['종목코드'].unique()
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금'] else 1.0) for code in unique_codes}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval, total_seed = asset_df['평가금액'].sum(), (seed_df['보유수량'] * seed_df['매수평단']).sum()
    total_profit = total_eval - total_seed

    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit/total_seed*100) if total_seed > 0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    # 📍 탭 이름 수정 완료
    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리"])

    # --- 1. 종목 상세 ---
    with tabs[0]:
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['매수평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['수익률'] = (sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액'] * 100
        st.dataframe(get_styled_df(sum_df.sort_values('평가금액', ascending=False), ['약식종목명', '자산군', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        if not detail_df.empty and detail_df['종목코드'].iloc[0].upper() != "CASH":
            hist = fdr.DataReader(detail_df['종목코드'].iloc[0]).tail(120)
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
            avg_p = detail_df['매수금액'].sum() / detail_df['보유수량'].sum() if detail_df['보유수량'].sum() > 0 else 0
            if avg_p > 0: fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text=f"내 평단: {avg_p:,.0f}")
            fig.update_layout(height=400, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True, key=f"candle_{sel_name}")

    # --- 2. 비중 및 리밸런싱 ---
    with tabs[1]:
        st.subheader("📊 전체 비중 가이드 (잔상 Overlay)")
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        grp_df['차이'] = grp_df['비중'] - grp_df['목표']
        
        # 가이드 텍스트 박스
        if len(grp_df[abs(grp_df['차이']) >= 5]) >= 3:
            st.error("🚨 **종합 리밸런싱 필요**: 목표 비중 이탈 자산이 3개 이상입니다.")
        
        st.plotly_chart(create_static_overlay_pie(grp_df['자산군'].tolist(), grp_df['비중'].tolist(), grp_df['목표'].tolist(), "전체 자산 배분 현황 (불투명:현재 vs 반투명:목표)"), use_container_width=True)
        st.dataframe(get_styled_df(grp_df.sort_values('비중', ascending=False), ['자산군', '평가금액', '비중', '목표', '차이']), use_container_width=True, hide_index=True)

    # --- 3. 카테고리 분석 (📍 세액공제 통합 및 가이드 강화) ---
    with tabs[2]:
        groups = {"세액공제 계좌": ["세액공제 O", "세액공제 X"], "ISA": ["ISA"]}
        for g_name, cats in groups.items():
            sub_df = asset_df[asset_df['계좌카테고리'].isin(cats)].copy()
            if not sub_df.empty:
                st.subheader(f"🏦 {g_name} 통합 분석")
                cat_eval = sub_df['평가금액'].sum()
                sub_grp = sub_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
                sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100
                sub_grp['목표'] = sub_grp['자산군'].map(group_targets.get(g_name, {})).fillna(0)
                sub_grp['차이'] = sub_grp['비중'] - sub_grp['목표']
                
                # 가이드 결론
                recom_type = "헤지" if current_fx > 1380 else "노출"
                for _, row in sub_grp.iterrows():
                    if row['차이'] <= -3.0 and row['자산군'] in code_map:
                        rec_code = code_map[row['자산군']][recom_type]
                        st.info(f"💡 **{row['자산군']} 추가 매수 필요**: 현재 환율 대응을 위해 **환{recom_type}형 ({rec_code})**을 추천합니다.")

                st.plotly_chart(create_static_overlay_pie(sub_grp['자산군'].tolist(), sub_grp['비중'].tolist(), sub_grp['목표'].tolist(), f"{g_name} 비중 분석"), use_container_width=True, key=f"overlay_{g_name}")
                st.dataframe(get_styled_df(sub_df.assign(비중=(sub_df['평가금액']/cat_eval)*100).sort_values('비중', ascending=False), ['계좌명', '약식종목명', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)
                st.markdown("---")

    # --- 4. 계좌별 ---
    with tabs[3]:
        for acc in asset_df['계좌명'].unique():
            a_df = asset_df[asset_df['계좌명'] == acc].copy()
            st.markdown(f"### 🏦 {acc}")
            a_df['비중'] = (a_df['평가금액'] / a_df['평가금액'].sum()) * 100
            st.dataframe(get_styled_df(a_df.sort_values('비중', ascending=False), ['약식종목명', '보유수량', '현재가', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)

    # --- 5. 환율관리 ---
    with tabs[4]:
        st.subheader(f"🌎 실시간 환율: {current_fx:,.2f}원")
        t_fx = {"노출": 30, "헤지": 70} if current_fx > 1400 else ({"노출": 80, "헤지": 20} if current_fx < 1330 else {"노출": 50, "헤지": 50})
        fx_config = {"세액공제 O": ["S&P500", "나스닥100"], "세액공제 X": ["S&P500", "나스닥100"], "ISA": ["다우존스", "S&P500"]}
        
        for cat, targets in fx_config.items():
            st.markdown(f"### 🏦 {cat}")
            for asset in targets:
                f_df = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['자산군'] == asset)].copy()
                if not f_df.empty:
                    st.write(f"#### 📊 {asset} (As-Is vs To-Be)")
                    f_df['구분'] = f_df['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    asis = f_df.groupby('구분')['평가금액'].sum().reset_index()
                    c1, c2 = st.columns(2)
                    c1.plotly_chart(px.pie(asis, values='평가금액', names='구분', title="현재", hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}).update_layout(height=230, showlegend=False), use_container_width=True, key=f"fx_is_{cat}_{asset}")
                    c2.plotly_chart(px.pie(pd.DataFrame([{"구분":"환노출", "v":t_fx['노출']}, {"구분":"환헤지", "v":t_fx['헤지']}]), values='v', names='구분', title="목표", hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}).update_layout(height=230, showlegend=False), use_container_width=True, key=f"fx_to_{cat}_{asset}")
            st.markdown("---")

except Exception as e:
    st.error(f"🚨 오류: {e}")
