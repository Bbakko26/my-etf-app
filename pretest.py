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

# 📍 [NEW] 이중 도넛 차트 함수 (안쪽:현재, 바깥쪽 얇은 띠:목표)
def create_double_donut(labels, current_vals, target_vals, title):
    colors = px.colors.qualitative.Pastel
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}

    fig = go.Figure()

    # 1. 바깥쪽 얇은 띠 (목표 비중 - 가이드라인 역할)
    fig.add_trace(go.Pie(
        labels=labels, values=target_vals,
        hole=0.85, # 매우 얇게 설정
        sort=False,
        direction='clockwise',
        marker=dict(colors=[color_map[l] for l in labels], line=dict(color='white', width=1)),
        opacity=0.4, # 가이드라인이므로 반투명하게
        hoverinfo="label+percent+name",
        name="목표(Target)"
    ))

    # 2. 안쪽 메인 도넛 (현재 비중)
    fig.add_trace(go.Pie(
        labels=labels, values=current_vals,
        hole=0.6, # 바깥 띠보다 안쪽에 위치
        sort=False,
        direction='clockwise',
        marker=dict(colors=[color_map[l] for l in labels], line=dict(color='white', width=2)),
        hoverinfo="label+percent+name",
        name="현재(As-Is)",
        # 도넛 크기 조절을 위해 domain 사용
        domain={'x': [0.08, 0.92], 'y': [0.08, 0.92]} 
    ))

    fig.update_layout(
        title=dict(text=title, font=dict(size=15)),
        height=400,
        margin=dict(t=50, b=10, l=10, r=10),
        showlegend=True,
        legend=dict(orientation="h", y=-0.1)
    )
    return fig

# 스타일 설정
st.markdown("<style>html,body,[class*='css']{font-size:12px!important;}h1{font-size:1.1rem!important;}[data-testid='stMetricValue']{font-size:1rem!important;}</style>", unsafe_allow_html=True)

try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- [TARGET_SETTING] ---
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "다우존스": 10.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0}
    group_targets = {
        "세액공제 계좌": {"나스닥100": 40.0, "S&P500": 40.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0},
        "ISA": {"다우존스": 50.0, "S&P500": 30.0, "현금": 20.0}
    }
    code_map = {"S&P500": {"노출": "360750", "헤지": "448290"}, "나스닥100": {"노출": "133690", "헤지": "448300"}, "다우존스": {"노출": "458730", "헤지": "452250"}}
    # --------------------------

    with st.spinner('데이터 동기화 중...'):
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금'] else 1.0) for code in asset_df['종목코드'].unique()}
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

    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리"])

    # 1. 종목 상세 (차트 복구)
    with tabs[0]:
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['매수평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['수익률'] = (sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액'] * 100
        st.dataframe(sum_df.sort_values('평가금액', ascending=False), use_container_width=True, hide_index=True)
        
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        if not detail_df.empty and detail_df['종목코드'].iloc[0].upper() != "CASH":
            hist = fdr.DataReader(detail_df['종목코드'].iloc[0]).tail(120)
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'], increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
            avg_p = detail_df['매수금액'].sum() / detail_df['보유수량'].sum() if detail_df['보유수량'].sum() > 0 else 0
            if avg_p > 0: fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text=f"내 평단: {avg_p:,.0f}")
            fig.update_layout(height=400, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True, key=f"chart_{sel_name}") # key 추가

    # 2. 비중 및 리밸런싱 (📍 이중 도넛 적용)
    with tabs[1]:
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        
        st.plotly_chart(create_double_donut(grp_df['자산군'].tolist(), grp_df['비중'].tolist(), grp_df['목표'].tolist(), "전체 비중 분석 (안쪽:현재 vs 바깥띠:목표)"), use_container_width=True, key="main_double_donut")

    # 3. 카테고리 분석 (📍 이중 도넛 및 가이드)
    with tabs[2]:
        groups = {"세액공제 계좌": ["세액공제 O", "세액공제 X"], "ISA": ["ISA"]}
        for g_name, cats in groups.items():
            sub_df = asset_df[asset_df['계좌카테고리'].isin(cats)].copy()
            if not sub_df.empty:
                st.subheader(f"🏦 {g_name} 통합 가이드")
                cat_eval = sub_df['평가금액'].sum()
                sub_grp = sub_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
                sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100
                sub_grp['목표'] = sub_grp['자산군'].map(group_targets.get(g_name, {})).fillna(0)
                sub_grp['차이'] = sub_grp['비중'] - sub_grp['목표']
                
                # 정밀 가이드
                recom_fx = "헤지" if current_fx > 1380 else "노출"
                for _, row in sub_grp.iterrows():
                    if row['차이'] <= -3.0 and row['자산군'] in code_map:
                        st.info(f"💡 **{row['자산군']} 부족**: 환{recom_fx}형 ({code_map[row['자산군']][recom_fx]}) 추가 매수 권장")

                st.plotly_chart(create_double_donut(sub_grp['자산군'].tolist(), sub_grp['비중'].tolist(), sub_grp['목표'].tolist(), f"{g_name} 비중 비교"), use_container_width=True, key=f"cat_double_{g_name}")
                st.markdown("---")

    # 4. 계좌별 / 5. 환율관리 (기존 로직 유지하되 key 보강)
    with tabs[4]:
        st.subheader(f"🌎 환율 가이드 (현재: {current_fx:,.0f}원)")
        t_fx = {"노출": 30, "헤지": 70} if current_fx > 1400 else ({"노출": 80, "헤지": 20} if current_fx < 1330 else {"노출": 50, "헤지": 50})
        fx_config = {"세액공제 O": ["S&P500", "나스닥100"], "세액공제 X": ["S&P500", "나스닥100"], "ISA": ["다우존스", "S&P500"]}
        for cat, targets in fx_config.items():
            st.markdown(f"### 🏦 {cat}")
            for asset in targets:
                f_df = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['자산군'] == asset)].copy()
                if not f_df.empty:
                    f_df['구분'] = f_df['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    asis = f_df.groupby('구분')['평가금액'].sum().reset_index()
                    c1, c2 = st.columns(2)
                    c1.plotly_chart(px.pie(asis, values='평가금액', names='구분', title=f"{asset} 현재", hole=0.5).update_layout(height=220), use_container_width=True, key=f"fx_asis_{cat}_{asset}")
                    c2.plotly_chart(px.pie(pd.DataFrame([{"구분":"환노출", "v":t_fx['노출']}, {"구분":"환헤지", "v":t_fx['헤지']}]), values='v', names='구분', title=f"{asset} 목표", hole=0.5).update_layout(height=220), use_container_width=True, key=f"fx_tobe_{cat}_{asset}")

except Exception as e:
    st.error(f"🚨 오류 발생: {e}")
except Exception as e:
    st.error(f"🚨 오류: {e}")
