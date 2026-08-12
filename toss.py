import streamlit as st
import requests

# -------------------------------------------------------------
# 1. 사용자 정보 설정 (발급받으신 진짜 키로 변경해주세요)
# -------------------------------------------------------------
API_KEY = "tsck_live_ZiTWKPQCOFGqJGIGkHNceF"
SECRET_KEY = "tssk_live_UhFQqT4efR9LK1Eb6uMPe9S8Oa3oeJuVjUeSuCC8EWfM"
BASE_URL = "https://openapi.tossinvest.com"

# -------------------------------------------------------------
# 2. 서버 IP 자동 확인
# -------------------------------------------------------------
try:
    server_ip = requests.get("https://api.ipify.org", timeout=5).text
    st.info(f"💡 허용 IP 관리 등록용 서버 IP: **[ {server_ip} ]**")
except Exception:
    pass

# -------------------------------------------------------------
# 3. 토큰 발급 및 계좌번호 조회 함수
# -------------------------------------------------------------
def get_access_token():
    url = f"{BASE_URL}/oauth2/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": SECRET_KEY,
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        st.error(f"❌ 토큰 발급 실패: {response.text}")
        return None

def get_account_seq(access_token):
    url = f"{BASE_URL}/api/v1/accounts"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json().get("result", [])
        if data:
            return data[0].get("accountSeq")
        st.error("❌ 계좌를 찾을 수 없습니다.")
        return None
    st.error(f"❌ 계좌 조회 실패: {response.text}")
    return None

# -------------------------------------------------------------
# 4. 보유 자산 현황 (현재가, 총평가액, 금일 변동액) 조회 함수
# -------------------------------------------------------------
def get_holdings(access_token, account_seq):
    url = f"{BASE_URL}/api/v1/holdings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Tossinvest-Account": str(account_seq)
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        result = response.json().get("result", {})
        items = result.get("items", [])
        
        # --- [1] 계좌 전체 요약 정보 ---
        market_val = result.get("marketValue", {}).get("amount", {})
        profit_loss = result.get("profitLoss", {})
        daily_pl = result.get("dailyProfitLoss", {})
        
        total_eval_krw = float(market_val.get("krw", 0) or 0)
        total_pl_krw = float(profit_loss.get("amount", {}).get("krw", 0) or 0)
        total_pl_rate = float(profit_loss.get("rate", 0) or 0) * 100
        daily_pl_krw = float(daily_pl.get("amount", {}).get("krw", 0) or 0)
        daily_pl_rate = float(daily_pl.get("rate", 0) or 0) * 100

        st.subheader("📌 전체 계좌 요약 (원화 기준)")
        col1, col2, col3 = st.columns(3)
        col1.metric("총 평가금액", f"{total_eval_krw:,.0f} 원")
        col2.metric("총 평가손익", f"{total_pl_krw:+,.0f} 원", f"{total_pl_rate:+.2f}%")
        col3.metric("금일 변동액", f"{daily_pl_krw:+,.0f} 원", f"{daily_pl_rate:+.2f}%")

        st.divider()

        # --- [2] 개별 종목 상세 현황 ---
        if not items:
            st.info("보유 중인 주식이 없습니다.")
            return

        st.subheader("📈 종목별 실시간 시세 및 평가 현황")
        
        for item in items:
            name = item.get("name", item.get("symbol"))
            curr = item.get("currency", "KRW")
            qty = float(item.get("quantity", 0))
            avg_price = float(item.get("averagePurchasePrice", 0))
            last_price = float(item.get("lastPrice", 0))
            
            # 종목별 금액 및 변동폭
            item_eval = float(item.get("marketValue", {}).get("amount", 0) or 0)
            item_daily_amount = float(item.get("dailyProfitLoss", {}).get("amount", 0) or 0)
            item_daily_rate = float(item.get("dailyProfitLoss", {}).get("rate", 0) or 0) * 100
            item_total_amount = float(item.get("profitLoss", {}).get("amount", 0) or 0)
            item_total_rate = float(item.get("profitLoss", {}).get("rate", 0) or 0) * 100
            
            # 통화 표기 단위
            symbol_curr = "원" if curr == "KRW" else "$"
            fmt = ",.0f" if curr == "KRW" else ",.2f"

            with st.expander(f"**{name}** | 현재가: {last_price:{fmt}}{symbol_curr}", expanded=True):
                c1, c2, c3, c4 = st.columns(4)
                c1.write(f"• **보유수량:** {qty:g} 주")
                c1.write(f"• **평단가:** {avg_price:{fmt}} {symbol_curr}")
                
                c2.write(f"• **실시간 현재가:** {last_price:{fmt}} {symbol_curr}")
                c2.write(f"• **총 평가금액:** {item_eval:{fmt}} {symbol_curr}")
                
                # 금일 변동 (HTML 태그 허용으로 수정 완료)
                d_color = "red" if item_daily_amount > 0 else ("blue" if item_daily_amount < 0 else "gray")
                c3.write("**금일 변동:**")
                c3.markdown(f"<span style='color:{d_color}; font-weight:bold;'>{item_daily_amount:+{fmt}} {symbol_curr} ({item_daily_rate:+.2f}%)</span>", unsafe_allow_html=True)
                
                # 누적 손익 (HTML 태그 허용으로 수정 완료)
                t_color = "red" if item_total_amount > 0 else ("blue" if item_total_amount < 0 else "gray")
                c4.write("**누적 손익:**")
                c4.markdown(f"<span style='color:{t_color}; font-weight:bold;'>{item_total_amount:+{fmt}} {symbol_curr} ({item_total_rate:+.2f}%)</span>", unsafe_allow_html=True)

    else:
        st.error(f"❌ 잔고 조회 실패: {response.text}")

# -------------------------------------------------------------
# 5. 메인 앱 레이아웃
# -------------------------------------------------------------
st.title("💰 토스증권 실시간 포트폴리오 대시보드")

if st.button("🔄 실시간 시세 및 잔고 새로고침"):
    with st.spinner("토스증권에서 최신 시세를 불러오는 중..."):
        token = get_access_token()
        if token:
            seq = get_account_seq(token)
            if seq:
                get_holdings(token, seq)
