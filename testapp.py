import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# 📍 [수정] st.set_page_config는 반드시 코드 최상단(Import 바로 아래)에 위치해야 합니다.
st.set_page_config(page_title="Family Portfolio (TEST)", layout="wide")

# 1. 데이터 불러오기 함수
def load_data():
    target_file = 'my_assets_ex.csv' # 🧪 테스트용 파일명
    try:
        df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})
    
    # 기본 전처리
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    if '자산군' not in df.columns:
        df['자산군'] = df['약식종목명'] if '약식종목명' in df.columns else df['종목명']
    if '계좌카테고리' not in df.columns:
        df['계좌카테고리'] = '미지정'
    return df

# 2. 모바일 최적화 CSS (기능 1)
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
    
    # 기능 4: SEED(원금) 행 분리
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    unique_codes = asset_df['종목코드'].unique()
    current_price_map, change_rate_map = {}, {}
    
    with st.spinner('테스트 데이터 시세 반영 중...'):
        for code in unique_codes:
            if code.upper() in ['CASH', '현금', 'NAN', '']:
                current_price_map[code], change_rate_map[code] = 1.0, 0.0
                continue
            try:
                # 기능 6: 120일 차트 데이터 확보
                price_history = fdr.DataReader(code).tail(130)
                if len(price_history) >= 2:
                    curr_p = float(price_history['Close'].iloc[-1])
                    prev_p = float(price_history['Close'].iloc[-2])
                    current_price_map[code] = curr_p
                    change_rate_map[code] = ((curr_p - prev_p) / prev_p) * 100
            except:
                current_price_map[code], change_rate_map[code] = 0.0, 0.0

    # 데이터 연산
    asset_df['현재가'] = asset_df['종목코드'].map(current_price_map)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    asset_df['수익률'] = asset_df.apply(lambda x: 0.0 if x['종목코드'].upper() == 'CASH' else ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] != 0 else 0), axis=1)

    # 기능 4: 누적 지표 계산
    total_eval = asset_df['평가금액'].sum()
    total_seed = (seed_df['보유수량'] * seed_df['매수평단']).sum() if not seed_df.empty else asset_df['매수금액'].sum()
    total_profit = total_eval - total_seed
    total_rtn = (total_profit / total_seed * 100) if total_seed != 0 else 0

    st.warning("🧪 테스트 환경 (my_assets_ex.csv) 실행 중")
    st.title("💰 Family Portfolio")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("총 투입원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{total_rtn:.2f}%", f"{total_profit:+,.0f}원")

    tab1, tab2, tab_cat, tab3 = st.tabs(["📊 상세", "🍩 비중", "🏦 분석", "💼 전체"])

    # 📍 [해결] 기능 2, 3: 문자열과 숫자가 섞여도 에러 없는 포맷팅 함수
    def safe_format(val):
        try:
            return f"{float(val):,.0f}"
        except (ValueError, TypeError):
            return val # '-' 등은 그대로 반환

    def make_display_table(target_df, cols):
        display_df = target_df.copy()
        is_cash = display_df['종목코드'].str.upper() == 'CASH'
        
        # 기능 3: 현금을 '-'로 표시하여 가독성 증대
        for col in ['보유수량', '매수평단', '현재가']:
            if col in display_df.columns:
                display_df[col] = display_df[col].astype(object)
                display_df.loc[is_cash, col] = "-"
        
        # [수정] 스크린샷의 Index 오류 방지를 위해 존재하지 않는 컬럼명 참조 제거
        rename_dict = {'약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}
        res = display_df[cols].rename(columns=rename_dict)
        
        # 기능 2: 현재가 정수화 스타일링
        return res.style.format({
            '수량': lambda x: safe_format(x),
            '평단': lambda x: safe_format(x),
            '현재가': lambda x: safe_format(x),
            '평가액': '{:,.0f}',
            '수익률': '{:.2f}%'
        })

    # --- TAB 1: 상세 현황 (기능 6 차트 포함) ---
    with tab1:
        sort_ref = asset_df.groupby('종목명')['평가금액'].sum().sort_values(ascending=False).index.tolist()
        selected_stock = st.selectbox("📂 종목 선택", sort_ref)
        target_df = asset_df[asset_df['종목명'] == selected_stock].copy()
        
        daily_chg = change_rate_map.get(target_df['종목코드'].iloc[0], 0.0)
        st.markdown(f"**{target_df['약식종목명'].iloc[0]}** <span style='color:{'#d32f2f' if daily_chg > 0 else '#1976d2'}; font-size:12px;'>({daily_chg:+.2f}%)</span>", unsafe_allow_html=True)
        
        st.dataframe(make_display_table(target_df.sort_values(by='평가금액', ascending=False), 
                                      ['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), 
                     use_container_width=True, hide_index=True)

        stock_code = target_df['종목코드'].iloc[0]
        if stock_code.upper() != 'CASH':
            try:
                stock_h = fdr.DataReader(stock_code)
                plot_data = stock_h[stock_h.index >= (datetime.now() - timedelta(days=120))]
                fig = go.Figure(data=[go.Candlestick(x=plot_data.index, open=plot_data['Open'], high=plot_data['High'], low=plot_data['Low'], close=plot_data['Close'], 
                                                     increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
                # 기능 6: 내 평단 점선 복구
                avg_p = target_df['매수금액'].sum() / target_df['보유수량'].sum() if target_df['보유수량'].sum() != 0 else 0
                fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text="내 평단")
                fig.update_layout(height=350, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            except: st.info("차트 로딩 중...")

    # --- TAB 2: 비중 (종목별) ---
    with tab2:
        sum_df = asset_df.groupby(['약식종목명', '종목코드']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['비중'] = (sum_df['평가금액'] / total_eval) * 100
        st.plotly_chart(px.pie(sum_df, values='평가금액', names='약식종목명', hole=0.4).update_traces(textinfo='percent'), use_container_width=True)
        st.dataframe(make_display_table(sum_df.sort_values(by='비중', ascending=False), ['약식종목명', '보유수량', '평가금액', '수익률']), use_container_width=True, hide_index=True)

    # --- TAB 3: 분석 (기능 5 자산군 통합) ---
    with tab_cat:
        for cat in ["세액공제 O", "세액공제 X", "ISA"]:
            if cat in asset_df['계좌카테고리'].unique():
                cat_assets = asset_df[asset_df['계좌카테고리'] == cat].copy()
                cat_seed = (seed_df[seed_df['계좌카테고리'] == cat]['보유수량'] * seed_df[seed_df['계좌카테고리'] == cat]['매수평단']).sum()
                cat_eval = cat_assets['평가금액'].sum()
                st.subheader(f"🏦 {cat} (누적: {(cat_eval-cat_seed)/cat_seed*100 if cat_seed!=0 else 0:+.2f}%)")
                
                # 기능 5: 자산군 통합 차트
                cat_group = cat_assets.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
                fig_cat = px.pie(cat_group, values='평가금액', names='자산군', hole=0.5)
                fig_cat.update_layout(height=400, showlegend=True, legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"))
                st.plotly_chart(fig_cat, use_container_width=True)
                
                cat_table = cat_assets.groupby(['약식종목명', '자산군', '종목코드']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
                cat_table['매수평단'] = cat_table['매수금액'] / cat_table['보유수량']
                cat_table['현재가'] = cat_table['종목코드'].map(current_price_map)
                cat_table['수익률'] = ((cat_table['평가금액'] - cat_table['매수금액']) / cat_table['매수금액'] * 100).fillna(0)
                st.dataframe(make_display_table(cat_table.sort_values(by='평가금액', ascending=False), 
                                              ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), 
                             use_container_width=True, hide_index=True)
                st.markdown("---")

    # --- TAB 4: 전체 계좌 (기능 4 누적수익률) ---
    with tab3:
        fixed_order = ["연금저축(키움)", "IRP(미래)", "연금저축(미래)", "경성IRP(삼성)", "중개형ISA(키움)"]
        for acc in [a for a in fixed_order if a in asset_df['계좌명'].unique()]:
            acc_assets = asset_df[asset_df['계좌명'] == acc]
            acc_seed = (seed_df[seed_df['계좌명'] == acc]['보유수량'] * seed_df[seed_df['계좌명'] == acc]['매수평단']).sum()
            st.markdown(f"### 🏦 {acc}")
            st.markdown(f"**수익률: {(acc_assets['평가금액'].sum()-acc_seed)/acc_seed*100 if acc_seed!=0 else 0:+.2f}%** (원금: {acc_seed:,.0f} / 현재: {acc_assets['평가금액'].sum():,.0f})")
            
            st.dataframe(make_display_table(acc_assets.sort_values(by='평가금액', ascending=False), 
                                          ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), 
                         use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 시스템 오류: {e}")
