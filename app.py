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

st.set_page_config(page_title="ETF 통합 관리자", layout="wide")

try:
    df = load_data()
    
    # 실시간 시세 반영
    unique_codes = df['종목코드'].unique()
    current_price_map = {}
    
    with st.spinner('실시간 시세 반영 중...'):
        for code in unique_codes:
            price_data = fdr.DataReader(code).iloc[-1]
            current_price_map[code] = price_data['Close']

    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df['보유_수량'] * df['매수평단'] if '보유_수량' in df.columns else df['보유수량'] * df['매수평단']
    df['평가금액'] = (df['보유_수량'] if '보유_수량' in df.columns else df['보유수량']) * df['현재가']

    # --- [상단 요약] ---
    st.title("💰 통합 ETF 포트폴리오")
    total_buy = df['매수금액'].sum()
    total_eval = df['평가금액'].sum()
    total_profit_rate = ((total_eval - total_buy) / total_buy) * 100

    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수금액", f"{total_buy:,.0f}원")
    c2.metric("총 평가금액", f"{total_eval:,.0f}원")
    c3.metric("전체 수익률", f"{total_profit_rate:.2f}%", f"{(total_eval - total_buy):,.0f}원")

    st.markdown("---")

    # --- [사이드바 및 탭 구성] ---
    selected_stock = st.sidebar.selectbox("상세 조회 종목", df['종목명'].unique())
    target_df = df[df['종목명'] == selected_stock].copy()
    
    # 보유수량 컬럼명 처리 (보유_수량 또는 보유수량)
    qty_col = '보유_수량' if '보유_수량' in target_df.columns else '보유수량'
    
    target_df['수익률'] = ((target_df['평가금액'] - target_df['매수금액']) / target_df['매수금액']) * 100
    
    # 통합 정보 계산
    total_qty = target_df[qty_col].sum()
    total_buy_amt = target_df['매수금액'].sum()
    total_eval_amt = target_df['평가금액'].sum()
    avg_price = total_buy_amt / total_qty
    total_profit_rate = ((total_eval_amt - total_buy_amt) / total_buy_amt) * 100
    curr_price = target_df['현재가'].iloc[0]

    tab1, tab2 = st.tabs(["📈 상세 차트", "🍩 자산 구성 및 통계"])

    with tab1:
        time_unit = st.radio("주기", ["일봉", "주봉"], horizontal=True)
        stock_history = fdr.DataReader(target_df['종목코드'].iloc[0])
        stock_history.index = pd.to_datetime(stock_history.index)

        if time_unit == "주봉":
            plot_data = stock_history.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'})
        else:
            plot_data = stock_history

        fig_chart = go.Figure(data=[go.Candlestick(
            x=plot_data.index,
            open=plot_data['Open'], high=plot_data['High'],
            low=plot_data['Low'], close=plot_data['Close'],
            name=time_unit
        )])

        fig_chart.add_hline(y=avg_price, line_dash="dash", line_color="red", 
                            annotation_text=f"통합 평단: {avg_price:,.0f}", annotation_position="top left")

        fig_chart.update_layout(height=500, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig_chart, use_container_width=True)

        # 📍 [업데이트] 상세 테이블 상단에 통합 행 추가
        st.subheader(f"🏦 {selected_stock} 상세 현황")
        
        # 통합 행 데이터 생성
        total_row = pd.DataFrame([{
            '계좌명': '⭐ 통합 (전체)',
            qty_col: total_qty,
            '매수평단': avg_price,
            '현재가': curr_price,
            '평가금액': total_eval_amt,
            '수익률': total_profit_rate
        }])
        
        # 기존 계좌별 데이터와 합치기
        display_df = pd.concat([total_row, target_df[['계좌명', qty_col, '매수평단', '현재가', '평가금액', '수익률']]], ignore_index=True)

        st.table(display_df.style.format({
            qty_col: '{:,.0f}',
            '매수평단': '{:,.0f}',
            '현재가': '{:,.0f}',
            '평가금액': '{:,.0f}',
            '수익률': '{:.2f}%'
        }))

    with tab2:
        pie_df = df.groupby('종목명')['평가금액'].sum().reset_index()
        fig_pie = px.pie(pie_df, values='평가금액', names='종목명', hole=0.5, title="종목별 자산 비중")
        fig_pie.update_traces(textinfo='percent+label')
        st.plotly_chart(fig_pie, use_container_width=True)

        st.markdown("---")
        
        st.subheader("📊 종목별 통합 요약")
        summary_df = df.groupby(['종목명', '종목코드']).agg({
            qty_col: 'sum',
            '매수금액': 'sum',
            '평가금액': 'sum'
        }).reset_index()
        
        summary_df['평균매수단가'] = summary_df['매수금액'] / summary_df[qty_col]
        summary_df['통합수익률'] = ((summary_df['평가금액'] - summary_df['매수금액']) / summary_df['매수금액']) * 100
        
        st.table(summary_df[['종목명', qty_col, '평균매수단가', '평가금액', '통합수익률']].style.format({
            qty_col: '{:,.0f}',
            '평균매수단가': '{:,.0f}',
            '평가금액': '{:,.0f}',
            '통합수익률': '{:.2f}%'
        }))

        st.markdown("---")

        st.subheader("🏦 계좌별 전체 상세 내역")
        for acc in df['계좌명'].unique():
            acc_df = df[df['계좌명'] == acc].copy()
            acc_df['수익률'] = ((acc_df['평가금액'] - acc_df['매수금액']) / acc_df['매수금액']) * 100
            
            st.write(f"📍 **{acc}**")
            st.table(acc_df[['종목명', qty_col, '매수평단', '현재가', '평가금액', '수익률']].style.format({
                qty_col: '{:,.0f}',
                '매수평단': '{:,.0f}',
                '현재가': '{:,.0f}',
                '평가금액': '{:,.0f}',
                '수익률': '{:.2f}%'
            }))

except Exception as e:
    st.error(f"오류 발생: {e}")