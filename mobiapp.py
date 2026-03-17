import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# 1. 데이터 로드 및 전처리
def load_data():
    try:
        df = pd.read_csv('my_assets.csv', encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv('my_assets.csv', encoding='cp949', dtype={'종목코드': str})
    
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    if '약식종목명' not in df.columns:
        df['약식종목명'] = df['종목명']
    return df

st.set_page_config(page_title="통합 자산 관리 시스템", layout="wide")

try:
    df = load_data()
    unique_codes = df['종목코드'].unique()
    current_price_map, change_rate_map = {}, {}
    
    # 2. 실시간 시세 반영 (현금은 API 제외)
    with st.spinner('실시간 시세 반영 중...'):
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

    # 3. 데이터 계산 루틴 (수익률 계산 오류 방지용)
    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    df['평가금액'] = df['보유수량'] * df['현재가']
    df['수익률'] = df.apply(lambda x: 0.0 if x['종목코드'].upper() == 'CASH' else ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] != 0 else 0), axis=1)
    
    total_eval_sum = df['평가금액'].sum()
    total_buy = df['매수금액'].sum()
    total_profit_amt = total_eval_sum - total_buy

    # 4. 상단 대시보드 및 급락 알림
    st.title("💰 통합 자산 포트폴리오")
    
    # 📍 전일 대비 -2.5% 이상 하락 알람 복구
    alert_list = [f"**[{df[df['종목코드']==c]['약식종목명'].iloc[0]}]** ({r:.2f}%)" for c, r in change_rate_map.items() if r <= -2.5]
    if alert_list:
        st.error(f"⚠️ **급락 주의:** 현재 {' | '.join(alert_list)} 종목이 -2.5% 이상 하락 중입니다.")

    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수금액", f"{total_buy:,.0f}원")
    c2.metric("총 평가금액", f"{total_eval_sum:,.0f}원")
    # 📍 수익 금액(원) 복구
    c3.metric("누적 수익률", f"{(total_profit_amt/total_buy*100) if total_buy!=0 else 0:.2f}%", f"{total_profit_amt:+,.0f}원")

    tab1, tab2, tab_cat, tab3 = st.tabs(["📊 상세 현황", "🍩 종목 비중", "🏦 카테고리 분석", "💼 전체 계좌"])

    # 📍 현금 행 시각적 Null 처리 함수
    def apply_cash_null(row):
        if row['종목코드'].upper() == 'CASH':
            return None, None, None
        return row['보유수량'], row['매수평단'], row['현재가']

    # --- 1. 상세 현황 ---
    with tab1:
        sort_ref = df.groupby('종목명')['평가금액'].sum().sort_values(ascending=False).index.tolist()
        selected_stock = st.selectbox("📂 종목 선택", sort_ref)
        target_df = df[df['종목명'] == selected_stock].copy()
        
        # 종목별 통합 성적 및 전일 대비 등락
        daily_chg = change_rate_map.get(target_df['종목코드'].iloc[0], 0.0)
        st.markdown(f"📍 **{target_df['약식종목명'].iloc[0]} 통합 성적** <span style='color:{'#d32f2f' if daily_chg > 0 else '#1976d2'}; font-size:14px; margin-left:10px;'>전일 대비 ({daily_chg:+.2f}%)</span>", unsafe_allow_html=True)
        
        t_qty, t_buy, t_eval = target_df['보유수량'].sum(), target_df['매수금액'].sum(), target_df['평가금액'].sum()
        is_cash = target_df['종목코드'].iloc[0] == 'CASH'
        
        sum_row = pd.DataFrame([{'수량': t_qty if not is_cash else None, '평단': t_buy/t_qty if t_qty!=0 and not is_cash else None, '현재가': target_df['현재가'].iloc[0] if not is_cash else None, '평가액': t_eval, '수익률': (t_eval-t_buy)/t_buy*100 if t_buy!=0 else 0}])
        st.dataframe(sum_row.style.format({'수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'}, na_rep="-"), use_container_width=True, hide_index=True)

        st.write("📝 계좌별 내역")
        target_df[['표시수량', '표시평단', '표시현재가']] = target_df.apply(apply_cash_null, axis=1, result_type='expand')
        st.dataframe(target_df.sort_values(by='평가금액', ascending=False)[['계좌명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
        }, na_rep="-"), use_container_width=True, hide_index=True)

    # --- 2. 종목 비중 ---
    with tab2:
        sum_df = df.groupby(['약식종목명', '종목코드']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['비중'] = (sum_df['평가금액'] / total_eval_sum) * 100
        sum_df['수익률'] = ((sum_df['평가금액']-sum_df['매수금액'])/sum_df['매수금액']*100).fillna(0)
        st.plotly_chart(px.pie(sum_df, values='평가금액', names='약식종목명', hole=0.4).update_traces(textinfo='percent+label'), use_container_width=True)
        
        sum_df[['표시수량', '표시평단', '표시현재가']] = sum_df.apply(lambda r: (None, None, None) if r['종목코드'] == 'CASH' else (r['보유수량'], r['매수금액']/r['보유수량'], current_price_map.get(r['종목코드'])), axis=1, result_type='expand')
        st.dataframe(sum_df.sort_values(by='비중', ascending=False)[['약식종목명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'약식종목명':'종목', '표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
        }, na_rep="-"), use_container_width=True, hide_index=True)

    # --- 3. 카테고리 분석 ---
    with tab_cat:
        cat_order = ["세액공제 O", "세액공제 X", "ISA"]
        for cat in [c for c in cat_order if c in df['계좌카테고리'].unique()]:
            cat_df = df[df['계좌카테고리'] == cat].copy()
            st.markdown(f"#### 📌 {cat}")
            l, r = st.columns([1.3, 1.7])
            with l:
                fig = px.pie(cat_df, values='평가금액', names='약식종목명', hole=0.5)
                fig.update_layout(showlegend=True, height=350, legend=dict(orientation="h", yanchor="top", y=-0.1, xanchor="center", x=0.5))
                st.plotly_chart(fig, use_container_width=True)
            with r:
                cat_df[['표시수량', '표시평단', '표시현재가']] = cat_df.apply(apply_cash_null, axis=1, result_type='expand')
                st.dataframe(cat_df.sort_values(by='평가금액', ascending=False)[['계좌명', '약식종목명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'약식종목명':'종목', '표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
                    '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
                }, na_rep="-"), use_container_width=True, hide_index=True)

    # --- 4. 전체 계좌 ---
    with tab3:
        # 📍 계좌 출력 순서 고정
        fixed_order = ["연금저축(키움)", "IRP(미래)", "연금저축(미래)", "경성IRP(삼성)", "중개형ISA(키움)"]
        for acc in [a for a in fixed_order if a in df['계좌명'].unique()]:
            acc_df = df[df['계좌명'] == acc].copy()
            st.markdown(f"🏦 **{acc}**")
            acc_df[['표시수량', '표시평단', '표시현재가']] = acc_df.apply(apply_cash_null, axis=1, result_type='expand')
            st.dataframe(acc_df.sort_values(by='평가금액', ascending=False)[['약식종목명', '표시수량', '표시평단', '표시현재가', '평가금액', '수익률']].rename(columns={'약식종목명':'종목', '표시수량':'수량', '표시평단':'평단', '표시현재가':'현재가', '평가금액':'평가액'}).style.format({
                '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
            }, na_rep="-"), use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 오류 발생: {e}")