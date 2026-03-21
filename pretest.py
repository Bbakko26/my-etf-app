import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

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

# 이중 도넛 함수 (고유 키 인자 추가)
def create_double_donut(labels, current_vals, target_vals, title):
    color_map = {'환노출': '#EF553B', '환헤지': '#636EFA'}
    if labels and labels[0] not in color_map:
        colors = px.colors.qualitative.Pastel
        color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}
    fig = go.Figure()
    fig.add_trace(go.Pie(labels=labels, values=target_vals, hole=0.88, sort=False, direction='clockwise',
        marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels], line=dict(color='white', width=1)),
        opacity=0.3, hoverinfo="label+percent", name="목표"))
    fig.add_trace(go.Pie(labels=labels, values=current_vals, hole=0.65, sort=False, direction='clockwise',
        marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels], line=dict(color='white', width=2)),
        hoverinfo="label+percent", name="현재", domain={'x': [0.1, 0.9], 'y': [0.1, 0.9]}))
    fig.update_layout(title=dict(text=title, font=dict(size=13)), height=320, margin=dict(t=50, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="h", y=-0.1))
    return fig

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

    with st.spinner('실시간 데이터 업데이트 중...'):
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금'] else 1.0) for code in asset_df['종목코드'].unique()}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval = asset_df['평가금액'].sum()

    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리", "6. 실탄 관리"])

    # --- 1. 종목 상세 ---
    with tabs[0]:
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '평가금액':'sum'}).reset_index()
        st.dataframe(sum_df.sort_values('평가금액', ascending=False), use_container_width=True, hide_index=True)
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[asset_df['종목명'] == sel_name].copy()
        if not detail_df.empty and detail_df['종목코드'].iloc[0].upper() != "CASH":
            hist = fdr.DataReader(detail_df['종목코드'].iloc[0]).tail(120)
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
            st.plotly_chart(fig, use_container_width=True, key=f"candle_{sel_name}")

    # --- 2. 비중 및 리밸런싱 ---
    with tabs[1]:
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        st.plotly_chart(create_double_donut(grp_df['자산군'].tolist(), grp_df['비중'].tolist(), grp_df['목표'].tolist(), "전체 비중 분석"), use_container_width=True, key="main_donut")

    # --- 3. 카테고리 분석 ---
    with tabs[2]:
        groups = {"세액공제 계좌": ["세액공제 O", "세액공제 X"], "ISA": ["ISA"]}
        for g_name, cats in groups.items():
            sub_df = asset_df[asset_df['계좌카테고리'].isin(cats)].copy()
            if not sub_df.empty:
                st.subheader(f"🏦 {g_name} 통합 분석")
                sub_grp = sub_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
                sub_grp['비중'] = (sub_grp['평가금액'] / sub_df['평가금액'].sum()) * 100
                sub_grp['목표'] = sub_grp['자산군'].map(group_targets.get(g_name, {})).fillna(0)
                st.plotly_chart(create_double_donut(sub_grp['자산군'].tolist(), sub_grp['비중'].tolist(), sub_grp['목표'].tolist(), f"{g_name} 비교"), use_container_width=True, key=f"cat_donut_{g_name}")

    # --- 5. 환율관리 ---
    with tabs[4]:
        st.subheader(f"🌎 실시간 환율: {current_fx:,.2f}원")
        # 환율 구간별 목표 자동 설정
        if current_fx >= 1450: t_fx = {"노출": 0, "헤지": 100}
        elif current_fx >= 1400: t_fx = {"노출": 30, "헤지": 70}
        elif current_fx >= 1330: t_fx = {"노출": 70, "헤지": 30}
        else: t_fx = {"노출": 100, "헤지": 0}

        fx_config = {"세액공제 O": ["S&P500", "나스닥100"], "세액공제 X": ["S&P500", "나스닥100"], "ISA": ["다우존스", "S&P500"]}
        for cat, targets in fx_config.items():
            st.markdown(f"#### 🏦 {cat}")
            cols = st.columns(len(targets))
            for i, asset in enumerate(targets):
                f_df = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['자산군'] == asset)].copy()
                if not f_df.empty:
                    f_df['구분'] = f_df['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    asis = f_df.groupby('구분')['평가금액'].sum().reset_index()
                    labels = ['환노출', '환헤지']
                    curr_vals = [asis[asis['구분']==l]['평가금액'].sum() for l in labels]
                    curr_p = [(v/sum(curr_vals))*100 if sum(curr_vals)>0 else 0 for v in curr_vals]
                    with cols[i]:
                        st.plotly_chart(create_double_donut(labels, curr_p, [t_fx['노출'], t_fx['헤지']], f"{asset} 대응"), use_container_width=True, key=f"fx_donut_{cat}_{asset}")

        st.divider()
        st.subheader("📈 원/달러 환율 구간별 정밀 액션 가이드")
        # 📍 [FIX] SyntaxError 해결: 딕셔너리 키 '기존 보유분 관리' 명시
        guide_data = [
            {"환율 구간": "1,450원 이상", "단계": "심각", "신규 매수 액션": "100% 환헤지(H) 종목만 매수", "기존 보유분 관리": "기존 환노출 수익분의 50% 이상을 (H)로 스위칭"},
            {"환율 구간": "1,400 ~ 1,450원", "단계": "주의", "신규 매수 액션": "환헤지(H) 70% : 환노출 30%", "기존 보유분 관리": "신규 적립금으로 환헤지 비중을 우선 채움"},
            {"환율 구간": "1,330 ~ 1,400원", "단계": "중립", "신규 매수 액션": "환헤지(H) 30% : 환노출 70%", "기존 보유분 관리": "비중 이탈이 없다면 기존 포지션 유지"},
            {"환율 구간": "1,250 ~ 1,330원", "단계": "안정", "신규 매수 액션": "100% 환노출 종목 매수", "기존 보유분 관리": "환헤지(H) 종목을 환노출로 서서히 교체 시작"},
            {"환율 구간": "1,250원 미만", "단계": "기회", "신규 매수 액션": "100% 환노출 + 적극 매수", "기존 보유분 관리": "모든 (H) 종목을 환노출로 전환 완료"}
        ]
        guide_df = pd.DataFrame(guide_data)

        def highlight_row(row):
            active = False
            r = row['환율 구간']
            if "이상" in r and current_fx >= 1450: active = True
            elif "미만" in r and current_fx < 1250: active = True
            elif "~" in r:
                low, high = map(lambda x: float(x.replace(',','').replace('원','').strip()), r.split('~'))
                if low <= current_fx < high: active = True
            return ['background-color: rgba(255, 75, 75, 0.2);' if active else '' for _ in row]

        st.table(guide_df.style.apply(highlight_row, axis=1))

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
