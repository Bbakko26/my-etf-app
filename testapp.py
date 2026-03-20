import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

# [필수] 최상단 설정
st.set_page_config(page_title="Family Portfolio", layout="wide")

# 1. 데이터 로드 함수
def load_data():
    target_file = 'my_assets.csv' 
    try:
        df = pd.read_csv(target_file, encoding='utf-8-sig', dtype={'종목코드': str})
    except:
        df = pd.read_csv(target_file, encoding='cp949', dtype={'종목코드': str})
    
    df['종목코드'] = df['종목코드'].fillna('CASH').str.strip()
    df['보유수량'] = pd.to_numeric(df['보유수량'], errors='coerce').fillna(0)
    df['매수평단'] = pd.to_numeric(df['매수평단'], errors='coerce').fillna(0)
    if '자산군' not in df.columns: df['자산군'] = df['약식종목명']
    return df

# 스타일 설정
st.markdown("""<style>
    html, body, [class*="css"] { font-size: 12px !important; }
    h1 { font-size: 1.1rem !important; }
    [data-testid="stMetricValue"] { font-size: 1.0rem !important; }
    .stDataFrame div { font-size: 11px !important; }
    </style>""", unsafe_allow_html=True)

# 포맷팅 헬퍼
def safe_format(val):
    try: return f"{float(val):,.0f}"
    except: return val

def get_styled_df(target_df, cols_to_show):
    available_cols = [c for c in cols_to_show if c in target_df.columns]
    df_view = target_df[available_cols].copy().astype(object)
    if '종목코드' in target_df.columns:
        is_cash = target_df['종목코드'].str.upper() == 'CASH'
        for c in ['보유수량', '매수평단', '현재가']:
            if c in df_view.columns: df_view.loc[is_cash, c] = "-"
    rename_map = {'계좌명':'계좌', '약식종목명':'종목', '보유수량':'수량', '매수평단':'평단', '평가금액':'평가액'}
    df_view = df_view.rename(columns=rename_map)
    format_rules = {'평가액': '{:,.0f}', '수익률': '{:.2f}%', '비중': '{:.1f}%', '목표': '{:.1f}%', '차이': '{:+.1f}%'}
    for col in ['수량', '평단', '현재가']:
        if col in df_view.columns: format_rules[col] = lambda x: safe_format(x)
    return df_view.style.format(format_rules)

try:
    df_raw = load_data()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    
    # --- 📍 [TARGET_SETTING] 목표 비중 및 가이드 설정 ---
    # 1. 전체 포트폴리오 목표 (2번 탭용)
    total_target = {"나스닥100": 35.0, "S&P500": 35.0, "국내 ETF": 10.0, "금": 5.0, "현금": 15.0}
    
    # 2. 카테고리별 세부 목표 (3번 탭용)
    cat_target = {
        "세액공제 계좌": {"나스닥100": 40.0, "S&P500": 40.0, "기타": 20.0},
        "ISA": {"국내 ETF": 50.0, "현금": 50.0}
    }
    # -------------------------------------------------------

    with st.spinner('데이터 업데이트 중...'):
        unique_codes = asset_df['종목코드'].unique()
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금','NAN',''] else 1.0) for code in unique_codes}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['매수금액'] = asset_df.apply(lambda x: x['보유수량'] if x['종목코드'].upper() == 'CASH' else x['보유수량'] * x['매수평단'], axis=1)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval = asset_df['평가금액'].sum()

    # 탭 명칭 수정 (요청사항 반영)
    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리"])

    # --- 1. 종목 상세 ---
    with tabs[0]:
        sum_df = asset_df.groupby(['약식종목명', '종목코드', '자산군', '종목명']).agg({'보유수량':'sum', '매수금액':'sum', '평가금액':'sum'}).reset_index()
        sum_df['매수평단'] = sum_df['매수금액'] / sum_df['보유수량']
        sum_df['현재가'] = sum_df['종목코드'].map(price_map).fillna(0)
        sum_df['수익률'] = (sum_df['평가금액'] - sum_df['매수금액']) / sum_df['매수금액'] * 100
        st.dataframe(get_styled_df(sum_df.sort_values('평가금액', ascending=False), ['약식종목명', '자산군', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)
        
        st.divider()
        sel_name = st.selectbox("종목 선택", sum_df['종목명'].unique())
        detail_df = asset_df[(asset_df['종목명'] == sel_name) & (asset_df['보유수량'] > 0)].copy()
        st.dataframe(get_styled_df(detail_df, ['계좌명', '보유수량', '매수평단', '현재가', '평가금액', '수익률']), use_container_width=True, hide_index=True)

    # --- 2. 비중 및 리밸런싱 ---
    with tabs[1]:
        st.subheader("📊 전체 포트폴리오 리밸런싱 가이드")
        grp_df = asset_df.groupby('자산군').agg({'평가금액':'sum'}).reset_index()
        grp_df['비중'] = (grp_df['평가금액'] / total_eval) * 100
        grp_df['목표'] = grp_df['자산군'].map(total_target).fillna(0)
        grp_df['차이'] = grp_df['비중'] - grp_df['목표']
        
        # 가이드 텍스트 박스
        diff_5 = grp_df[abs(grp_df['차이']) >= 5.0]
        if len(diff_5) >= 3:
            st.error("🚨 **종합 리밸런싱 필요**: 3개 이상의 자산군이 목표 비중을 5% 이상 이탈했습니다.")
        elif len(diff_5) > 0:
            st.warning("⚠️ **부분 리밸런싱 권장**: 현재 자산 배분이 목표에서 조금씩 벗어나고 있습니다.")
        else:
            st.success("✅ **양호**: 모든 자산군이 목표 비중 내에서 순조롭게 운용 중입니다.")

        c1, c2 = st.columns(2)
        c1.plotly_chart(px.pie(grp_df, values='비중', names='자산군', title="현재 비중", hole=0.5).update_layout(height=300), use_container_width=True, key="p2_is")
        c2.plotly_chart(px.pie(grp_df, values='목표', names='자산군', title="목표 비중", hole=0.5).update_layout(height=300), use_container_width=True, key="p2_to")
        st.dataframe(get_styled_df(grp_df.sort_values('비중', ascending=False), ['자산군', '평가금액', '비중', '목표', '차이']), use_container_width=True, hide_index=True)

    # --- 3. 카테고리 분석 (계좌 통합 및 가이드) ---
    with tabs[2]:
        categories = {
            "세액공제 계좌": ["세액공제 O"],
            "일반 계좌": ["세액공제 X"],
            "ISA": ["ISA"]
        }
        for title, cats in categories.items():
            sub_df = asset_df[asset_df['계좌카테고리'].isin(cats)].copy()
            if not sub_df.empty:
                st.subheader(f"🏦 {title} 통합 분석")
                # 카테고리 내 비중 계산
                cat_eval = sub_df['평가금액'].sum()
                sub_grp = sub_df.groupby('자산군')['평가금액'].sum().reset_index()
                sub_grp['비중'] = (sub_grp['평가금액'] / cat_eval) * 100
                
                # 가이드 로직 (예: ISA는 현금 비중 유지 등)
                if title == "ISA" and sub_grp[sub_grp['자산군']=='현금']['비중'].sum() > 40:
                    st.info(f"💡 {title}: 현재 매수 대기 자금이 충분합니다. 시장 상황에 따라 순차 매수를 진행하세요.")
                
                st.plotly_chart(px.pie(sub_grp, values='비중', names='자산군', hole=0.5).update_layout(height=280), use_container_width=True, key=f"cat_pie_{title}")
                st.dataframe(get_styled_df(sub_df.assign(비중=(sub_df['평가금액']/cat_eval)*100).sort_values('비중', ascending=False), 
                             ['계좌명', '약식종목명', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)
                st.markdown("---")

    # --- 4. 계좌별 ---
    with tabs[3]:
        for acc in asset_df['계좌명'].unique():
            a_df = asset_df[asset_df['계좌명'] == acc].copy()
            st.markdown(f"### 🏦 {acc}")
            a_df['비중'] = (a_df['평가금액'] / a_df['평가금액'].sum()) * 100
            st.dataframe(get_styled_df(a_df.sort_values('비중', ascending=False), ['약식종목명', '보유수량', '현재가', '평가금액', '비중', '수익률']), use_container_width=True, hide_index=True)

    # --- 5. 환율관리 (As-Is vs To-Be 나란히 배치) ---
    with tabs[4]:
        st.subheader(f"🌎 현재 환율: {current_fx:,.2f}원")
        # 권장 비율 설정
        if current_fx > 1400: t_fx = {"노출": 30, "헤지": 70}
        elif current_fx < 1330: t_fx = {"노출": 80, "헤지": 20}
        else: t_fx = {"노출": 50, "헤지": 50}
        
        for tg in ["S&P500", "나스닥100"]:
            fx_data = asset_df[(asset_df['자산군'] == tg) & (asset_df['보유수량'] > 0)].copy()
            if not fx_data.empty:
                st.markdown(f"#### 📊 {tg} 환율 대응 (As-Is vs To-Be)")
                fx_data['구분'] = fx_data['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                curr_fx_grp = fx_data.groupby('구분')['평가금액'].sum().reset_index()
                
                c1, c2 = st.columns(2)
                with c1:
                    st.plotly_chart(px.pie(curr_fx_grp, values='평가금액', names='구분', title=f"{tg} 현재", hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}).update_layout(height=250), use_container_width=True, key=f"fx_is_{tg}")
                with c2:
                    rec_df = pd.DataFrame([{"구분":"환노출", "값":t_fx['노출']}, {"구분":"환헤지", "값":t_fx['헤지']}])
                    st.plotly_chart(px.pie(rec_df, values='값', names='구분', title=f"{tg} 권장", hole=0.5, color='구분', color_discrete_map={'환노출':'#EF553B', '환헤지':'#636EFA'}).update_layout(height=250), use_container_width=True, key=f"fx_to_{tg}")

except Exception as e:
    st.error(f"🚨 시스템 오류: {e}")
