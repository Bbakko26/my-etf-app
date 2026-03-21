import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import plotly.graph_objects as go
import plotly.express as px

# --- [추가] 리밸런싱 엔진 클래스 ---
class RebalanceEngine:
    def __init__(self, target_weights, safe_assets):
        self.target_weights = target_weights
        self.safe_assets = safe_assets

    def calculate(self, df):
        # 계좌별 잔액 및 현재가 추출
        account_balances = df.groupby('계좌명')['평가금액'].sum().to_dict()
        total_assets = sum(account_balances.values())
        current_prices = df.set_index('약식종목명')['현재가'].to_dict()
        
        # 1. 전체 포트폴리오 차원의 종목별 목표 금액
        overall_target_amounts = {t: total_assets * w for t, w in self.target_weights.items()}
        allocation = {acc: {t: 0 for t in self.target_weights} for acc in account_balances}
        remaining_targets = overall_target_amounts.copy()

        # 2. IRP 안전자산 30% 우선 할당 (Step A)
        irp_accounts = [acc for acc in account_balances if 'IRP' in acc]
        for acc in irp_accounts:
            required_safe = account_balances[acc] * 0.3
            allocated_safe = 0
            for t in sorted(self.safe_assets, key=lambda x: self.target_weights.get(x, 0), reverse=True):
                if allocated_safe >= required_safe: break
                can_fill = min(remaining_targets.get(t, 0), required_safe - allocated_safe)
                allocation[acc][t] = can_fill
                allocated_safe += can_fill
                remaining_targets[t] -= can_fill

        # 3. 나머지 자산 배분 (Step B)
        for acc, balance in account_balances.items():
            available = balance - sum(allocation[acc].values())
            rem_total_target = sum(remaining_targets.values())
            if rem_total_target > 0:
                for t in self.target_weights:
                    if remaining_targets[t] > 0:
                        share = remaining_targets[t] / rem_total_target
                        to_add = min(remaining_targets[t], available * share)
                        # IRP 위험자산 70% 캡 체크
                        if 'IRP' in acc and t not in self.safe_assets:
                            risk_limit = (balance * 0.7) - sum(v for k, v in allocation[acc].items() if k not in self.safe_assets)
                            to_add = min(to_add, max(0, risk_limit))
                        allocation[acc][t] += to_add
                        remaining_targets[t] -= to_add

        # 4. 결과 정리
        res = []
        for acc, assets in allocation.items():
            for t, target_val in assets.items():
                curr_val = df[(df['계좌명'] == acc) & (df['약식종목명'] == t)]['평가금액'].sum()
                price = current_prices.get(t, 1)
                diff_qty = int((target_val - curr_val) // price) if price > 0 else 0
                if diff_qty != 0:
                    res.append({'계좌': acc, '종목': t, '현재가': price, '목표금액': target_val, '필요수량': diff_qty})
        return pd.DataFrame(res)

# --- 기존 코드의 탭 부분 수정 ---
# 탭 정의에 "⚖️ 리밸런싱" 추가
tabs = st.tabs(["📊 종목 상세", "🍩 전체 비중", "🏦 카테고리 분석", "💼 계좌별", "🌎 환율관리", "⚖️ 리밸런싱"])

# ... (기존 TAB 0~4 로직 유지) ...

# --- TAB 6: 리밸런싱 (신규 이식) ---
with tabs[5]:
    st.subheader("⚖️ 통합 목표 기반 리밸런싱 가이드")
    
    # 설정값 (사용자가 정한 통합 비중)
    my_targets = {
        'S&P500': 0.45, '나스닥100': 0.25, '금': 0.15, '미국국채': 0.10, 'KOFR': 0.05
    }
    safe_list = ['금', '미국국채', 'KOFR']
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write("**🎯 통합 목표 비중**")
        st.json(my_targets)
    
    with col2:
        st.write("**🛡️ 안전자산 룰 (IRP 30%)**")
        st.info(f"대상 종목: {', '.join(safe_list)}")
        
    if st.button("🔄 리밸런싱 계산하기"):
        engine = RebalanceEngine(my_targets, safe_list)
        # asset_df는 기존 코드에서 연산된 데이터프레임 사용
        rebal_df = engine.calculate(asset_df)
        
        if not rebal_df.empty:
            st.success("계산 완료! 아래 수량만큼 매수/매도하세요.")
            # 가시성을 위해 스타일 적용
            def color_diff(val):
                color = 'red' if val > 0 else 'blue'
                return f'color: {color}'
            
            st.dataframe(rebal_df.style.applymap(color_diff, subset=['필요수량']).format({
                '목표금액': '{:,.0f}', '현재가': '{:,.0f}'
            }), use_container_width=True, hide_index=True)
        else:
            st.info("현재 포트폴리오가 목표 비중에 근접합니다. 조정이 필요 없습니다.")
