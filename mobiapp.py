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

st.set_page_config(page_title="통합 자산 관리", layout="wide")

# 모바일 최적화 CSS
st.markdown("""
    <style>
    html, body, [class*="css"] { font-size: 12px !important; }
    h1 { font-size: 1.2rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
    .stDataFrame div { font-size: 11px !important; }
    .main .block-container { padding-top: 1.5rem !important; }
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
                price_history = fdr.DataReader(code).tail(130)
                if len(price_history) >= 2:
                    curr_p = float(price_history['Close'].iloc[-1])
                    prev_p = float(price_history['Close'].iloc[-2])
                    chg_r = ((curr_p - prev_p) / prev_p) * 100
                    current_price_map[code], change_rate_map[code] = curr_p, chg_r
            except:
                current_price_map[code], change_rate_map[code] = 0.0, 0.0

    # 자산 계산
    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    df['평가금액'] = df['보유수량'] * df['현재가']
    df['수익률'] = df.apply(lambda x: 0.0 if x['종목코드'].upper() == 'CASH' else ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] != 0 else 0), axis=1)
    
    total_eval_sum = df['평가금액'].sum()
    total_buy = df['매수금액'].sum()
    total_profit_amt = total_eval_sum - total_buy

    # 급락 알림
    alert_list = [f"{df[df['종목코드']==c]['약식종목명'].iloc[0]}({r:.1f}%)" for c, r in change_rate_map.items() if r <= -2.5]
    if alert_list:
        st.error(f"📉 급락: {', '.join(alert_list)}")

    st.title("💰 통합 자산 포트폴리오")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수", f"{total_buy:,.0f}원")
    c2.metric("총 평가", f"{total_eval_sum:,.0f}원")
    c3.metric("수익률", f"{(total_profit_amt/total_buy*100) if total_buy!=0 else 0:.2f}%", f"{total_profit_amt:+,.0f}원")

    tab1, tab2, tab_cat, tab3 = st.tabs(["📊종목상세", "🍩전체비중", "🏦카테고리 분석", "💼 계좌별 비중"])

    # 안전한 포맷팅 함수
    def safe_format(val, fmt="{:,.0f}"):
        try: return fmt.format(val)
        except: return val

    def make_display_table(target_df, cols):
        display_df = target_df.copy()
        is_cash = display_df['종목코드'].str.upper() == 'CASH'
        for col in ['보유수량', '매수평단', '현재가']:
            if col in display_df.columns:
                display_df[col] = display_df[col].astype(object)
                display_df.loc[is_cash, col] = "-"
        rename_dict = {'약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}
        res = display_df[cols].rename(columns=rename_dict)
        return res.style.format({
            '수량': lambda x: safe_format(x),
            '평단': lambda x: safe_format(x),
            '현재가': lambda x: safe_format(x),
            '평가액': '{:,.0f}',
            '수익률': '{:.2f}%'
        })

    # --- 1. 상세 현황 ---
    with tab1:
        sort_ref = df.groupby('종목명')['평가금액'].sum().sort_values(ascending=False).index.tolist()
        selected_stock = st.selectbox("📂 종목 선택", sort_ref)
        target_df = df[df['종목명'] == selected_stock].copy()
        daily_chg = change_rate_map.get(target_df['종목코드'].iloc[0], 0.0)
        st.markdown(f"**{target_df['약식종목명'].iloc[0]}** <span style='color:{'#d32f2f' if daily_chg > 0 else '#1976d2'}; font-size:12px;'>({daily_chg:+.2f}%)</span>", unsafe_allow_html=True)
        disp_tab1 = make_display_table(target_df.sort_values(by='평가금액', ascending=False), ['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률'])
        st.dataframe(disp_tab1, use_container_width=True, hide_index=True)

        stock_code = target_df['종목코드'].iloc[0]
        if stock_code.upper() != 'CASH':
            try:
                stock_h = fdr.DataReader(stock_code)
                plot_data = stock_h[stock_h.index >= (datetime.now() - timedelta(days=120))]
                fig = go.Figure(data=[go.Candlestick(x=plot_data.index, open=plot_data['Open'], high=plot_data['High'], low=plot_data['Low'], close=plot_data['Close'], increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
                avg_p = target_df['매수금액'].sum() / target_df['보유수량'].sum() if target_df['보유수량'].sum() != 0 else 0
                fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text="내 평단")
                fig.update_layout(height=400, margin=dict(l=10, r=10, t=10, b=10), xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
            except: st.warning("⚠️ 차트 실패")
        else: st.info("💡 현금 차트 미제공")

    # --- 2. 종목 비중 ---
    with tab2:
        sum_df = df.groupby(['약식종목명', '종목코드']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['매수평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['현재가'] = sum_df['종목코드'].map(current_price_map)
        sum_df['수익률'] = ((sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액'] * 100).fillna(0)
        sum_df['비중'] = (sum_df['평가금액'] / total_eval_sum) * 100
        
        st.plotly_chart(px.pie(sum_df, values='평가금액', names='약식종목명', hole=0.4).update_traces(textinfo='percent'), use_container_width=True)
        disp_tab2 = make_display_table(sum_df.sort_values(by='비중', ascending=False), ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률'])
        st.dataframe(disp_tab2, use_container_width=True, hide_index=True)

    # --- 3. 카테고리 분석 (📍 차트 크기 조정됨) ---
    with tab_cat:
        cat_order = ["세액공제 O", "세액공제 X", "ISA"]
        for cat in [c for c in cat_order if c in df['계좌카테고리'].unique()]:
            cat_df = df[df['계좌카테고리'] == cat].copy()
            st.markdown(f"**📌 {cat}**")
            
            cat_sum = cat_df.groupby(['약식종목명', '종목코드']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
            cat_sum['매수평단'] = cat_sum['매수금액'] / cat_sum['보유수량']
            cat_sum['현재가'] = cat_sum['종목코드'].map(current_price_map)
            cat_sum['수익률'] = ((cat_sum['평가금액'] - cat_sum['매수금액']) / cat_sum['매수금액'] * 100).fillna(0)
            
            # 📍 차트 높이를 400으로 키우고 범례 위치 조정
            fig_p = px.pie(cat_sum, values='평가금액', names='약식종목명', hole=0.5)
            fig_p.update_layout(
                showlegend=True, 
                height=350, # 📍 높이 확대
                legend=dict(orientation="h", y=-0.1, x=0.5, xanchor="center"),
                margin=dict(l=10, r=10, t=30, b=50) # 📍 여백 조정
            )
            st.plotly_chart(fig_p, use_container_width=True)
            
            disp_tab_cat = make_display_table(cat_sum.sort_values(by='평가금액', ascending=False), 
                                             ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률'])
            st.dataframe(disp_tab_cat, use_container_width=True, hide_index=True)
            st.markdown("---")

    # --- 4. 전체 계좌 ---
    with tab3:
        fixed_order = ["연금저축(키움)", "IRP(미래)", "연금저축(미래)", "경성IRP(삼성)", "중개형ISA(키움)"]
        for acc in [a for a in fixed_order if a in df['계좌명'].unique()]:
            st.markdown(f"🏦 **{acc}**")
            acc_df = df[df['계좌명'] == acc].copy()
            disp_tab3 = make_display_table(acc_df.sort_values(by='평가금액', ascending=False), ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률'])
            st.dataframe(disp_tab3, use_container_width=True, hide_index=True)

except Exception as e:
    st.error(f"⚠️ 오류 발생: {e}")
