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
    if '계좌카테고리' not in df.columns:
        df['계좌카테고리'] = '미지정'
    return df

# 스타일 설정
st.set_page_config(page_title="통합 자산 관리 시스템", layout="wide")
st.markdown("""
    <style>
    h1 { font-size: 1.5rem !important; white-space: nowrap; }
    html, body, [class*="css"] { font-size: 13px !important; }
    .up-color { color: #d32f2f; font-weight: bold; }
    .down-color { color: #1976d2; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

try:
    df = load_data()
    
    unique_codes = df['종목코드'].unique()
    current_price_map = {}
    change_rate_map = {}
    
    with st.spinner('실시간 시세 반영 중...'):
        for code in unique_codes:
            if code == 'CASH' or code == '' or pd.isna(code):
                current_price_map[code] = 1.0
                change_rate_map[code] = 0.0
                continue
            try:
                price_history = fdr.DataReader(code).tail(2)
                if len(price_history) >= 2:
                    current_price = price_history['Close'].iloc[-1]
                    prev_price = price_history['Close'].iloc[-2]
                    change_rate = ((current_price - prev_price) / prev_price) * 100
                else:
                    current_price = price_history['Close'].iloc[-1]
                    change_rate = 0.0
                current_price_map[code] = current_price
                change_rate_map[code] = change_rate
            except:
                current_price_map[code] = 0
                change_rate_map[code] = 0

    # 금액 및 수익률 계산
    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df.apply(lambda x: x['보유수량'] if x['종목코드'] == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    df['평가금액'] = df['보유수량'] * df['현재가']
    df['수익률'] = df.apply(lambda x: 0.0 if x['종목코드'] == 'CASH' else ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] != 0 else 0), axis=1)
    
    total_eval_sum = df['평가금액'].sum()

    st.title("💰 통합 자산 포트폴리오")
    
    # 급락 알림
    alert_list = [f"**[{df[df['종목코드']==c]['약식종목명'].iloc[0]}]** ({r:.2f}%)" for c, r in change_rate_map.items() if r <= -2.5]
    if alert_list:
        st.error(f"⚠️ **급락 주의:** 현재 {' | '.join(alert_list)} 종목이 -2.5% 이상 하락 중입니다.")

    total_buy = df['매수금액'].sum()
    total_profit_amt = total_eval_sum - total_buy
    total_profit_rate = (total_profit_amt / total_buy) * 100 if total_buy != 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수", f"{total_buy:,.0f}원")
    c2.metric("총 평가", f"{total_eval_sum:,.0f}원")
    c3.metric("누적 수익률", f"{total_profit_rate:.2f}%", f"{total_profit_amt:+,.0f}원")

    st.markdown("---")
    tab1, tab2, tab_cat, tab3 = st.tabs(["📊 상세 현황", "🍩 종목 비중", "🏦 카테고리 분석", "💼 전체 계좌"])

    # --- TAB 1: 상세 현황 ---
    with tab1:
        sort_ref = df.groupby('종목명')['평가금액'].sum().sort_values(ascending=False).index.tolist()
        selected_stock = st.selectbox("📂 종목 선택", sort_ref)
        target_df = df[df['종목명'] == selected_stock].copy()
        
        daily_change = change_rate_map.get(target_df['종목코드'].iloc[0], 0.0)
        c_style = "up-color" if daily_change > 0 else "down-color" if daily_change < 0 else ""
        st.markdown(f"📍 **{target_df['약식종목명'].iloc[0]} 통합 성적** <span class='{c_style}' style='margin-left:10px;'>전일 대비 ({daily_change:+.2f}%)</span>", unsafe_allow_html=True)
        
        t_buy_sum = target_df['매수금액'].sum()
        t_eval_sum = target_df['평가금액'].sum()
        summary = pd.DataFrame([{
            '수량': target_df['보유수량'].sum(), 
            '평단': t_buy_sum / target_df['보유수량'].sum() if target_df['보유수량'].sum() != 0 else 0,
            '현재가': target_df['현재가'].iloc[0], '평가액': t_eval_sum, 
            '비중': (t_eval_sum / total_eval_sum) * 100, 
            '수익률': ((t_eval_sum - t_buy_sum) / t_buy_sum * 100) if t_buy_sum != 0 else 0
        }])
        st.dataframe(summary.style.format({'수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'}), use_container_width=True, hide_index=True)
        
        st.write("📝 계좌별 상세 내역")
        st.dataframe(target_df.sort_values(by='평가금액', ascending=False)[['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']].style.format({
            '보유수량': '{:,.0f}', '매수평단': '{:,.0f}', '현재가': '{:,.0f}', '평가금액': '{:,.0f}', '수익률': '{:.2f}%'
        }), use_container_width=True, hide_index=True)

    # --- TAB 2: 종목 비중 ---
    with tab2:
        sum_df = df.groupby(['약식종목명']).agg({'보유수량': 'sum', '매수금액': 'sum', '평가금액': 'sum'}).reset_index()
        sum_df['비중'] = (sum_df['평가금액'] / total_eval_sum) * 100
        sum_df['수익률'] = sum_df.apply(lambda x: 0.0 if x['약식종목명'] == '현금' else ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] != 0 else 0), axis=1)
        
        st.plotly_chart(px.pie(sum_df, values='평가금액', names='약식종목명', hole=0.4, title="전체 자산 비중").update_traces(textinfo='percent+label'), use_container_width=True)
        st.dataframe(sum_df.sort_values(by='비중', ascending=False).style.format({
            '보유수량': '{:,.0f}', '매수금액': '{:,.0f}', '평가금액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
        }), use_container_width=True, hide_index=True)

    # --- TAB_CAT: 카테고리 분석 ---
    with tab_cat:
        st.subheader("🏦 계좌 카테고리별 포트폴리오")
        cat_order = ["세액공제 O", "세액공제 X", "ISA"]
        actual_cats = [c for c in cat_order if c in df['계좌카테고리'].unique()] + [c for c in df['계좌카테고리'].unique() if c not in cat_order]
        
        for cat in actual_cats:
            cat_df = df[df['계좌카테고리'] == cat].copy()
            c_eval = cat_df['평가금액'].sum()
            c_buy = cat_df['매수금액'].sum()
            st.markdown(f"#### 📌 {cat} (평가: {c_eval:,.0f}원 / 수익: {((c_eval-c_buy)/c_buy*100 if c_buy !=0 else 0):+.2f}%)")
            
            l, r = st.columns([1.3, 1.7]) # 📍 도넛 차트 공간을 조금 더 확보
            with l:
                cat_sum = cat_df.groupby('약식종목명')['평가금액'].sum().reset_index()
                fig_cat = px.pie(cat_sum, values='평가금액', names='약식종목명', hole=0.5)
                # 📍 차트 사이즈 확대 및 여백 최소화
                fig_cat.update_layout(showlegend=True, height=350, margin=dict(l=10, r=10, t=30, b=10),
                                      legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5))
                st.plotly_chart(fig_cat, use_container_width=True)
            with r:
                cat_df['비중'] = (cat_df['평가금액'] / c_eval) * 100
                # 📍 테이블을 비중 순으로 정렬
                cat_df_sorted = cat_df.sort_values(by='비중', ascending=False)
                st.dataframe(cat_df_sorted[['계좌명', '약식종목명', '평가금액', '비중', '수익률']].rename(columns={'약식종목명':'종목', '평가금액':'평가액'}).style.format({
                    '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
                }), use_container_width=True, hide_index=True)
            st.markdown("---")

    # --- TAB 3: 전체 계좌 ---
    with tab3:
        for acc in df['계좌명'].unique():
            acc_df = df[df['계좌명'] == acc].copy()
            a_eval = acc_df['평가금액'].sum()
            a_buy = acc_df['매수금액'].sum()
            st.markdown(f"🏦 **{acc}** (평가액: {a_eval:,.0f}원 / 수익률: {((a_eval-a_buy)/a_buy*100 if a_buy !=0 else 0):+.2f}%)")
            
            # 📍 계좌 내 비중 계산 및 컬럼 순서 재구성
            acc_df['계좌내비중'] = (acc_df['평가금액'] / a_eval) * 100
            acc_df_sorted = acc_df.sort_values(by='계좌내비중', ascending=False)
            
            # 📍 요청하신 순서: 종목 - 수량 - 평단 - 현재가 - 평가액 - 비중 - 수익률
            display_cols = ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '계좌내비중', '수익률']
            st.dataframe(acc_df_sorted[display_cols].rename(columns={
                '약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액', '계좌내비중':'비중'
            }).style.format({
                '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
            }), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 오류 발생: {e}")
