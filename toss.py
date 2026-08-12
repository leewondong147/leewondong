import requests

API_KEY = "ZiTWKPQCOFGqJGIGkHNceF"
SECRET_KEY = "UhFQqT4efR9LK1Eb6uMPe9S8Oa3oeJuVjUeSuCC8EWfM"
BASE_URL = "https://openapi.tossinvest.com"

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
        print("✅ 인증 성공: Access Token을 정상 발급받았습니다.")
        return response.json().get("access_token")
    else:
        print(f"❌ 인증 실패 (상태 코드: {response.status_code}): {response.text}")
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
        print("\n==========================================")
        print("          📊 내 계좌 보유 주식 현황          ")
        print("==========================================")
        holdings = data.get("holdings", [])
        if not holdings:
            print("보유 중인 주식이 없거나 잔고를 불러올 수 없습니다.")
        else:
            for item in holdings:
                name = item.get("name", item.get("symbol"))
                quantity = item.get("quantity", 0)
                print(f"▶ 종목명: {name} | 보유수량: {quantity}주")
    else:
        print(f"❌ 잔고 조회 실패: {response.text}")

if __name__ == "__main__":
    token = get_access_token()
    if token:
        get_portfolio_balance(token)
    
    # 🚨 이 줄이 핵심입니다! 프로그램이 바로 종료되지 않고 화면을 멈춰줍니다.
    input("\n[실행 완료] 화면을 닫으려면 엔터키를 누르세요...")
