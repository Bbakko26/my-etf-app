import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

# [필수] 최상단 설정
st.set_page_config(page_title="Family Portfolio", layout="wide")

# 1. 데이터 로드
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

# 📍 애니메이션 최적화 함수 (프레임 속도 및 부드러움 조정)
def create_overlay_ani_pie(labels, current_vals, target_vals, title):
    colors = px.colors.qualitative.Pastel # 눈이 편안한 파스텔톤 사용
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}

    fig = go.Figure(
        layout=go.Layout(
            title=dict(text=title, font=dict(size=14)),
            updatemenus=[dict(
                type="buttons", x=0.1, y=1.15,
                buttons=[dict(label="▶ 시뮬레이션 (As-Is ↔ To-Be)", method="animate", 
                             args=[None, {"frame": {"duration": 800, "redraw": True}, "fromcurrent": True, "transition": {"duration": 500, "easing": "cubic-in-out"}}])]
            )]
        ),
        data=[
            # [뒤쪽: 목표 잔상]
            go.Pie(labels=labels, values=target_vals, hole=0.6, sort=False, opacity=0.3,
                   marker=dict(colors=[color_map[l] for l in labels]),
                   hoverinfo="label+percent", name="Target", domain={'x': [0, 1], 'y': [0, 1]}),
            # [앞쪽: 현재 상태]
            go.Pie(labels=labels, values=current_vals, hole=0.5, sort=False,
                   marker=dict(colors=[color_map[l] for l in labels], line=dict(color='#FFFFFF', width=2)),
                   hoverinfo="label+percent", name="As-Is", domain={'x': [0, 1], 'y': [0, 1]})
        ],
        frames=[
            go.Frame(data=[go.Pie(values=target_vals), go.Pie(values=current_vals)], name="f1"),
            go.Frame(data=[go.Pie(values=target_vals), go.Pie(values=target_vals)], name="f2"),
            go.Frame(data=[go.Pie(values=target_vals), go.Pie(values=current_vals)], name="f3")
        ]
    )
    fig.update_layout(height=400, margin=dict(t=80, b=20), legend=dict(orientation="h", y=-0.1))
    return fig

# 스타일 설정
st.markdown("<style>html,body,[class*='css']{font-size:12px!important;}h1{font-size:1.1rem!important;}[data-testid='stMetricValue']{font-size:1rem!important;}</style>", unsafe_allow_html=True)

try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- 📍 [TARGET_SETTING] ---
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "국내 ETF": 10.0, "금": 5.0, "현금": 15.0}
    group_targets = {
        "세액공제 계좌": {"나스닥100": 40.0, "S&P500": 40.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0},
        "ISA": {"다우존스": 50.0, "S&P500": 30.0, "현금": 20.0}
    }
    code_map = {"S&P500": {"노출": "360750", "헤지": "448290"}, "나스닥100": {"노출": "133690", "헤지": "448300"}, "다우존스": {"노출": "458730", "헤지": "452250"}}
    # --------------------------

    with st.spinner('데이터 업데이트 중...'):
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

    # 1. 종목 상세 (기존 로직 유지)
    with tabs[0]:
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['수익률'] = (sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액'] * 100
        st.dataframe(sum_df.sort_values('평가금액', ascending=False), use_container_width=True, hide_index=True)
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        if not detail_df.empty and detail_df['종목코드'].iloc[0].upper() != "CASH":
            hist = fdr.DataReader(detail_df['종목코드'].iloc[0]).tail(120)
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
            st.plotly_chart(fig, use_container_width=True)

    # 2. 비중 및 리밸런싱 (애니메이션 적용)
    with tabs[1]:
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        st.plotly_chart(create_overlay_ani_pie(grp_df['자산군'].tolist(), grp_df['비중'].tolist(), grp_df['목표'].tolist(), "전체 자산 배분 가이드"), use_container_width=True)

    # 3. 카테고리 분석 (📍 세액공제 통합 및 가이드)
    with tabs[2]:
        groups = {"세액공제 계좌": ["세액공제 O", "세액공제 X"], "ISA": ["ISA"]}
        for g_name, cats in groups.items():
            sub_df = asset_df[asset_df['계좌카테고리'].isin(cats)].copy()
            if not sub_df.empty:
                st.subheader(f"🏦 {g_name} 분석")
                cat_eval = sub_df['평가금액'].sum()
                sub_grp = sub_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
                sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100
                sub_grp['목표'] = sub_grp['자산군'].map(group_targets.get(g_name, {})).fillna(0)
                sub_grp['차이'] = sub_grp['비중'] - sub_grp['목표']
                
                # 가이드 결론 출력
                recom_fx = "헤지" if current_fx > 1380 else "노출"
                for _, row in sub_grp.iterrows():
                    if row['차이'] <= -3.0 and row['자산군'] in code_map:
                        st.info(f"💡 **{row['자산군']} 추가 매수 필요**: 환{recom_fx}형 ({code_map[row['자산군']][recom_fx]}) 추천")

                st.plotly_chart(create_overlay_ani_pie(sub_grp['자산군'].tolist(), sub_grp['비중'].tolist(), sub_grp['목표'].tolist(), f"{g_name} 시뮬레이션"), use_container_width=True, key=f"ani_{g_name}")
                st.markdown("---")

    # 5. 환율관리 (As-Is vs To-Be 상세화)
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
                    c1.plotly_chart(px.pie(asis, values='평가금액', names='구분', title=f"{asset} 현재", hole=0.5).update_layout(height=220), use_container_width=True, key=f"fx_is_{cat}_{asset}")
                    c2.plotly_chart(px.pie(pd.DataFrame([{"구분":"환노출", "v":t_fx['노출']}, {"구분":"환헤지", "v":t_fx['헤지']}]), values='v', names='구분', title=f"{asset} 목표", hole=0.5).update_layout(height=220), use_container_width=True, key=f"fx_to_{cat}_{asset}")

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
