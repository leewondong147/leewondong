import streamlit as st
import requests

# -------------------------------------------------------------
# 1. 사용자 정보 설정 (발급받으신 진짜 키로 변경해주세요)
# -------------------------------------------------------------
API_KEY = "tsck_live_ZiTWKPQCOFGqJGIGkHNceF"
SECRET_KEY = "tssk_live_UhFQqT4efR9LK1Eb6uMPe9S8Oa3oeJuVjUeSuCC8EWfM"
BASE_URL = "https://openapi.tossinvest.com"

# -------------------------------------------------------------
# 2. 토큰 발급 함수 (경로 및 전송 방식 수정)
# -------------------------------------------------------------
def get_access_token():
    url = f"{BASE_URL}/oauth2/token"  # 설명서에 맞게 경로 변경!
    payload = {
        "grant_type": "client_credentials",
        "client_id": API_KEY,
        "client_secret": SECRET_KEY,
    }
    # JSON이 아니라 일반 Form 데이터(data=payload)로 전송합니다.
    response = requests.post(url, data=payload)
    
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        st.error(f"❌ 토큰 발급 실패: {response.text}")
        return None

# -------------------------------------------------------------
# 3. 내 계좌번호(accountSeq) 조회 함수
# -------------------------------------------------------------
def get_account_seq(access_token):
    url = f"{BASE_URL}/api/v1/accounts"
    headers = {"Authorization": f"Bearer {access_token}"}
    
    response = requests.get(url, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        accounts = data.get("result", [])
        if accounts:
            # 첫 번째 종합매매 계좌의 고유번호를 반환합니다.
            return accounts[0].get("accountSeq")
        else:
            st.error("❌ 토스증권 계좌를 찾을 수 없습니다.")
            return None
    else:
        st.error(f"❌ 계좌 조회 실패: {response.text}")
        return None

# -------------------------------------------------------------
# 4. 주식 잔고 및 평단가 조회 함수
# -------------------------------------------------------------
def get_holdings(access_token, account_seq):
    url = f"{BASE_URL}/api/v1/holdings"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "X-Tossinvest-Account": str(account_seq) # 알아낸 계좌번호를 헤더에 필수로 넣습니다!
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
                # 문자열로 오는 가격을 숫자로 변환합니다.
                avg_price = float(item.get("averagePurchasePrice", 0))
                
                st.write(f"▶ **{name}** | 보유수량: **{qty}주** | 평단가: **{avg_price:,.0f}원**")
    else:
        st.error(f"❌ 잔고 조회 실패: {response.text}")

# -------------------------------------------------------------
# 5. 스트림릿 화면 구성 및 버튼 실행
# -------------------------------------------------------------
st.title("💰 토스증권 내 주식 잔고 조회")
st.write("토스증권 Open API를 이용해 내 계좌를 불러옵니다.")

if st.button("잔고 조회하기"):
    with st.spinner("토스증권 서버와 통신 중입니다..."):
        # 1단계: 출입증 받기
        token = get_access_token()
        if token:
            # 2단계: 내 계좌번호 확인하기
            account_seq = get_account_seq(token)
            if account_seq:
                st.success("✅ 토스증권 연결 성공!")
                # 3단계: 잔고 불러오기
                get_holdings(token, account_seq)
