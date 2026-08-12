import requests

# -------------------------------------------------------------
# 1. 사용자 정보 설정 (토스증권 개발자 센터 발급 정보)
# -------------------------------------------------------------
API_KEY = "ZiTWKPQCOFGqJGIGkHNceF"
SECRET_KEY = "UhFQqT4efR9LK1Eb6uMPe9S8Oa3oeJuVjUeSuCC8EWfM"

# 토스증권 Open API 기본 URL
BASE_URL = "https://openapi.tossinvest.com"


# -------------------------------------------------------------
# 2. Access Token(출입증) 발급 함수
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
        token_data = response.json()
        print("✅ 인증 성공: Access Token을 정상 발급받았습니다.")
        return token_data.get("access_token")
    else:
        print(
            f"❌ 인증 실패 (상태 코드: {response.status_code}): {response.text}"
        )
        return None


# -------------------------------------------------------------
# 3. 계좌 보유 잔고 및 평단가 조회 함수
# -------------------------------------------------------------
def get_portfolio_balance(access_token):
    url = f"{BASE_URL}/v1/trading/accounts/balance"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()
        print("\n==========================================")
        print("          📊 내 계좌 보유 주식 현황          ")
        print("==========================================")

        # 응답 데이터 내 보유 종목 리스트 추출 (토스증권 API 규격에 맞춰 파싱)
        holdings = data.get("holdings", [])

        if not holdings:
            print("보유 중인 주식이 없거나 잔고를 불러올 수 없습니다.")
            return

        for item in holdings:
            symbol = item.get("symbol")  # 종목코드 (예: 005930)
            name = item.get("name", symbol)  # 종목명
            quantity = item.get("quantity", 0)  # 보유 수량
            avg_price = item.get("average_price", 0)  # 평균 단가(평단가)
            current_price = item.get("current_price", 0)  # 현재가

            print(f"▶ 종목명: {name} ({symbol})")
            print(f"   - 보유수량: {quantity:,} 주")
            print(f"   - 평단가  : {avg_price:,.0f} 원")
            if current_price:
                print(f"   - 현재가  : {current_price:,.0f} 원")
            print("------------------------------------------")
    else:
        print(
            f"❌ 잔고 조회 실패 (상태 코드: {response.status_code}): {response.text}"
        )


# -------------------------------------------------------------
# 4. 메인 실행부
# -------------------------------------------------------------
if __name__ == "__main__":
    # 1단계: 토큰 발급
    token = get_access_token()

    # 2단계: 토큰 발급 성공 시 잔고 조회 실행
    if token:
        get_portfolio_balance(token)
