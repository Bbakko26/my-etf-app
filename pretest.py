import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

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

# 📍 이중 도넛 차트 함수 (안쪽:현재, 바깥쪽 얇은 띠:목표)
def create_double_donut(labels, current_vals, target_vals, title, key_id):
    # 환율 관리용 색상 고정
    color_map = {'환노출': '#EF553B', '환헤지': '#636EFA'}
    # 자산군용 색상은 파스텔톤
    if labels and labels[0] not in color_map:
        colors = px.colors.qualitative.Pastel
        color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}

    fig = go.Figure()
    # 1. 바깥쪽 얇은 띠 (Target)
    fig.add_trace(go.Pie(
        labels=labels, values=target_vals, hole=0.88, sort=False, direction='clockwise',
        marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels], line=dict(color='white', width=1)),
        opacity=0.35, hoverinfo="label+percent", name="목표"
    ))
    # 2. 안쪽 메인 도넛 (As-Is)
    fig.add_trace(go.Pie(
        labels=labels, values=current_vals, hole=0.65, sort=False, direction='clockwise',
        marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels], line=dict(color='white', width=2)),
        hoverinfo="label+percent", name="현재", domain={'x': [0.1, 0.9], 'y': [0.1, 0.9]} 
    ))
    fig.update_layout(title=dict(text=title, font=dict(size=14)), height=350, margin=dict(t=50, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="h", y=-0.1))
    return fig

# 스타일 설정
st.markdown("<style>html,body,[class*='css']{font-size:12px!important;}h1{font-size:1.1rem!important;}[data-testid='stMetricValue']{font-size:1rem!important;}.stDataFrame div{font-size:11px!important;}</style>", unsafe_allow_html=True)

try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- 📍 [TARGET_SETTING] 목표 비중 및 종목 코드 설정 ---
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "다우존스": 10.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0}
    group_targets = {
        "세액공제 계좌": {"나스닥100": 40.0, "S&P500": 40.0, "국내 ETF": 10.0, "금": 5.0, "현금": 5.0},
        "ISA": {"다우존스": 50.0, "S&P500": 30.0, "현금": 20.0}
    }
    code_map = {
        "S&P500": {"노출": "360750", "헤지": "448290"},
        "나스닥100": {"노출": "133690", "헤지": "448300"},
        "다우존스": {"노출": "458730", "헤지": "452250"}
    }
    # -------------------------------------------------------

    with st.spinner('실시간 데이터 업데이트 중...'):
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금'] else 1.0) for code in asset_df['종목코드'].unique()}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval, total_seed = asset_df['평가금액'].sum(), (seed_df['보유수량'] * seed_df['매수평단']).sum()
    total_profit = total_eval - total_seed

    # 상단 메트릭스
    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit/total_seed*100) if total_seed > 0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리", "6. 실탄 관리"])

    # --- 1. 종목 상세 ---
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
            fig = go.Figure(data=[go.Candlestick(x=hist.index, open=hist['Open'], high=hist['High'], low=hist['Low'], close=hist['Close'])])
            avg_p = detail_df['매수금액'].sum() / detail_df['보유수량'].sum() if detail_df['보유수량'].sum() > 0 else 0
            if avg_p > 0: fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text=f"내 평단: {avg_p:,.0f}")
            fig.update_layout(height=400, xaxis_rangeslider_visible=False)
            st.plotly_chart(fig, use_container_width=True, key=f"dt_chart_{sel_name}")

    # --- 2. 비중 및 리밸런싱 ---
    with tabs[1]:
        st.subheader("📊 전체 비중 분석 (Double Donut)")
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        st.plotly_chart(create_double_donut(grp_df['자산군'].tolist(), grp_df['비중'].tolist(), grp_df['목표'].tolist(), "안쪽:현재 vs 바깥띠:목표", "total_double"), use_container_width=True)

    # --- 3. 카테고리 분석 ---
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
                
                # 가이드 결론
                recom_fx = "헤지" if current_fx > 1380 else "노출"
                for _, row in sub_grp.iterrows():
                    if row['차이'] <= -3.0 and row['자산군'] in code_map:
                        st.info(f"💡 **{row['자산군']} 부족**: 환{recom_fx}형 ({code_map[row['자산군']][recom_fx]}) 추가 매수")
                
                st.plotly_chart(create_double_donut(sub_grp['자산군'].tolist(), sub_grp['비중'].tolist(), sub_grp['목표'].tolist(), f"{g_name} 비중 비교", f"cat_{g_name}"), use_container_width=True)
                st.markdown("---")

    # --- 4. 계좌별 ---
    with tabs[3]:
        for acc in asset_df['계좌명'].unique():
            a_df = asset_df[asset_df['계좌명'] == acc].copy()
            st.markdown(f"### 🏦 {acc}")
            a_df['비중'] = (a_df['평가금액'] / a_df['평가금액'].sum()) * 100
            st.dataframe(a_df.sort_values('비중', ascending=False), use_container_width=True, hide_index=True)

    # --- 5. 환율관리 ---
    with tabs[4]:
        st.subheader(f"🌎 환율 가이드 (현재: {current_fx:,.0f}원)")
        t_fx = {"노출": 30, "헤지": 70} if current_fx > 1400 else ({"노출": 80, "헤지": 20} if current_fx < 1330 else {"노출": 50, "헤지": 50})
        fx_config = {"세액공제 O": ["S&P500", "나스닥100"], "세액공제 X": ["S&P500", "나스닥100"], "ISA": ["다우존스", "S&P500"]}
        for cat, targets in fx_config.items():
            st.markdown(f"### 🏦 {cat}")
            cols = st.columns(len(targets))
            for i, asset in enumerate(targets):
                f_df = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['자산군'] == asset)].copy()
                if not f_df.empty:
                    f_df['구분'] = f_df['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    asis = f_df.groupby('구분')['평가금액'].sum().reset_index()
                    labels = ['환노출', '환헤지']
                    curr_vals = [asis[asis['구분']==l]['평가금액'].sum() for l in labels]
                    total_asset_v = sum(curr_vals)
                    curr_pcts = [(v/total_asset_v)*100 if total_asset_v > 0 else 0 for v in curr_vals]
                    with cols[i]:
                        st.plotly_chart(create_double_donut(labels, curr_pcts, [t_fx['노출'], t_fx['헤지']], f"📊 {asset} 대응", f"fx_{cat}_{asset}"), use_container_width=True)

    # --- 6. 실탄 관리 (📍 신규 탭) ---
    with tabs[5]:
        st.subheader("🔋 미집행 자산(실탄) 운용 가이드")
        cash_sum = asset_df[asset_df['자산군'] == '현금']['평가금액'].sum()
        isa_rem = 20000000 - asset_df[asset_df['계좌카테고리'] == 'ISA']['평가금액'].sum()
        
        c1, c2 = st.columns(2)
        c1.metric("보유 실탄 (KOFR 등)", f"{cash_sum:,.0f}원")
        c2.metric("ISA 잔여 한도 (연간)", f"{max(0, isa_rem):,.0f}원")

        st.divider()
        st.markdown("### 🗓️ 순차 매수 스케줄링")
        days_left = (datetime(2026, 12, 31) - datetime.now()).days
        weeks_left = max(1, days_left // 7)
        weekly_invest = cash_sum / weeks_left
        st.info(f"💡 **분할 매수**: 올해 남은 {weeks_left}주 동안 매주 **평균 {weekly_invest:,.0f}원**씩 투입하세요.")
        
        st.markdown("### 🏹 상황별 타격 지점")
        recom_fx_type = "환헤지(H)형" if current_fx > 1420 else ("환노출형" if current_fx < 1350 else "중립(반반)")
        st.warning(f"💱 **환율 대응**: 현재 {current_fx:,.1f}원은 고환율입니다. **{recom_fx_type}** 위주로 집행하세요.")
        st.success(f"📉 **하락장 대응**: 지수 -10% 급락 시, 예비 실탄의 20%인 **{(cash_sum * 0.2):,.0f}원**을 즉시 투입하세요.")

        st.markdown("### 🎯 추천 종목 (환율 반영)")
        target_f = "헤지" if current_fx > 1400 else "노출"
        recom_df = pd.DataFrame([{"자산군": a, "추천코드": c[target_f], "유형": f"환{target_f}"} for a, c in code_map.items()])
        st.table(recom_df)

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
