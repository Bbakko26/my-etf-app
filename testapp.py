import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

# [필수] 최상단 설정
st.set_page_config(page_title="Family Portfolio (Pro)", layout="wide")

# 1. 데이터 로드 함수
def load_data():
    target_file = 'my_assets_ex.csv' 
    try:
        df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})
    
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)
    df['매수평단'] = pd.to_numeric(df['매수평단'], errors='coerce').fillna(0)
    
    if '자산군' not in df.columns:
        df['자산군'] = df['약식종목명']
    return df

# 스타일 설정
st.markdown("""<style>
    html, body, [class*="css"] { font-size: 12px !important; }
    h1 { font-size: 1.1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.0rem !important; }
    .stDataFrame div { font-size: 11px !important; }
    </style>""", unsafe_allow_html=True)

def safe_format(val):
    try:
        return f"{float(val):,.0f}"
    except:
        return val

def get_styled_df(target_df, cols_to_show):
    available_cols = [c for c in cols_to_show if c in target_df.columns]
    # 에러 해결: 타입을 object로 미리 변환하여 문자열(-) 삽입 허용
    df_view = target_df[available_cols].copy().astype(object)
    
    if '종목코드' in target_df.columns:
        is_cash = target_df['종목코드'].str.upper() == 'CASH'
        for c in ['보유수량', '매수평단', '현재가']:
            if c in df_view.columns:
                df_view.loc[is_cash, c] = "-"

    rename_map = {'계좌명':'계좌', '약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}
    df_view = df_view.rename(columns=rename_map)
    
    format_rules = {'평가액': '{:,.0f}', '수익률': '{:.2f}%', '비중': '{:.1f}%'}
    for col in ['수량', '평단', '현재가']:
        if col in df_view.columns:
            format_rules[col] = lambda x: safe_format(x)
            
    return df_view.style.format(format_rules)

try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    unique_codes = asset_df['종목코드'].unique()
    price_map, chg_map = {}, {}
    
    with st.spinner('실시간 시세 동기화 중...'):
        for code in unique_codes:
            if code.upper() in ['CASH', '현금', 'NAN', '']:
                price_map[code], chg_map[code] = 1.0, 0.0
                continue
            try:
                hist = fdr.DataReader(code).tail(2)
                p = float(hist['Close'].iloc[-1])
                price_map[code] = p
                chg_map[code] = ((p - hist['Close'].iloc[-2]) / hist['Close'].iloc[-2] * 100) if len(hist) > 1 else 0
            except: price_map[code], chg_map[code] = 0.0, 0.0
        
        try:
            usd_krw = fdr.DataReader('USD/KRW').tail(1)
            current_fx = float(usd_krw['Close'].iloc[-1])
        except: current_fx = 1350.0

    # 자산 연산
    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    asset_df['수익률'] = asset_df.apply(lambda x: ((x['평가금액'] - x['매수금액']) / x['매수금액'] * 100) if x['매수금액'] > 0 else 0, axis=1)
    
    total_eval = asset_df['평가금액'].sum()
    total_seed = (seed_df['보유수량'] * seed_df['매수평단']).sum()
    total_profit = total_eval - total_seed

    st.title("💰 Family Portfolio")
    c1, c2, c3 = st.columns(3)
    c1.metric("총 원금", f"{total_seed:,.0f}원")
    c2.metric("현재 자산", f"{total_eval:,.0f}원")
    c3.metric("누적 수익", f"{(total_profit/total_seed*100) if total_seed > 0 else 0:.2f}%", f"{total_profit:+,.0f}원")

    tabs = st.tabs(["📊 상세", "🍩 비중", "🏦 분석", "💼 전체", "🌎 환율관리"])

    # --- TAB 1: 상세 ---
    with tabs[0]:
        st.subheader("📋 종목별 종합 현황")
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['매수평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['수익률'] = sum_df.apply(lambda x: (x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] > 0 else 0, axis=1)
        
        st.dataframe(get_styled_df(sum_df.sort_values('평가금액', ascending=False), 
                     ['약식종목명', '자산군', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)
        
        st.divider()
        st.subheader("🔍 종목별 상세/차트")
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[(asset_df['종목명'] == sel_name) & (asset_df['보유수량'] > 0)].copy()
        st.dataframe(get_styled_df(detail_df, ['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)
        
        if not detail_df.empty:
            code = detail_df['종목코드'].iloc[0]
            if code != "CASH":
                try:
                    hist_data = fdr.DataReader(code).tail(120)
                    fig = go.Figure(data=[go.Candlestick(x=hist_data.index, open=hist_data['Open'], high=hist_data['High'], low=hist_data['Low'], close=hist_data['Close'], increasing_line_color='#d32f2f', decreasing_line_color='#1976d2')])
                    avg_p = detail_df['매수금액'].sum() / detail_df['보유수량'].sum() if detail_df['보유수량'].sum() > 0 else 0
                    if avg_p > 0:
                        fig.add_hline(y=avg_p, line_dash="dash", line_color="red", annotation_text=f"내 평단: {avg_p:,.0f}", annotation_position="top left")
                    fig.update_layout(height=400, margin=dict(l=10, r=10, t=30, b=10), xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True, key="detail_candle_chart")
                except: st.info("차트 데이터를 불러올 수 없습니다.")

    # --- TAB 2: 비중 (자산군) ---
    with tabs[1]:
        st.subheader("🍩 자산군별 비중")
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum', '매수금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['수익률'] = grp_df.apply(lambda x: (x['평가금액'] - x['매수금액']) / x['매수금액'] * 100 if x['매수금액'] > 0 else 0, axis=1)
        st.plotly_chart(px.pie(grp_df, values='평가금액', names='자산군', hole=0.4), use_container_width=True, key="main_asset_pie")
        st.dataframe(get_styled_df(grp_df.sort_values('비중', ascending=False), ['자산군', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)

    # --- TAB 3: 분석 (📍 계좌명 추가 및 비중 정렬) ---
    with tabs[2]:
        for cat in ["세액공제 O", "세액공제 X", "ISA"]:
            if cat in asset_df['계좌카테고리'].unique():
                c_assets = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['보유수량'] > 0)].copy()
                st.subheader(f"🏦 {cat}")
                st.plotly_chart(px.pie(c_assets.groupby('자산군')['평가금액'].sum().reset_index(), values='평가금액', names='자산군', hole=0.5), use_container_width=True, key=f"pie_{cat}")
                
                c_assets['비중'] = (c_assets['평가금액'] / c_assets['평가금액'].sum()) * 100 if c_assets['평가금액'].sum() > 0 else 0
                # 📍 요구사항: 계좌명 컬럼 추가 및 비중 내림차순 정렬
                st.dataframe(get_styled_df(c_assets.sort_values('비중', ascending=False), 
                             ['계좌명', '약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)
                st.markdown("---")

    # --- TAB 4: 전체 (📍 비중 정렬) ---
    with tabs[3]:
        acc_order = ["연금저축(키움)", "IRP(미래)", "연금저축(미래)", "경성IRP(삼성)", "중개형ISA(키움)"]
        for acc in [a for a in acc_order if a in asset_df['계좌명'].unique()]:
            a_assets = asset_df[(asset_df['계좌명'] == acc) & (asset_df['보유수량'] > 0)].copy()
            st.markdown(f"### 🏦 {acc}")
            
            a_assets['비중'] = (a_assets['평가금액'] / a_assets['평가금액'].sum()) * 100 if a_assets['평가금액'].sum() > 0 else 0
            # 📍 요구사항: 비중 내림차순 정렬
            st.dataframe(get_styled_df(a_assets.sort_values('비중', ascending=False), 
                         ['약식종목명', '보유수량', '매수평단', '현재가', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)

    # --- TAB 5: 환율 관리 ---
    with tabs[4]:
        st.subheader("💱 실시간 환율 정보")
        st.metric("원/달러 환율", f"{current_fx:,.2f}원")
        
        if current_fx < 1330:
            advice, t_ratio = "환율 저점: **환노출 비중 80% 이상** 추천", {"노출": 80, "헤지": 20}
        elif current_fx > 1400:
            advice, t_ratio = "환율 고점: **환헤지 비중 70% 이상** 추천", {"노출": 30, "헤지": 70}
        else:
            advice, t_ratio = "중립 구간: **환노출 50 : 환헤지 50** 추천", {"노출": 50, "헤지": 50}
        st.info(advice)

        st.subheader("📊 주요 자산군 환율 대응 현황")
        for tg in ["S&P500", "나스닥100"]:
            fx_sub = asset_df[(asset_df['자산군'] == tg) & (asset_df['계좌카테고리'].isin(["세액공제 O", "세액공제 X"])) & (asset_df['보유수량'] > 0)].copy()
            if not fx_sub.empty:
                fx_sub['구분'] = fx_sub['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x or '헤지' in x else '환노출')
                fx_grp = fx_sub.groupby('구분')['평가금액'].sum().reset_index()
                
                cl1, cl2 = st.columns(2)
                with cl1:
                    st.write(f"**현재 {tg} 비율**")
                    st.plotly_chart(px.pie(fx_grp, values='평가금액', names='구분', hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}), use_container_width=True, key=f"curr_fx_pie_{tg}")
                with cl2:
                    st.write(f"**권장 {tg} 비율**")
                    rec_df = pd.DataFrame([{"구분":"환노출", "비율":t_ratio['노출']}, {"구분":"환헤지", "비율":t_ratio['헤지']}])
                    st.plotly_chart(px.pie(rec_df, values='비율', names='구분', hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}), use_container_width=True, key=f"rec_fx_pie_{tg}")

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
