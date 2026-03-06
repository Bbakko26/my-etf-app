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
    if '약식종목명' not in df.columns:
        df['약식종목명'] = df['종목명']
    if '계좌카테고리' not in df.columns:
        df['계좌카테고리'] = '미지정'
    return df

# 스타일 설정
st.set_page_config(page_title="ETF Manager Pro", layout="wide")
st.markdown("""
    <style>
    h1 { font-size: 1.5rem !important; white-space: nowrap; }
    html, body, [class*="css"] { font-size: 13px !important; }
    .stTable td, .stTable th { font-size: 11px !important; padding: 3px !important; }
    [data-testid="stMetricValue"] { font-size: 1.25rem !important; }
    .footnote-item { font-size: 11px; color: #666; margin-bottom: 2px; line-height: 1.4; }
    .up-color { color: #d32f2f; font-weight: bold; }
    .down-color { color: #1976d2; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

try:
    df = load_data()
    
    unique_codes = df['종목코드'].unique()
    current_price_map = {}
    change_rate_map = {}
    
    with st.spinner('시세 반영 중...'):
        for code in unique_codes:
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

    df['현재가'] = df['종목코드'].map(current_price_map)
    df['매수금액'] = df['보유수량'] * df['매수평단']
    df['평가금액'] = df['보유수량'] * df['현재가']
    total_eval_sum = df['평가금액'].sum()

    # 상단 요약
    st.title("💰 통합 ETF 포트폴리오")
    # ---------------------------------------------------------
    # 🚨 [신규] 전일 대비 -2.5% 이상 하락 알람 로직
    # ---------------------------------------------------------
    alert_list = []
    for code, change in change_rate_map.items():
        if change <= -2.5:
            # 해당 코드를 가진 종목명(약식) 가져오기
            stock_name = df[df['종목코드'] == code]['약식종목명'].iloc[0]
            alert_list.append(f"**[{stock_name}]** ({change:.2f}%)")
    
    if alert_list:
        alert_msg = " | ".join(alert_list)
        st.error(f"⚠️ **급락 주의:** 현재 {alert_msg} 종목이 전일 대비 -2.5% 이상 하락 중입니다.")
    # ---------------------------------------------------------

    total_buy = df['매수금액'].sum()
    total_profit_amt = total_eval_sum - total_buy
    total_profit_rate = (total_profit_amt / total_buy) * 100 if total_buy != 0 else 0

    c1, c2, c3 = st.columns(3)
    c1.metric("총 매수", f"{total_buy:,.0f}")
    c2.metric("총 평가", f"{total_eval_sum:,.0f}")
    c3.metric("수익률", f"{total_profit_rate:.2f}%", f"{total_profit_amt:+,.0f}원")

    st.markdown("---")
    name_map = df.drop_duplicates('종목명').set_index('종목명')['약식종목명'].to_dict()
    tab1, tab2, tab_cat, tab3 = st.tabs(["📊 상세 현황", "🍩 종목 비중", "🏦 카테고리 분석", "💼 전체 계좌"])

    with tab1:
        sort_ref = df.groupby('종목명')['평가금액'].sum().sort_values(ascending=False).index.tolist()
        selected_stock = st.selectbox("📂 종목 선택", sort_ref)
        
        target_df = df[df['종목명'] == selected_stock].copy()
        target_df['수익률'] = ((target_df['평가금액'] - target_df['매수금액']) / target_df['매수금액']) * 100
        
        total_qty = target_df['보유수량'].sum()
        total_buy_amt = target_df['매수금액'].sum()
        total_eval_amt = target_df['평가금액'].sum()
        avg_price = total_buy_amt / total_qty
        stock_profit_rate = ((total_eval_amt - total_buy_amt) / total_buy_amt) * 100
        stock_weight = (total_eval_amt / total_eval_sum) * 100
        
        # 📍 전일 대비 등락 계산 및 스타일 적용
        daily_change = change_rate_map.get(target_df['종목코드'].iloc[0], 0.0)
        change_style = "up-color" if daily_change > 0 else "down-color" if daily_change < 0 else ""
        change_sign = "+" if daily_change > 0 else ""

        # 📍 제목 옆에 전일 대비 등락 표시 추가
        st.markdown(f"""
            📍 **{name_map.get(selected_stock)} 통합 성적** <span class='{change_style}' style='margin-left:10px; font-size: 14px;'>
                전일 대비 ({change_sign}{daily_change:.2f}%)
            </span>
        """, unsafe_allow_html=True)
        
        # 통합 성적 테이블 (수익률 소수점 둘째자리 유지)
        summary_data = pd.DataFrame([{
            '수량': total_qty, '평단': avg_price, '현재가': target_df['현재가'].iloc[0], 
            '평가액': total_eval_amt, '비중': stock_weight, '수익률': stock_profit_rate
        }])
        st.table(summary_data.style.hide(axis='index').format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', 
            '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
        }))
        
        st.write("📝 계좌별 내역")
        acc_detail = target_df.sort_values(by='평가금액', ascending=False)
        st.table(acc_detail[['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']].rename(columns={'보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}).style.hide(axis='index').format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '수익률': '{:.2f}%'
        }))

        # 차트
       # --- 캔들스틱 차트 (최근 3개월 설정 추가) ---
        st.markdown("---")
        from datetime import datetime, timedelta
        
        # 1. 주기 선택 (기존 로직)
        time_unit = st.radio("주기", ["일봉", "주봉"], horizontal=True, key="chart_unit")
        
        # 2. 데이터 가져오기 및 전처리
        stock_history = fdr.DataReader(target_df['종목코드'].iloc[0])
        
        # 3. [추가] 최근 3개월 날짜 계산 및 필터링
        four_months_ago = datetime.now() - timedelta(days=120)
        # 데이터가 3개월보다 적을 경우를 대비해 슬라이싱 처리
        plot_data_full = stock_history.resample('W').agg({'Open':'first', 'High':'max', 'Low':'min', 'Close':'last'}) if time_unit == "주봉" else stock_history
        
        # 초기 표시 범위를 위한 4개월 데이터 추출
        plot_data_4m = plot_data_full[plot_data_full.index >= four_months_ago]
        
        # 만약 4개월치 데이터가 너무 적다면 전체 데이터를 사용
        if len(plot_data_4m) < 5:
            display_data = plot_data_full
        else:
            display_data = plot_data_4m

        # 4. 차트 생성
        fig_chart = go.Figure(data=[go.Candlestick(
            x=display_data.index,
            open=display_data['Open'],
            high=display_data['High'],
            low=display_data['Low'],
            close=display_data['Close'],
            increasing_line_color='#d32f2f', # 상승 (Red)
            decreasing_line_color='#1976d2'  # 하락 (Blue)
        )])
        
        # 내 평단선 표시
        fig_chart.add_hline(y=avg_price, line_dash="dash", line_color="#FF5722", line_width=2, 
                    annotation_text=f"내 평단: {avg_price:,.0f}", annotation_position="top left")
        
        # 레이아웃 설정
        fig_chart.update_layout(
            height=450,
            template="plotly_white", # 깔끔한 흰색 배경 템플릿
            margin=dict(l=10, r=10, t=30, b=10),
            xaxis_rangeslider_visible=False,
            # 그리드 스타일 및 날짜 형식
            xaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.3)', tickformat='%y-%m-%d'),
            yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.3)', side='right'), # 가격축을 오른쪽으로
            showlegend=False
        )
        
        st.plotly_chart(fig_chart, use_container_width=True)
    with tab2:
        sum_df = df.groupby(['약식종목명']).agg({'보유수량': 'sum', '매수금액': 'sum', '평가금액': 'sum'}).reset_index()
        sum_df['평균평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['비중'] = (sum_df['평가금액'] / total_eval_sum) * 100
        sum_df['수익률'] = ((sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액']) * 100
        price_lookup = df[['약식종목명', '현재가']].drop_duplicates('약식종목명')
        sum_df = pd.merge(sum_df, price_lookup, on='약식종목명').sort_values(by='비중', ascending=False)

        fig_pie = px.pie(sum_df, values='평가금액', names='약식종목명', hole=0.4, title="종목별 자산 비중")
        st.plotly_chart(fig_pie, use_container_width=True)
        st.table(sum_df[['약식종목명', '보유수량', '평균평단', '현재가', '평가금액', '비중', '수익률']].rename(columns={'약식종목명':'종목', '보유수량':'수량', '평균평단':'평단', '평가금액':'평가액'}).style.hide(axis='index').format({
            '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
        }))

    with tab_cat:
        st.subheader("🏦 계좌 카테고리별 포트폴리오")
        for cat in df['계좌카테고리'].unique():
            cat_df = df[df['계좌카테고리'] == cat].copy()
            cat_total_eval = cat_df['평가금액'].sum()
            cat_total_buy = cat_df['매수금액'].sum()
            cat_profit_rate = ((cat_total_eval - cat_total_buy) / cat_total_buy) * 100 if cat_total_buy != 0 else 0
            
            st.markdown(f"#### 📌 {cat} (평가: {cat_total_eval:,.0f}원 / 수익: {cat_profit_rate:+.2f}%)")
            
            # 1. 컬럼 비율 조정 (기존 [1, 2] -> [1.2, 1.8]로 차트 공간 확보)
            c_left, c_right = st.columns([1.2, 1.8]) 
            
            with c_left:
                cat_sum = cat_df.groupby('약식종목명')['평가금액'].sum().reset_index()
                
                # 2. 도넛 차트 생성 및 속성 변경
                fig_cat = px.pie(cat_sum, values='평가금액', names='약식종목명', hole=0.5)
                
                # 3. 상세 레이아웃 조정 (높이를 200 -> 350으로 대폭 확대, 마진 제거)
                fig_cat.update_layout(
                    showlegend=True,          # 차트가 커지므로 범례를 다시 표시해도 좋습니다
                    legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5), # 범례 하단 배치
                    height=350,               # 높이 확대
                    margin=dict(l=10, r=10, t=10, b=10) # 여백 최소화로 꽉 차게 표시
                )
                
                # 4. 차트 내부 텍스트 스타일 (선택 사항)
                fig_cat.update_traces(textposition='inside', textinfo='percent+label')
                
                st.plotly_chart(fig_cat, use_container_width=True)
                
            with c_right:
                cat_df['비중'] = (cat_df['평가금액'] / cat_total_eval) * 100
                cat_df['수익률'] = ((cat_df['평가금액'] - cat_df['매수금액']) / cat_df['매수금액']) * 100
                
                # 테이블 높이를 차트와 맞추기 위해 상단 여백 약간 추가 가능
                st.table(cat_df[['계좌명', '약식종목명', '평가금액', '비중', '수익률']].rename(
                    columns={'약식종목명':'종목', '평가금액':'평가액'}
                ).style.hide(axis='index').format({
                    '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
                }))
            st.markdown("---")

    with tab3:
        for acc in df['계좌명'].unique():
            acc_df = df[df['계좌명'] == acc].copy()
            acc_total_eval = acc_df['평가금액'].sum()
            acc_total_buy = acc_df['매수금액'].sum()
            acc_total_profit_rate = ((acc_total_eval - acc_total_buy) / acc_total_buy) * 100 if acc_total_buy != 0 else 0
            acc_df['계좌내비중'] = (acc_df['평가금액'] / acc_total_eval) * 100
            acc_df['수익률'] = ((acc_df['평가금액'] - acc_df['매수금액']) / acc_df['매수금액']) * 100
            
            st.markdown(f"🏦 **{acc}** (평가액: {acc_total_eval:,.0f}원 / 수익률: {acc_total_profit_rate:+.2f}%)")
            st.table(acc_df[['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '계좌내비중', '수익률']].rename(columns={'약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액', '계좌내비중':'비중'}).style.hide(axis='index').format({
                '수량': '{:,.0f}', '평단': '{:,.0f}', '현재가': '{:,.0f}', '평가액': '{:,.0f}', '비중': '{:.1f}%', '수익률': '{:.2f}%'
            }))

    st.markdown("---")
    st.markdown("**[참고: 종목 명칭 정보]**")
    for short_name, full_name in name_map.items():
        st.markdown(f"<div class='footnote-item'>• {short_name} : {full_name}</div>", unsafe_allow_html=True)

except Exception as e:
    st.error(f"⚠️ 오류 발생: {e}")
