import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# 1. 데이터 불러오기
def load_data():
    try:
        df = pd.read_csv('my_assets.csv', encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv('my_assets.csv', encoding='cp949', dtype={'종목코드': str})
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    if '약식종목명' not in df.columns:
        df['약식종목명'] = df['종목명']
    return df

st.set_page_config(page_title="통합 자산 관리", layout="wide")

# 📍 폰트 및 모바일 최적화 스타일 (이 부분을 교체하세요)
st.markdown("""
    <style>
    /* 전체 폰트 크기 하향 조정 */
    html, body, [class*="css"] { font-size: 12px !important; }
    
    /* 제목(Title) 크기 대폭 축소 */
    h1 { font-size: 1.2rem !important; padding-bottom: 10px !important; }
    h4 { font-size: 1.0rem !important; margin-top: 10px !important; }

    /* 메인 지표(Metric) 크기 축소 - 모바일에서 안 깨지게 */
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    [data-testid="stMetricLabel"] { font-size: 0.8rem !important; }
    [data-testid="stMetricDelta"] { font-size: 0.75rem !important; }

    /* 테이블 내 텍스트 정렬 및 크기 */
    .stDataFrame div { font-size: 11px !important; }
    
    /* 모바일에서 탭 메뉴가 잘 보이도록 간격 조정 */
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 40px; white-space: nowrap; font-size: 12px !important; }

    /* 불필요한 여백 제거 */
    .main .block-container { padding-top: 1.5rem !important; padding-bottom: 1rem !important; }
    </style>
    """, unsafe_allow_html=True)

try:
    df = load_data()
    unique_codes = df['종목코드'].unique()
    current_price_map, change_rate_map = {}, {}
    
    with st.spinner('시세 반영 중...'):
        for code in unique_codes:
            if code.upper() in ['CASH', '현금', 'NAN', '']:
                current_price_map[code], change_rate_map[code] = 1.0, 0.0
                continue
            try:
                price_history = fdr.DataReader(code).tail(2)
                if len(price_history) >= 2:
                    curr_p = price_history['Close'].iloc[-1]
                    prev_p = price_history['Close'].iloc[-2]
                    chg_r = ((curr_p - prev_p) / prev_p) * 100
                    current_price_map[code], change_rate_map[code] = curr_p, chg_r
                else:
                    current_price_map[code], change_rate_map[code] = price_history['Close'].iloc[-1], 0.0
            except:
                current_price_map[code], change_rate_map[code] = 0.0, 0.0

    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    df['평가금액'] = df['보유수량'] * df['현재가']
    df['수익률'] = df.apply(lambda x: 0.0 if x['종목코드'].upper() == 'CASH' else ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] != 0 else 0), axis=1)
    
    total_eval_sum = df['평가금액'].sum()
    total_buy = df['매수금액'].sum()
    total_profit_amt = total_eval_sum - total_buy

    # 📍 모바일 알람 텍스트 크기 조정
    alert_list = [f"{df[df['종목코드']==c]['약식종목명'].iloc[0]}({r:.1f}%)" for c, r in change_rate_map.items() if r <= -2.5]
    if alert_list:
        st.error(f"📉 급락: {', '.join(alert_list)}")

    st.title("💰 통합 자산 포트폴리오")
    
    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수", f"{total_buy:,.0f}원")
    c2.metric("총 평가", f"{total_eval_sum:,.0f}원")
    c3.metric("수익률", f"{(total_profit_amt/total_buy*100) if total_buy!=0 else 0:.2f}%", f"{total_profit_amt:+,.0f}원")

    tab1, tab2, tab_cat, tab3 = st.tabs(["📊 상세", "🍩 비중", "🏦 분석", "💼 전체"])

    def apply_cash_null(row):
        if row['종목코드'].upper() == 'CASH': return None, None, None
        return row['보유수량'], row['매수평단'], row['현재가']

    # --- 1. 상세 현황 ---
    with tab1:
        sort_ref = df.groupby('종목명')['평가금액'].sum().sort_values(ascending=False).index.tolist()
        selected_stock = st.selectbox("📂 종목 선택", sort_ref)
        target_df = df[df['종목명'] == selected_stock].copy()
        
        daily_chg = change_rate_map.get(target_df['종목코드'].iloc[0], 0.0)
        chg_color = '#d32f2f' if daily_chg > 0 else '#1976d2'
        st.markdown(f"**{target_df['약식종목명'].iloc[0]}** <span style='color:{chg_color}; font-size:12px;'>({daily_chg:+.2f}%)</span>", unsafe_allow_html=True)
        
        target_df[['표시수량', '표시평단', '표시현재가']] = target_df.apply(apply_cash_null, axis=1, result_type='expand')
        st.dataframe(target_df.sort_values(by='평가금액', ascending=False)[['계좌명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
        }, na_rep="-"), use_container_width=True, hide_index=True)

    # --- 2. 종목 비중 ---
    with tab2:
        sum_df = df.groupby(['약식종목명', '종목코드']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['비중'] = (sum_df['평가금액'] / total_eval_sum) * 100
        st.plotly_chart(px.pie(sum_df, values='평가금액', names='약식종목명', hole=0.4).update_traces(textinfo='percent'), use_container_width=True)
        
        sum_df[['표시수량', '표시평단', '표시현재가']] = sum_df.apply(lambda r: (None, None, None) if r['종목코드'] == 'CASH' else (r['보유수량'], r['매수금액']/r['보유수량'], current_price_map.get(r['종목코드'])), axis=1, result_type='expand')
        st.dataframe(sum_df.sort_values(by='비중', ascending=False)[['약식종목명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'약식종목명':'종목', '표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
        }, na_rep="-"), use_container_width=True, hide_index=True)

    # --- 3. 카테고리 분석 ---
    with tab_cat:
        cat_order = ["세액공제 O", "세액공제 X", "ISA"]
        for cat in [c for c in cat_order if c in df['계좌카테고리'].unique()]:
            cat_df = df[df['계좌카테고리'] == cat].copy()
            st.markdown(f"**📌 {cat}**")
            fig = px.pie(cat_df, values='평가금액', names='약식종목명', hole=0.5)
            fig.update_layout(showlegend=True, height=280, legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"), margin=dict(t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            cat_df[['표시수량', '표시평단', '표시현재가']] = cat_df.apply(apply_cash_null, axis=1, result_type='expand')
            st.dataframe(cat_df.sort_values(by='평가금액', ascending=False)[['계좌명', '약식종목명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'약식종목명':'종목', '표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
                '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
            }, na_rep="-"), use_container_width=True, hide_index=True)

    # --- 4. 전체 계좌 ---
    with tab3:
        fixed_order = ["연금저축(키움)", "IRP(미래)", "연금저축(미래)", "경성IRP(삼성)", "중개형ISA(키움)"]
        for acc in [a for a in fixed_order if a in df['계좌명'].unique()]:
            st.markdown(f"🏦 **{acc}**")
            acc_df = df[df['계좌명'] == acc].copy()
            acc_df[['표시수량', '표시평단', '표시현재가']] = acc_df.apply(apply_cash_null, axis=1, result_type='expand')
            st.dataframe(acc_df.sort_values(by='평가금액', ascending=False)[['약식종목명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'약식종목명':'종목', '표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
                '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
            }, na_rep="-"), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 오류: {e}")
