import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# 1. 앱 기본 설정
st.set_page_config(page_title="이원동 지존 주식앱", layout="wide")
st.title("🚀 이원동의 '전종목 실시간 급등락 레이더' (Ver 2.0)")
st.caption("한국 시장 전체(KRX) 상장 종목을 한 번에 돌려 급등 징후를 실시간 포착합니다.")

# 2. 인터넷에서 실시간 한국 거래소(KRX) 전체 종목 리스트 원격 수집
@st.cache_data(ttl=3600)
def load_krx_contents():
    try:
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        dfs = pd.read_html(url, header=0)
        df_krx = dfs[0][['회사명', '종목코드']].copy()
        df_krx.columns = ['Name', 'Code']
        df_krx['Code'] = df_krx['Code'].astype(str).str.zfill(6)
        return df_krx
    except Exception as e:
        # 비상용 백업 핵심 리스트
        backup = [
            {"Name": "삼성전자", "Code": "005930"}, {"Name": "SK하이닉스", "Code": "000660"},
            {"Name": "현대차", "Code": "005380"}, {"Name": "네이버", "Code": "035420"},
            {"Name": "카카오", "Code": "035720"}, {"Name": "에코프로비엠", "Code": "247540"}
        ]
        return pd.DataFrame(backup)

# 데이터 로드 실행
krx_list = load_krx_contents()

# 3. 제어판 (사이드바)
st.sidebar.header("⚙️ 레이더 감시 설정")
target_percent = st.sidebar.number_input("🚨 포착 기준 상승률 (%)", min_value=0.1, max_value=10.0, value=2.0, step=0.1)
scan_limit = st.sidebar.slider("📊 스캔할 종목 수 (테스트용)", min_value=10, max_value=len(krx_list), value=50, step=10)

st.subheader(f"📡 현재 상장 종목 중 상위 {scan_limit}개 종목을 대상으로 단기 {target_percent}% 이상 급등주를 탐색합니다.")

# 4. 실시간 레이더 가동 버튼
if st.sidebar.button("🛰️ 전종목 실시간 레이더 가동"):
    st.info("⚡ 한국 시장 전체 종목을 감시망에 등록하고 스캔을 시작합니다...")
    
    # 발견된 급등주를 실시간으로 누적해서 보여줄 표(데이터프레임) 자리 만들기
    detected_container = st.empty()
    log_container = st.empty()
    
    # 처음 켰을 때 전체 종목의 '시작 가격'을 기억해둘 저장소(딕셔너리)
    base_prices = {}
    detected_stocks = [] # 포착된 급등주 목록 리스트

    # 대상 종목들의 최초 기준 가격 세팅 (속도를 위해 최초 1회 수집)
    with st.spinner("⌛ 모든 종목의 감시 시작 기준가를 수집하고 있습니다... (약 10~20초 소요)"):
        # 설정한 스캔 제한 수만큼만 먼저 돌립니다 (야후 파이낸스 과부하 방지용)
        subset_list = krx_list.head(scan_limit)
        
        # 야후용 코드로 한방에 묶어서 조회하기 (속도 극대화 꿀팁!)
        yahoo_codes = [f"{code}.KS" for code in subset_list['Code']]
        try:
            # 여러 종목을 한 번에 다운로드
            tickers_data = yf.download(yahoo_codes, period="1d", interval="1m", group_by='ticker', progress=False)
            
            for code in subset_list['Code']:
                y_code = f"{code}.KS"
                try:
                    # 각 종목별 가장 최근 종가(현재가)를 기준가로 저장
                    if y_code in tickers_data and not tickers_data[y_code].empty:
                        base_prices[code] = tickers_data[y_code]['Close'].iloc[-1]
                except:
                    # 코스피에서 실패하면 코스닥(.KQ)으로 시도할 수 있도록 일단 보류
                    base_prices[code] = None
        except Exception as e:
            st.error(f"초기 데이터 수집 중 오류 발생: {e}")
            st.stop()
            
    st.success("🎯 모든 종목 감시망 등록 완료! 실시간 순회 스캔을 시작합니다.")

    # 5. 무한 루프 스캔 엔진 가동
    while True:
        now_time = datetime.now().strftime('%H:%M:%S')
        with log_container:
            st.write(f"🔄 [{now_time}] 전체 종목 실시간 재스캔 중...")

        try:
            # 실시간으로 전체 주가 한 번에 긁어오기
            current_tickers_data = yf.download(yahoo_codes, period="1d", interval="1m", group_by='ticker', progress=False)
            
            # 2,500개 종목을 하나씩 돌면서 상승률 체크하는 자동 반복문!
            for idx, row in subset_list.iterrows():
                name = row['Name']
                code = row['Code']
                y_code = f"{code}.KS"
                
                # 데이터가 정상적으로 들어왔는지 확인
                if y_code in current_tickers_data and not current_tickers_data[y_code].empty:
                    current_price = current_tickers_data[y_code]['Close'].iloc[-1]
                    
                    # 기준가가 없는 종목은 현재가를 기준가로 잡아줌
                    if code not in base_prices or base_prices[code] is None or pd.isna(base_prices[code]):
                        base_prices[code] = current_price
                        continue
                        
                    base_price = base_prices[code]
                    
                    # 📈 상승률 실시간 연산!
                    if base_price > 0:
                        change_rate = ((current_price - base_price) / base_price) * 100
                        
                        # 🚨 설정한 포착 기준(예: 2%)을 넘었을 때!
                        if change_rate >= target_percent:
                            # 이미 발견된 종목인지 중복 체크 후 리스트에 추가
                            already_detected = any(s['종목코드'] == code for s in detected_stocks)
                            if not already_detected:
                                detected_stocks.append({
                                    "포착시간": now_time,
                                    "종목명": name,
                                    "종목코드": code,
                                    "기준가격": f"{base_price:,.0f}원",
                                    "현재가격": f"{current_price:,.0f}원",
                                    "실시간상승률": f"{change_rate:+.2f}%"
                                })
                                # 새로운 파동 추적을 위해 기준가 갱신
                                base_prices[code] = current_price
            
            # 6. 발견된 급등주가 있다면 화면 전광판에 실시간 표로 출력!
            if detected_stocks:
                df_detected = pd.DataFrame(detected_stocks)
                with detected_container:
                    st.error("🚨 [지존 세력 급등 포착 목록] 🚨")
                    st.dataframe(df_detected, use_container_width=True)
            else:
                with detected_container:
                    st.info("📡 현재 조건에 맞는 급등 종목이 없습니다. 계속 탐색 중...")

            # 야후 파이낸스 차단 방지 및 서버 과부하 방지를 위해 10초 대기 후 다음 바퀴 회전
            time.sleep(10)
            
        except Exception as e:
            time.sleep(5)
