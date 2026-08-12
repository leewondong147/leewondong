import streamlit as st
import requests

# -------------------------------------------------------------
# 1. 사용자 정보 설정 (발급받으신 진짜 키로 변경해주세요)
# -------------------------------------------------------------
API_KEY = "tsck_live_ZiTWKPQCOFGqJGIGkHNceF"
SECRET_KEY = "tssk_live_UhFQqT4efR9LK1Eb6uMPe9S8Oa3oeJuVjUeSuCC8EWfM"
BASE_URL = "https://openapi.tossinvest.com"

# -------------------------------------------------------------
# 2. 스트림릿 서버의 진짜 IP 주소 찾기 (자동)
# -------------------------------------------------------------
# 이 코드가 스트림릿의 진짜 외부 인터넷 주소를 알아내 줍니다.
server_ip = requests.get("https://api.ipify.org").text
st.info(f"💡 토스증권에 등록해야 할 이 서버의 IP 주소는 [ {server_ip} ] 입니다.")
st.write("위 IP 주소를 복사해서 토스증권 WTS [설정] > [Open API] > [허용 IP 관리]에 추가해 주세요.")

# -------------------------------------------------------------
# 3. 토큰 발급 함수
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

# -------------------------------------------------------------
# 4. 내 계좌번호(accountSeq) 조회 함수
# -------------------------------------------------------------
def get_account_seq(access_token):
    url = f"{BASE_URL}/api/v1/accounts"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        accounts = data.get("result", [])
        if accounts:
            return accounts[0].get("accountSeq")
        else:
            st.error("❌ 토스증권 계좌를 찾을 수 없습니다.")
            return None
    else:
        st.error(f"❌ 계좌 조회 실패: {response.text}")
        return None

# -------------------------------------------------------------
# 5. 주식 잔고 및 평단가 조회 함수
# -------------------------------------------------------------
def get_holdings(access_token, account_seq):
    url = f"{BASE_URL}/api/v1/holdings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Tossinvest-Account": str(account_seq)
    }
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json().get("result", {})
        items = data.get("items", [])
        
        if not items:
            st.info("보유 중인 주식이 없습니다.")
        else:
            st.subheader("📊 내 계좌 보유 주식 현황")
            for item in items:
                name = item.get("name")
                qty = item.get("quantity")
                avg_price = float(item.get("averagePurchasePrice", 0))
                st.write(f"▶ **{name}** | 보유수량: **{qty}주** | 평단가: **{avg_price:,.0f}원**")
    else:
        st.error(f"❌ 잔고 조회 실패: {response.text}")

# -------------------------------------------------------------
# 6. 화면 구성 및 실행 버튼
# -------------------------------------------------------------
st.title("💰 토스증권 내 주식 잔고 조회")

if st.button("잔고 조회하기"):
    with st.spinner("토스증권 서버와 통신 중입니다..."):
        token = get_access_token()
        if token:
            account_seq = get_account_seq(token)
            if account_seq:
                st.success("✅ 토스증권 연결 성공!")
                get_holdings(token, account_seq)
