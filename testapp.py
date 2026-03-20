import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

st.set_page_config(page_title="Family Portfolio", layout="wide")

# 1. 데이터 로드
def load_data():
    target_file = 'my_assets_ex.csv'
    try:
        df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)
    df['매수평단'] = pd.to_numeric(df['매수평단'], errors='coerce').fillna(0)
    return df

# 스타일 및 포맷팅 함수
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
    rename_map = {'계좌명':'계좌', '약식종목명':'종목', '평가금액':'평가액'}
    df_view = df_view.rename(columns=rename_map)
    format_rules = {'평가액': '{:,.0f}', '수익률': '{:.2f}%', '비중': '{:.1f}%', '차이': '{:+.1f}%', '목표': '{:.1f}%'}
    for col in ['보유수량', '매수평단', '현재가']:
        if col in df_view.columns: format_rules[col] = lambda x: safe_format(x)
    return df_view.style.format(format_rules)

try:
    df_raw = load_data()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- 📍 [TARGET_SETTING] 여기서 목표 비중을 수정하세요 ---
    # 순차적 매수 구간일 경우, 현재 보유하고자 하는 '현금' 비중을 먼저 정하고 나머지를 배분하세요.
    base_target = {
        "나스닥100": 30.0,
        "S&P500": 30.0,
        "미국배당다우존스": 10.0,
        "국내 ETF": 10.0,
        "금": 5.0,
        "현금": 15.0  # 현재 순차 매수 중이라면 현금 비중을 높게 잡으세요.
    }
    # -------------------------------------------------------

    with st.spinner('시세 동기화 중...'):
        unique_codes = asset_df['종목코드'].unique()
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금','NAN',''] else 1.0) for code in unique_codes}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval = asset_df['평가금액'].sum()

    tabs = st.tabs(["📊 상세", "🏦 분석 및 리밸런싱", "💼 전체", "🌎 환율관리"])

    # --- TAB 2: 분석 및 리밸런싱 ---
    with tabs[1]:
        st.subheader("🎯 포트폴리오 리밸런싱 엔진")
        
        # 자산군별 집계 및 목표 매핑
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['현재비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(base_target).fillna(0)
        grp_df['차이'] = grp_df['현재비중'] - grp_df['목표']
        
        # 리밸런싱 로직 판단
        over_limit_stocks = grp_df[abs(grp_df['차이']) >= 5.0]
        
        if len(over_limit_stocks) >= 3:
            st.error(f"🚨 **종합 리밸런싱 필요**: 5% 이상 이격된 자산이 {len(over_limit_stocks)}개입니다. 전체 비중 조절을 권장합니다.")
        elif len(over_limit_stocks) > 0:
            st.warning(f"⚠️ **부분 리밸런싱 알림**: 일부 자산이 목표 비중을 벗어났습니다.")
        else:
            st.success("✅ 현재 모든 자산이 목표 비중 내에서 양호하게 유지되고 있습니다.")

        # 추가 매수 가이드 결론 (텍스트)
        for _, row in grp_df.iterrows():
            if row['차이'] <= -3.0:
                # 환율에 따른 종목 추천 분기
                recom_type = "환헤지(H) 종목" if current_fx > 1400 else "환노출형 종목"
                if row['자산군'] == "현금": continue
                st.write(f"💡 **{row['자산군']}**: 목표 대비 부족합니다. 현재 환율({current_fx:,.0f}원) 기준 **{recom_type} 추가 매수**를 검토하세요.")

        # 시각화 (도넛 차트 크기 최적화)
        c1, c2 = st.columns(2)
        with c1:
            fig_is = px.pie(grp_df, values='현재비중', names='자산군', hole=0.5, title="현재 비중 (As-Is)")
            fig_is.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            st.plotly_chart(fig_is, use_container_width=True, key="bal_asis")
        with c2:
            fig_to = px.pie(grp_df, values='목표', names='자산군', hole=0.5, title="목표 비중 (To-Be)")
            fig_to.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), showlegend=False)
            st.plotly_chart(fig_to, use_container_width=True, key="bal_target")
            
        st.dataframe(get_styled_df(grp_df.sort_values('현재비중', ascending=False), ['자산군', '현재비중', '목표', '차이']), use_container_width=True, hide_index=True)

    # --- TAB 4: 환율관리 (강화 버전) ---
    with tabs[3]:
        st.subheader(f"🌎 현재 환율: {current_fx:,.2f}원")
        
        # 1. 권장 전략 크게 표시
        if current_fx > 1400:
            st.error("🔥 **고환율 구간: 환헤지(H) 비중 확대 권장 (Target 70%)**")
            t_fx = {"노출": 30, "헤지": 70}
        elif current_fx < 1330:
            st.success("❄️ **저환율 구간: 환노출 비중 확대 권장 (Target 80%)**")
            t_fx = {"노출": 80, "헤지": 20}
        else:
            st.info("⚖️ **중립 환율 구간: 노출 50 : 헤지 50 중립 전략 권장**")
            t_fx = {"노출": 50, "헤지": 50}

        # 2. 계좌 카테고리별 실시간 대응 현황
        for cat in ["세액공제 O", "세액공제 X", "ISA"]:
            if cat in asset_df['계좌카테고리'].unique():
                st.markdown(f"---")
                st.write(f"#### 🏦 {cat} 계좌 대응 상태")
                # S&P500, 나스닥 등 주요 외화 자산만 필터링
                fx_assets = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['자산군'].isin(['S&P500', '나스닥100']))].copy()
                if not fx_assets.empty:
                    fx_assets['구분'] = fx_assets['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    # 계좌 내 종목별 상세 비중 테이블
                    fx_assets['비중'] = (fx_assets['평가금액'] / fx_assets['평가금액'].sum()) * 100
                    st.dataframe(get_styled_df(fx_assets.sort_values('비중', ascending=False), ['약식종목명', '평가금액', '비중']), use_container_width=True, hide_index=True)
                else:
                    st.write("해당 계좌에 분석 가능한 외화 자산군이 없습니다.")

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
