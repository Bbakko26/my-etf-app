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

# 이중 도넛 함수 (기존 유지)
def create_double_donut(labels, current_vals, target_vals, title, key_id):
    colors = px.colors.qualitative.Pastel
    color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}
    fig = go.Figure()
    fig.add_trace(go.Pie(labels=labels, values=target_vals, hole=0.88, sort=False, opacity=0.3, marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels]), name="Target"))
    fig.add_trace(go.Pie(labels=labels, values=current_vals, hole=0.65, sort=False, marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels]), domain={'x': [0.1, 0.9], 'y': [0.1, 0.9]}, name="As-Is"))
    fig.update_layout(title=dict(text=title, font=dict(size=14)), height=300, margin=dict(t=50, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="h", y=-0.1))
    return fig

try:
    df_raw = load_data()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- [TARGET_SETTING] ---
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "다우존스": 10.0, "국내 ETF": 10.0, "금": 5.0, "현금": 15.0}
    code_map = {"S&P500": {"노출": "360750", "헤지": "448290"}, "나스닥100": {"노출": "133690", "헤지": "448300"}, "다우존스": {"노출": "458730", "헤지": "452250"}}
    # --------------------------

    with st.spinner('시세 동기화 중...'):
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금'] else 1.0) for code in asset_df['종목코드'].unique()}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval = asset_df['평가금액'].sum()

    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리", "6. 실탄 관리"])

    # (1~5번 탭은 기존 로직과 동일하므로 생략하거나 유지하시면 됩니다)

    # --- 6. 실탄 관리 (📍 신규 탭) ---
    with tabs[5]:
        st.subheader("🔋 미집행 자산(실탄) 운용 가이드")
        
        # 1. 현황 파악
        cash_assets = asset_df[asset_df['자산군'] == '현금']['평가금액'].sum()
        isa_unused = 20000000 - asset_df[asset_df['계좌카테고리'] == 'ISA']['평가금액'].sum() # 예: 연간 2천 한도 가정
        
        col1, col2 = st.columns(2)
        col1.metric("보유 실탄 (KOFR 등)", f"{cash_assets:,.0f}원")
        col2.metric("ISA 잔여 한도 (연간)", f"{max(0, isa_unused):,.0f}원")

        st.divider()
        
        # 2. 집행 스케줄링 계산
        st.markdown("### 🗓️ 순차 매수 스케줄링")
        weeks_left = (datetime(2026, 12, 31) - datetime.now()).days // 7
        if weeks_left > 0:
            weekly_invest = cash_assets / weeks_left
            st.info(f"💡 **정기 매수 가이드**: 올해 남은 {weeks_left}주 동안 매주 **평균 {weekly_invest:,.0f}원**씩 분할 매수하세요.")
        
        # 3. 환율 및 시장 상황별 대응
        st.markdown("### 🏹 상황별 타격 지점")
        
        # 환율 가이드
        recom_fx = "환헤지(H)형" if current_fx > 1420 else ("환노출형" if current_fx < 1350 else "중립(반반)")
        st.warning(f"💱 **환율 대응**: 현재 환율({current_fx:,.1f}원)은 고환율 구간입니다. 신규 매수는 **{recom_fx}** 종목을 우선 고려하세요.")
        
        # 지수 하락 시 대응 (MDD 기반 가상 시나리오)
        st.success(f"📉 **하락장 대응**: 주요 지수(S&P500 등)가 전고점 대비 **-10% 하락 시**, 보유 실탄의 20%인 **{(cash_assets * 0.2):,.0f}원**을 추가 투입하세요.")

        # 4. 추천 종목 (환율 반영)
        st.markdown("### 🎯 추천 타겟")
        target_type = "헤지" if current_fx > 1400 else "노출"
        recom_list = []
        for asset, codes in code_map.items():
            recom_list.append({"자산군": asset, "추천종목코드": codes[target_type], "유형": f"환{target_type}"})
        st.table(pd.DataFrame(recom_list))

except Exception as e:
    st.error(f"🚨 오류: {e}")
