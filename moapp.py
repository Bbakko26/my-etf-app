import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

# 1. 데이터 불러오기
def load_data():
    try:
        df = pd.read_csv('my_assets.csv', encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv('my_assets.csv', encoding='cp949', dtype={'종목코드': str})
    df['종목코드'] = df['종목코드'].str.strip()
    return df

# 모바일 최적화 스타일 설정
st.set_page_config(page_title="ETF Manager", layout="wide")
st.markdown("""
    <style>
    /* 1. 타이틀 사이즈 축소 (한 줄에 나오도록 조정) */
    h1 {
        font-size: 1.6rem !important;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }
    html, body, [class*="css"] { font-size: 14px !important; }
    .stTable td, .stTable th { font-size: 12px !important; padding: 4px !important; }
    [data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    </style>
    """, unsafe_allow_html=True)

try:
    df = load_data()
    
    # 실시간 시세 반영
    unique_codes = df['종목코드'].unique()
    current_price_map = {}
    with st.spinner('시세 반영 중...'):
        for code in unique_codes:
            price_data = fdr.DataReader(code).iloc[-1]
            current_price_map[code] = price_data['Close']

    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df['보유수량'] * df['매수평단']
    df['평가금액'] = df['보유수량'] * df['현재가']

    # --- [상단 요약] ---
    st.title("💰 통합 ETF 포트폴리오")
    
    total_buy = df['매수금액'].sum()
    total_eval = df['평가금액'].sum()
    total_profit_amt = total_eval - total_buy
    total_profit_rate = (total_profit_amt / total_buy) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수", f"{total_buy:,.0f}")
    c2.metric("총 평가", f"{total_eval:,.0f}")
    c3.metric("수익률", f"{total_profit_rate:.2f}%", f"{total_profit_amt:+,.0f}원")

    st.markdown("---")

    # --- [종목 선택] ---
    selected_stock = st.selectbox("📂 종목 선택", df['종목명'].unique())
    target_df = df[df['종목명'] == selected_stock].copy()
    target_df['수익률'] = ((target_df['평가금액'] - target_df['매수금액']) / target_df['매수금액']) * 100
    
    total_qty = target_df['보유수량'].sum()
    total_buy_amt = target_df['매수금액'].sum()
    total_eval_amt = target_df['평가금액'].sum()
    avg_price = total_buy_amt / total_qty
    stock_profit_rate = ((total_eval_amt - total_buy_amt) / total_buy_amt) * 100

    # --- [탭 구성] ---
    tab1, tab2, tab3 = st.tabs(["📊 상세 현황", "🍩 자산 비중", "🏦 전체 계좌"])

    with tab1:
        # 2. 테이블을 차트보다 먼저 배치
        st.write(f"📍 **{selected_stock} 통합 성적**")
        summary_data = pd.DataFrame([{
            '보유수량': total_qty, '평단가': avg_price, '현재가': target_df['현재가'].iloc[0], 
            '평가금액': total_eval_amt, '수익률': stock_profit_rate
        }])
        st.table(summary_data.style.format({
            '보유수량': '{:,.0f}', '평단가': '{:,.0f}', 
            '현재가': '{:,.0f}', '평가금액': '{:,.0f}', '수익률': '{:.2f}%'
        }))
        
        st.write("계좌별 내역")
        st.table(target_df[['계좌명', '보유수량', '매수평단', '평가금액', '수익률']].style.format({
            '보유수량': '{:,.0f}', '매수평단': '{:,.0f}', 
            '평가금액': '{:,.0f}', '수익률': '{:.2f}%'
        }))

        st.markdown("---")
        
        # 차트를 아래로 이동
        time_unit = st.radio("주기", ["일봉", "주봉"], horizontal=True)
        stock_history = fdr.DataReader(target_df['종목코드'].iloc[0])
        plot_data = stock_history.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}) if time_unit == "주봉" else stock_history

        fig_chart = go.Figure(data=[go.Candlestick(x=plot_data.index, open=plot_data['Open'], high=plot_data['High'], low=plot_data['Low'], close=plot_data['Close'])])
        fig_chart.add_hline(y=avg_price, line_dash="dash", line_color="red")
        fig_chart.update_layout(height=350, margin=dict(l=5, r=5, t=5, b=5), xaxis_rangeslider_visible=False)
        st.plotly_chart(fig_chart, use_container_width=True)

    with tab2:
        pie_df = df.groupby('종목명')['평가금액'].sum().reset_index()
        fig_pie = px.pie(pie_df, values='평가금액', names='종목명', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
        
        st.subheader("📊 종목별 통합 현황")
        sum_df = df.groupby(['종목명']).agg({'보유수량': 'sum', '매수금액': 'sum', '평가금액': 'sum'}).reset_index()
        price_lookup = df[['종목명', '현재가']].drop_duplicates('종목명')
        sum_df = pd.merge(sum_df, price_lookup, on='종목명')
        sum_df['평균평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['수익률'] = ((sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액']) * 100
        
        st.table(sum_df[['종목명', '보유수량', '평균평단', '현재가', '평가금액', '수익률']].style.format({
            '보유수량': '{:,.0f}', '평균평단': '{:,.0f}', '현재가': '{:,.0f}', 
            '평가금액': '{:,.0f}', '수익률': '{:.2f}%'
        }))

    with tab3:
        for acc in df['계좌명'].unique():
            acc_df = df[df['계좌명'] == acc].copy()
            acc_df['수익률'] = ((acc_df['평가금액'] - acc_df['매수금액']) / acc_df['매수금액']) * 100
            st.write(f"🏦 **{acc}**")
            st.table(acc_df[['종목명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']].style.format({
                '보유수량': '{:,.0f}', '매수평단': '{:,.0f}', '현재가': '{:,.0f}', 
                '평가금액': '{:,.0f}', '수익률': '{:.2f}%'
            }))

except Exception as e:
    st.error(f"오류: {e}")