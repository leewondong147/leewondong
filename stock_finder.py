import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# 💡 [안전장치] 한국 주식 코드를 야후 파이낸스용(.KS / .KQ)으로 바꿔주는 지능형 변환기
def format_stock_code(code, market_type="KOSPI"):
    code = str(code).strip().zfill(6)
    if any(code.endswith(ext) for ext in ['.KS', '.KQ', '.ks', '.kq']):
        return code.upper()
    if market_type == "KOSDAQ":
        return f"{code}.KQ"
    return f"{code}.KS"

# 1. 앱 브랜딩 설정 (이원동 대표님 지존 주식앱!)
st.set_page_config(page_title="이원동 지존 주식앱", layout="wide")
st.title("🚀 이원동의 '잡가지 지존 주식앱' (Ver 1.5)")
st.caption("실시간 전종목 세력 포착 및 단기 급등락 감지 시스템")

# 2. 🔍 인터넷에서 실시간 한국 거래소(KRX) 전체 종목 리스트 원격 수집
@st.cache_data(ttl=3600) # 1시간 동안 리스트를 기억해서 속도를 엄청나게 빠르게 만듭니다.
def load_krx_contents():
    try:
        # 한국거래소(KRX) 상장종목 전체를 가져오는 인터넷 주소
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        dfs = pd.read_html(url, header=0)
        df_krx = dfs[0][['회사명', '종목코드']].copy()
        
        # 컬럼명을 다루기 쉽게 영어로 표준화
        df_krx.columns = ['Name', 'Code']
        # 6자리 숫자로 이쁘게 채우기 (예: 5930 -> 005930)
        df_krx['Code'] = df_krx['Code'].astype(str).str.zfill(6)
        return df_krx
    except Exception as e:
        # 혹시 KRX 서버가 점검 중이거나 다운되었을 때 앱이 튕기지 않게 비상용 백업 리스트 작동
        backup = [
            {"Name": "삼성전자", "Code": "005930"}, {"Name": "SK하이닉스", "Code": "000660"},
            {"Name": "현대차", "Code": "005380"}, {"Name": "네이버", "Code": "035420"},
            {"Name": "카카오", "Code": "035720"}, {"Name": "에코프로비엠", "Code": "247540"}
        ]
        return pd.DataFrame(backup)

# 데이터 로드 실행
krx_list = load_krx_contents()

# 🚨 [108번째 줄 에러 완벽 해결 구역] 
# 대표님이 수정하시다 살짝 지워졌던 'Name_Code' 조립 연산을 가장 안전한 위치에 다시 달았습니다!
krx_list['Name_Code'] = krx_list['Name'] + " (" + krx_list['Code'] + ")"

# 3. 사이드바 제어판
st.sidebar.header("⚙️ 지존 감시 설정")

# 🔥 문제의 108번째 줄! 이제 전종목 이름과 코드가 에러 없이 완벽하게 리스트로 펼쳐집니다.
selected_stock = st.sidebar.selectbox(
    "🎯 리스트에서 종목 선택:", 
    ["직접 입력"] + krx_list['Name_Code'].tolist()
)

# 종목 코드 최종 추출 및 코스피/코스닥 판별
if selected_stock == "직접 입력":
    raw_code = st.sidebar.text_input("✍️ 종목코드 직접 입력 (6자리)", "005930")
    market = st.sidebar.selectbox("📊 시장 구분", ["KOSPI (본장)", "KOSDAQ (코스닥)"])
    m_type = "KOSDAQ" if "KOSDAQ" in market else "KOSPI"
    final_code = format_stock_code(raw_code, m_type)
    stock_name = "직접 지정 종목"
else:
    # 선택한 "삼성전자 (005930)" 문장에서 이름과 코드를 분리해내는 고급 기술
    stock_name = selected_stock.split(" (")[0]
    pure_code = selected_stock.split(" (")[1].replace(")", "").strip()
    
    # 코스닥 종목(보통 코드가 2이나 3 등으로 시작하거나 대형주가 아닌 벤처들) 판별 안전장치
    # 조금 더 정밀하게 하기 위해 코드가 특정 범위이거나 사용자가 선택할 수 있게 하되, 
    # 기본적으로 야후에서 검틀하기 위해 포맷팅 적용
    final_code = format_stock_code(pure_code)
    
# 알림 조건 및 주기 세팅
target_percent = st.sidebar.number_input("🚨 알림 기준 상승률 (%)", min_value=0.1, max_value=10.0, value=1.0, step=0.1)
check_interval = st.sidebar.slider("⏱️ 감시 주기 (초 단위)", min_value=5, max_value=300, value=30)

# 4. 메인 대시보드 화면
st.subheader(f"🔍 감시 대상: {stock_name} [{final_code}]")
st.write(f"📢 **{check_interval}초**마다 주가를 추적하여 단기 **{target_percent}%** 이상 급등 시 팝업을 가동합니다.")

# 실시간 엔진 가동 버튼
if st.sidebar.button("🚀 실시간 지존 감시 가동"):
    st.info("⚡ 야후 파이낸스 실시간 위성망에 연결하는 중...")
    
    log_area = st.empty()
    alert_area = st.container()
    
    # 최초 가격 수집 (시작점 잡기)
    try:
        ticker = yf.Ticker(final_code)
        init_data = ticker.history(period="1d", interval="1m")
        
        # 혹시 장 시작 직전이거나 코드가 안 맞으면 2일 치 데이터로 재시도
        if init_data.empty:
            init_data = ticker.history(period="2d")
            
        base_price = init_data['Close'].iloc[-1]
        st.success(f"🎯 연결 완료! 실시간 추적 시작 (기준가격: {base_price:,.0f}원)")
    except Exception as e:
        # 코스피(.KS)로 안 찾아지면 코스닥(.KQ)으로 한 번 더 찔러보는 스마트 엔진
        try:
            alt_code = final_code.replace(".KS", ".KQ")
            ticker = yf.Ticker(alt_code)
            init_data = ticker.history(period="1d", interval="1m")
            if init_data.empty: init_data = ticker.history(period="2d")
            base_price = init_data['Close'].iloc[-1]
            final_code = alt_code
            st.success(f"🎯 코스닥 종목 연결 완료! (기준가격: {base_price:,.0f}원)")
        except:
            st.error(f"❌ 주식 데이터를 가져오지 못했습니다. 종목 코드나 시장 구분을 확인해 주세요! (오류: {e})")
            st.stop()

    # 5. 무한 루프 감시 시스템 작동
    while True:
        try:
            now = datetime.now().strftime('%H:%M:%S')
            current_data = ticker.history(period="1d", interval="1m")
            current_price = current_data['Close'].iloc[-1]
            
            # 상승률 연산
            change_rate = ((current_price - base_price) / base_price) * 100
            
            # 메인 화면 전광판 갱신
            with log_area:
                st.metric(
                    label=f"⏱️ [{now}] {stock_name} 실시간 현재가", 
                    value=f"{current_price:,.0f}원", 
                    delta=f"{change_rate:+.2f}% (감시 시작점 대비)"
                )
            
            # 목표치 돌파 시 급등 사이렌
            if change_rate >= target_percent:
                with alert_area:
                    st.balloons() # 축하 폭죽 효과
                    st.error(f"🔔 [🔥지존 세력 급등 포착🔥] {stock_name}({final_code})이 기준가 대비 {change_rate:.2f}% 돌파! 현재가: {current_price:,.0f}원")
                
                # 다음 추적을 위해 기준가를 현재가로 자동 갱신
                base_price = current_price
                
            time.sleep(check_interval)
            
        except Exception as e:
            st.warning(f"데이터 갱신 대기 중... ({e})")
            time.sleep(5)
