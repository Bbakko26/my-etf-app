"""
2단계 탭 구조 데모
"""
import streamlit as st

st.set_page_config(page_title="탭 구조 데모", layout="wide")

st.markdown("""
<style>
html, body, [class*="css"] { font-size: 12px !important; }
.stApp { background: linear-gradient(180deg, #07101f 0%, #0b1220 100%); }
.block-container { padding-top: 1rem !important; max-width: 980px !important; }

/* ── 1단계 탭 (대분류) ── */
div[data-testid="stTabs"] > div:first-child {
    gap: 6px !important;
}
div[data-testid="stTabs"] button[role="tab"] {
    border-radius: 20px !important;
    padding: 6px 18px !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    border: 1px solid rgba(148,163,184,0.15) !important;
    background: rgba(15,23,42,0.6) !important;
    color: #94a3b8 !important;
    transition: all 0.2s !important;
}
div[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {
    background: rgba(99,102,241,0.25) !important;
    border-color: #6366f1 !important;
    color: #e0e7ff !important;
}

/* ── 2단계 탭 (소분류) ── */
.sub-tab-container {
    display: flex;
    gap: 4px;
    margin: 12px 0 16px 0;
    flex-wrap: wrap;
}
.sub-tab-btn {
    padding: 4px 14px;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 500;
    border: 1px solid rgba(148,163,184,0.12);
    background: rgba(15,23,42,0.4);
    color: #94a3b8;
    cursor: pointer;
    transition: all 0.15s;
}
.sub-tab-btn.active {
    background: rgba(139,92,246,0.2);
    border-color: #8b5cf6;
    color: #ddd6fe;
}

/* ── 컨텐츠 카드 ── */
.demo-card {
    background: rgba(15,23,42,0.76);
    border: 1px solid rgba(148,163,184,0.10);
    border-radius: 18px;
    padding: 20px;
    margin-top: 8px;
}
</style>
""", unsafe_allow_html=True)

st.title("💰 Family Portfolio")
st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

# ── 1단계 탭 (대분류 3개) ──────────────────────────────────────
tab1, tab2, tab3 = st.tabs(["📊 포트폴리오", "⚖️ 매매 / 리밸런싱", "⚙️ 설정"])

# ════════════════════════════════════════
# 대분류 1: 포트폴리오
# ════════════════════════════════════════
with tab1:
    # 2단계 탭 (소분류)
    sub_options = ["종목 상세", "전체 비중", "카테고리"]
    if "portfolio_sub" not in st.session_state:
        st.session_state.portfolio_sub = "종목 상세"

    cols = st.columns(len(sub_options))
    for i, opt in enumerate(sub_options):
        is_active = st.session_state.portfolio_sub == opt
        label = f"{'●' if is_active else '○'} {opt}"
        if cols[i].button(label, key=f"p_sub_{i}",
                          use_container_width=True,
                          type="primary" if is_active else "secondary"):
            st.session_state.portfolio_sub = opt
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    # 소분류별 컨텐츠
    if st.session_state.portfolio_sub == "종목 상세":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### 📋 종목 상세")
        st.markdown("보유 종목 현황, 수익률, 캔들차트가 여기에 표시됩니다.")
        import pandas as pd
        demo_df = pd.DataFrame({
            "종목": ["S&P500(H)", "나스닥100(H)", "금"],
            "보유수량": [31, 24, 60],
            "평단": [16200, 20800, 33195],
            "현재가": [16615, 21085, 31070],
            "수익률": ["+2.56%", "+1.37%", "-6.40%"],
        })
        st.dataframe(demo_df, use_container_width=True, hide_index=True)
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.portfolio_sub == "전체 비중":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### 🍩 전체 포트폴리오 비중")
        st.markdown("도넛 차트 + 현재 vs 목표 비중 비교가 여기에 표시됩니다.")
        st.progress(0.045, text="금 4.5% (목표 5%)")
        st.progress(0.955, text="현금 95.5% (목표 0%)")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.portfolio_sub == "카테고리":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### 🏦 카테고리별 비중")
        st.markdown("세액공제O / 세액공제X / ISA 별 도넛 차트가 여기에 표시됩니다.")
        for cat in ["세액공제 O", "세액공제 X", "ISA"]:
            st.markdown(f"**{cat}** — 총 1,854만원")
            st.divider()
        st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════════
# 대분류 2: 매매 / 리밸런싱
# ════════════════════════════════════════
with tab2:
    sub_options2 = ["리밸런싱 신호", "매매 입력", "매매 기록"]
    if "trade_sub" not in st.session_state:
        st.session_state.trade_sub = "리밸런싱 신호"

    cols2 = st.columns(len(sub_options2))
    for i, opt in enumerate(sub_options2):
        is_active = st.session_state.trade_sub == opt
        label = f"{'●' if is_active else '○'} {opt}"
        if cols2[i].button(label, key=f"t_sub_{i}",
                           use_container_width=True,
                           type="primary" if is_active else "secondary"):
            st.session_state.trade_sub = opt
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if st.session_state.trade_sub == "리밸런싱 신호":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### ⚖️ 리밸런싱 신호")
        c1, c2, c3 = st.columns(3)
        c1.metric("장세", "상승장", delta="신뢰도 67%")
        c2.metric("생애주기", "공격기", delta="은퇴까지 24년")
        c3.metric("환율 구간", "고환율", delta="헤지 70%")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.trade_sub == "매매 입력":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### 📝 매매 체결 입력")
        st.selectbox("계좌카테고리", ["세액공제 O", "세액공제 X", "ISA"])
        st.selectbox("계좌명", ["연금저축(키움)", "IRP(미래)", "경영성과IRP(삼성)"])
        st.selectbox("종목명", ["S&P500(H)", "S&P500", "나스닥100(H)", "나스닥100", "금", "미국채"])
        st.number_input("체결수량", min_value=0.0, step=1.0)
        st.number_input("체결가", min_value=0, step=100)
        st.button("✅ 저장", use_container_width=True, type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.trade_sub == "매매 기록":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### 📋 최근 매매 기록")
        st.markdown("매수/매도 히스토리가 여기에 표시됩니다.")
        st.markdown('</div>', unsafe_allow_html=True)

# ════════════════════════════════════════
# 대분류 3: 설정
# ════════════════════════════════════════
with tab3:
    sub_options3 = ["포트폴리오 설정", "잔고 수정"]
    if "setting_sub" not in st.session_state:
        st.session_state.setting_sub = "포트폴리오 설정"

    cols3 = st.columns(len(sub_options3))
    for i, opt in enumerate(sub_options3):
        is_active = st.session_state.setting_sub == opt
        label = f"{'●' if is_active else '○'} {opt}"
        if cols3[i].button(label, key=f"s_sub_{i}",
                           use_container_width=True,
                           type="primary" if is_active else "secondary"):
            st.session_state.setting_sub = opt
            st.rerun()

    st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)

    if st.session_state.setting_sub == "포트폴리오 설정":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### ⚙️ 포트폴리오 설정")
        st.number_input("은퇴 예정 연도", value=2050, min_value=2025, max_value=2070)
        st.selectbox("장세 수동 설정", ["자동 (지표 기반)", "상승장", "보합장", "하락장"])
        st.button("저장", type="primary")
        st.markdown('</div>', unsafe_allow_html=True)

    elif st.session_state.setting_sub == "잔고 수정":
        st.markdown('<div class="demo-card">', unsafe_allow_html=True)
        st.markdown("#### ✏️ 잔고 직접 수정")
        st.markdown("초기 데이터 입력 및 수동 보정용입니다.")
        st.markdown('</div>', unsafe_allow_html=True)
