import streamlit as st
import requests

# -------------------------------------------------------------
# 1. 사용자 정보 설정 (진짜 키로 변경해주세요)
# -------------------------------------------------------------
API_KEY = "tsck_live_ZiTWKPQCOFGqJGIGkHNceF"
SECRET_KEY = "tssk_live_UhFQqT4efR9LK1Eb6uMPe9S8Oa3oeJuVjUeSuCC8EWfM"
BASE_URL = "https://openapi.tossinvest.com"

# -------------------------------------------------------------
# 2. 화면 구성 (스트림릿 전용)
# -------------------------------------------------------------
st.title("📊 토스증권 내 주식 잔고 조회")
st.write("Open API를 이용해 내 계좌를 불러옵니다.")

# -------------------------------------------------------------
# 3. 토큰 발급 및 잔고 조회 함수
# -------------------------------------------------------------
def get_access_token():
    url = f"{BASE_URL}/v1/auth/token"
    headers = {"Content-Type": "application/json"}
    payload = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": SECRET_KEY,
    }
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        st.success("✅ 토스증권 서버 인증 성공!")
        return response.json().get("access_token")
    else:
        st.error(f"❌ 인증 실패: {response.text}")
        return None

def get_portfolio_balance(access_token):
    url = f"{BASE_URL}/v1/trading/accounts/balance"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        holdings = data.get("holdings", [])
        
        if not holdings:
            st.info("보유 중인 주식이 없습니다.")
        else:
            st.subheader("내 계좌 보유 주식 현황")
            # 보유 주식을 보기 쉽게 반복해서 출력합니다
            for item in holdings:
                name = item.get("name", item.get("symbol"))
                quantity = item.get("quantity", 0)
                avg_price = item.get("average_price", 0)
                
                st.write(f"▶ **{name}** | 보유수량: {quantity}주 | 평단가: {avg_price:,.0f}원")
    else:
        st.error(f"❌ 잔고 조회 실패: {response.text}")

# -------------------------------------------------------------
# 4. 버튼을 누르면 실행되도록 만들기
# -------------------------------------------------------------
if st.button("잔고 조회하기"):
    with st.spinner("토스증권에 연결 중입니다..."):
        token = get_access_token()
        if token:
            get_portfolio_balance(token)
