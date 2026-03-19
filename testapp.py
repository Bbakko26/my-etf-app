import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# 📍 [필수] 최상단 배치: 페이지 설정
st.set_page_config(page_title="Family Portfolio (CORE)", layout="wide")

# 1. 데이터 로드 및 초기 전처리
def load_data():
    target_file = 'my_assets_ex.csv' 
    try:
        df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})
    
    # 데이터 안정성 확보 (공백 제거 및 숫자 변환)
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)
    df['매수평단'] = pd.to_numeric(df['매수평단'], errors='coerce').fillna(0)
    
    # 필수 컬럼 보장
    if '자산군' not in df.columns:
        df['자산군'] = df['약식종목명'] if '약식종목명' in df.columns else df['종목명']
    if '계좌카테고리' not in df.columns:
        df['계좌카테고리'] = '미지정'
    return df

# 2. 모바일 최적화 스타일 (기능 1)
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 12px !important; }
    h1 { font-size: 1.1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.0rem !important; }
    .stDataFrame div { font-size: 11px !important; }
    .main .block-container { padding-top: 1.5rem !important; }
    .stTabs [data-baseweb="tab"] { font-size: 12px !important; padding: 10px 5px !important; }
    </style>
    """, unsafe_allow_html=True)

try:
    df_raw = load_data()
    
    # 기능 4: 원금(SEED)과 자산 분리
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # 시세 데이터 맵핑 (기능 6을 위해 130일치 확보)
    unique_codes = asset_df['종목코드'].unique()
    price_map, chg_map = {}, {}
    
    with st.spinner('실시간 시세 동기화 중...'):
        for code in unique_codes:
            if code.upper() in ['CASH', '현금', 'NAN', '']:
                price_map[code], chg_map[code] = 1.0, 0.0
                continue
            try:
                # FinanceDataReader 사용
                hist = fdr.DataReader(code).tail(130)
                if not hist.empty:
                    curr = float(hist['Close'].iloc[-1])
                    prev = float(hist['Close'].iloc[-2]) if len(hist) > 1 else curr
                    price_map[code], chg_map[code] = curr, ((curr - prev) / prev * 100)
            except: price_map[code], chg_map[code] = 0.0, 0.0

    # 자산 연산
    asset_df['현재가'] = asset_df['종목코드'].map(price_map)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    asset_df['수익률'] = asset_df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100) if x['매수금액'] != 0 else 0, axis=1)

    # 전체 대시보드 지표 (기능 4: SEED 기준)
    total_eval = asset_df['평가금액'].sum()
    total_seed = (seed_df['보유수량'] * seed_df['매수평단']).sum() if not seed_df.empty else asset_df['매수금액'].sum()
    total_profit = total_eval - total_seed

    st.warning("🧪 TEST MODE (my_assets_ex.csv)")
    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit/total_seed*100) if total_seed!=0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    tab1, tab2, tab_cat, tab3 = st.tabs(["📊 상세", "🍩 비중", "🏦 분석", "💼 전체"])

    # 📍 [기능 2, 3 해결] 안전 포맷팅 함수
    def safe_format(val):
        try:
            return f"{float(val):,.0f}"
        except (ValueError, TypeError):
            return val

    def get_styled_df(target_df, cols_to_show):
        available_cols = [c for c in cols_to_show if c in target_df.columns]
        df_view = target_df[available_cols].copy()
        
        # 기능 3: 현금을 '-'로 표시하여 가독성 증대
        if '종목코드' in target_df.columns:
            is_cash = target_df['종목코드'].str.upper() == 'CASH'
            for c in ['보유수량', '매수평단', '현재가']:
                if c in df_view.columns:
                    df_view[c] = df_view[c].astype(object)
                    df_view.loc[is_cash, c] = "-"

        # 컬럼명 매핑
        rename_map = {'약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}
        df_view = df_view.rename(columns=rename_map)
        
        # 기능 2: 현재가 정수화 스타일링
        format_rules = {'평가액': '{:,.0f}', '수익률': '{:.2f}%'}
        for c in ['수량', '평단', '현재가']:
            if c in df_view.columns:
                format_rules[c] = lambda x: safe_format(x)
        
        return df_view.style.format(format_rules)

    # --- TAB 1: 상세 (종합 현황 복구 및 기능 6 차트) ---
    with tab1:
        st.subheader("📋 종목별 종합 현황")
        # 종목별 합산
        summary_df = asset_df.groupby(['약식종목명', '종목코드', '자산군']).agg({
            '보유수량': 'sum', '매수금액': 'sum', '평가금액': 'sum'
        }).reset_index()
        summary_df['매수평단'] = summary_df['매수금액'] / summary_df['보유수량']
        summary_df['현재가'] = summary_df['종목코드'].map(price_map)
        summary_df['수익률'] = (summary_df['평가금액'] - summary_df['매수금액']) / summary_df['매수금액'] * 100
        summary_df = summary_df.fillna(0).sort_values(by='평가금액', ascending=False)
        
        st.dataframe(get_styled_df(summary_df, ['약식종목명', '자산군', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), 
                     use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🔍 종목별 상세/차트")
        sel_stock = st.selectbox("상세 확인 종목 선택", summary_df['약식종목명'].unique())
        detail_df = asset_df[asset_df['약식종목명'] == sel_stock].copy()
        st.dataframe(get_styled_df(detail_df, ['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), 
                     use_container_width=True, hide_index=True)
        
        # 기능 6: 120일 캔들스틱 차트
        code = detail_df['종목코드'].iloc[0]
        if code.upper() != 'CASH':
            try:
                hist_data = fdr.DataReader(code).tail(120)
                fig = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], 
                                                     increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
                # 내 평단 점선 표시
                avg_p = detail_df['매수금액'].sum() / detail_df['보유수량'].sum() if detail_df['보유수량'].sum() != 0 else 0
                fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text="내 평단")
                fig.update_layout(height=350, margin=dict(l=5, r=5, t=10, b=10), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            except: st.info("차트 데이터를 불러오는 중입니다...")

    # --- TAB 2: 비중 (종목별) ---
    with tab2:
        st.plotly_chart(px.pie(summary_df, values='평가금액', names='약식종목명', hole=0.4).update_traces(textinfo='percent'), use_container_width=True)

    # --- TAB 3: 분석 (기능 5 자산군 통합) ---
    with tab_cat:
        for cat in ["세액공제 O", "세액공제 X", "ISA"]:
            if cat in asset_df['계좌카테고리'].unique():
                c_assets = asset_df[asset_df['계좌카테고리'] == cat]
                # SE액공제 O 등 카테고리별 원금 합산
                c_seed = seed_df[seed_df['계좌카테고리'] == cat]['매수평단'].sum()
                c_eval = c_assets['평가금액'].sum()
                st.subheader(f"🏦 {cat}")
                st.write(f"누적 수익률: **{(c_eval-c_seed)/c_seed*100 if c_seed!=0 else 0:+.2f}%** (원금: {c_seed:,.0f})")
                
                # 기능 5: 자산군 통합 비중
                c_grp = c_assets.groupby('자산군')['평가금액'].sum().reset_index()
                st.plotly_chart(px.pie(c_grp, values='평가금액', names='자산군', hole=0.5).update_layout(height=350), use_container_width=True)
                st.markdown("---")

    # --- TAB 4: 전체 계좌 (고정 순서) ---
    with tab3:
        order = ["연금저축(키움)", "IRP(미래)", "연금저축(미래)", "경성IRP(삼성)", "중개형ISA(키움)"]
        for acc in [a for a in order if a in asset_df['계좌명'].unique()]:
            acc_data = asset_df[asset_df['계좌명'] == acc]
            acc_seed = seed_df[seed_df['계좌명'] == acc]['매수평단'].sum()
            st.markdown(f"### 🏦 {acc}")
            st.write(f"수익률: **{(acc_data['평가금액'].sum()-acc_seed)/acc_seed*100 if acc_seed!=0 else 0:+.2f}%**")
            st.dataframe(get_styled_df(acc_data, ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"🚨 시스템 코어 오류: {e}")
