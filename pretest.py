import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime

# [필수] 최상단 설정
st.set_page_config(page_title="Family Portfolio", layout="wide")

# 1. 데이터 로드
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

# 이중 도넛 함수
def create_double_donut(labels, current_vals, target_vals, title, key_id):
    color_map = {'환노출': '#EF553B', '환헤지': '#636EFA'}
    if labels and labels[0] not in color_map:
        colors = px.colors.qualitative.Pastel
        color_map = {label: colors[i % len(colors)] for i, label in enumerate(labels)}
    fig = go.Figure()
    fig.add_trace(go.Pie(labels=labels, values=target_vals, hole=0.88, sort=False, direction='clockwise',
        marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels], line=dict(color='white', width=1)),
        opacity=0.3, hoverinfo="label+percent", name="목표"))
    fig.add_trace(go.Pie(labels=labels, values=current_vals, hole=0.65, sort=False, direction='clockwise',
        marker=dict(colors=[color_map.get(l, '#BDC3C7') for l in labels], line=dict(color='white', width=2)),
        hoverinfo="label+percent", name="현재", domain={'x': [0.1, 0.9], 'y': [0.1, 0.9]}))
    fig.update_layout(title=dict(text=title, font=dict(size=13)), height=320, margin=dict(t=50, b=10, l=10, r=10), showlegend=True, legend=dict(orientation="h", y=-0.1))
    return fig

try:
    df_raw = load_data()
    seed_df = df_raw[df_raw['종목코드'] == 'SEED'].copy()
    asset_df = df_raw[df_raw['종목코드'] != 'SEED'].copy()
    
    # --- 📍 [TARGET_SETTING] ---
    code_map = {"S&P500": {"노출": "360750", "헤지": "448290"}, "나스닥100": {"노출": "133690", "헤지": "448300"}, "다우존스": {"노출": "458730", "헤지": "452250"}}
    # --------------------------

    with st.spinner('실시간 시세 로드 중...'):
        price_map = {code: (fdr.DataReader(code).tail(1)['Close'].iloc[-1] if code.upper() not in ['CASH','현금'] else 1.0) for code in asset_df['종목코드'].unique()}
        current_fx = float(fdr.DataReader('USD/KRW').tail(1)['Close'].iloc[-1])

    asset_df['현재가'] = asset_df['종목코드'].map(price_map).fillna(0)
    asset_df['평가금액'] = asset_df['보유수량'] * asset_df['현재가']
    total_eval = asset_df['평가금액'].sum()

    tabs = st.tabs(["1. 종목 상세", "2. 비중 및 리밸런싱", "3. 카테고리 분석", "4. 계좌별", "5. 환율관리", "6. 실탄 관리"])

    # --- 5. 환율관리 ---
    with tabs[4]:
        st.subheader(f"🌎 실시간 환율: {current_fx:,.2f}원")
        
        # 환율에 따른 동적 목표 비중 설정
        if current_fx >= 1450: t_fx = {"노출": 0, "헤지": 100}
        elif current_fx >= 1400: t_fx = {"노출": 30, "헤지": 70}
        elif current_fx >= 1330: t_fx = {"노출": 70, "헤지": 30}
        elif current_fx >= 1250: t_fx = {"노출": 100, "헤지": 0}
        else: t_fx = {"노출": 100, "헤지": 0}

        fx_config = {"세액공제 O": ["S&P500", "나스닥100"], "세액공제 X": ["S&P500", "나스닥100"], "ISA": ["다우존스", "S&P500"]}
        for cat, targets in fx_config.items():
            st.markdown(f"#### 🏦 {cat}")
            cols = st.columns(len(targets))
            for i, asset in enumerate(targets):
                f_df = asset_df[(asset_df['계좌카테고리'] == cat) & (asset_df['자산군'] == asset)].copy()
                if not f_df.empty:
                    f_df['구분'] = f_df['약식종목명'].apply(lambda x: '환헤지' if '(H)' in x else '환노출')
                    asis = f_df.groupby('구분')['평가금액'].sum().reset_index()
                    labels = ['환노출', '환헤지']
                    curr_vals = [asis[asis['구분']==l]['평가금액'].sum() for l in labels]
                    total_v = sum(curr_vals)
                    curr_p = [(v/total_v)*100 if total_v > 0 else 0 for v in curr_vals]
                    with cols[i]:
                        st.plotly_chart(create_double_donut(labels, curr_p, [t_fx['노출'], t_fx['헤지']], f"{asset} 대응 현황", f"fx_{cat}_{asset}"), use_container_width=True)

        st.divider()
        st.subheader("📈 원/달러 환율 구간별 정밀 액션 가이드")

        # 가이드 표 데이터
       모든 행의 키(Key)를 일관되게 '기존 보유분 관리'로 통일
        guide_data = [
            {
                "환율 구간": "1,450원 이상", 
                "단계": "심각", 
                "신규 매수 액션": "100% 환헤지(H) 종목만 매수", 
                "기존 보유분 관리": "기존 환노출 수익분의 50% 이상을 (H)로 스위칭"
            },
            {
                "환율 구간": "1,400 ~ 1,450원", 
                "단계": "주의", 
                "신규 매수 액션": "환헤지(H) 70% : 환노출 30%", 
                "기존 보유분 관리": "신규 적립금으로 환헤지 비중을 우선 채움"
            },
            {
                "환율 구간": "1,330 ~ 1,400원", 
                "단계": "중립", 
                "신규 매수 액션": "환헤지(H) 30% : 환노출 70%", 
                "기존 보유분 관리": "비중 이탈이 없다면 기존 포지션 유지"
            },
            {
                "환율 구간": "1,250 ~ 1,330원", 
                "단계": "안정", 
                "신규 매수 액션": "100% 환노출 종목 매수", 
                "기존 보유분 관리": "환헤지(H) 종목을 환노출로 서서히 교체 시작"
            },
            {
                "환율 구간": "1,250원 미만", 
                "단계": "기회", 
                "신규 매수 액션": "100% 환노출 + 적극 매수", 
                "기존 보유분 관리": "모든 (H) 종목을 환노출로 전환 완료"
            }
        ]
        guide_df = pd.DataFrame(guide_data)

        # 📍 현재 환율 구간 하이라이트 함수
        def highlight_row(row):
            is_active = False
            fx_range = row['환율 구간']
            if "이상" in fx_range and current_fx >= 1450: is_active = True
            elif "미만" in fx_range and current_fx < 1250: is_active = True
            elif "~" in fx_range:
                low, high = map(lambda x: float(x.replace(',','').replace('원','').strip()), fx_range.split('~'))
                if low <= current_fx < high: is_active = True
            
            return ['background-color: rgba(255, 75, 75, 0.3); font-weight: bold;' if is_active else '' for _ in row]

        st.table(guide_df.style.apply(highlight_row, axis=1))

    # --- 6. 실탄 관리 ---
    with tabs[5]:
        st.subheader("🔋 미집행 자산(실탄) 운용 가이드")
        cash_sum = asset_df[asset_df['자산군'] == '현금']['평가금액'].sum()
        weeks_left = max(1, (datetime(2026, 12, 31) - datetime.now()).days // 7)
        st.info(f"💡 **분할 매수**: 보유 실탄 {cash_sum:,.0f}원을 연말까지 매주 **{cash_sum/weeks_left:,.0f}원**씩 투입하세요.")
        
        target_f = "헤지" if current_fx > 1400 else "노출"
        recom_list = [{"자산군": a, "추천코드": c[target_f], "유형": f"환{target_f}"} for a, c in code_map.items()]
        st.table(pd.DataFrame(recom_list))

except Exception as e:
    st.error(f"🚨 오류 발생: {e}")
