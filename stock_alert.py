import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

st.set_page_config(page_title="이원동 주식 알림이", layout="wide")
st.title("📈 이원동 실시간 급등 감지 시스템 (Ver 1.0)")

# 1. 감시할 종목 및 조건 설정 구역
st.sidebar.header("⚙️ 감시 설정")
# 국내 주식은 종목코드 뒤에 .KS(코스피) 또는 .KQ(코스닥)을 붙여야 합니다.
stock_code = st.sidebar.text_input("🎯 종목코드 입력 (예: 삼성전자는 005930.KS)", "005930.KS")
target_percent = st.sidebar.number_input("🚨 알림 기준 상승률 (%)", min_value=0.5, max_value=10.0, value=1.5, step=0.1)
check_interval = st.sidebar.slider("⏱️ 감시 주기 (초 단위)", min_value=10, max_value=300, value=60)

st.subheader(f"🔍 현재 감시 종목: [{stock_code}] / 조건: 단기 {target_percent}% 이상 급등 시")

# 감시 시작 버튼
if st.sidebar.button("🚀 실시간 감시 시작"):
    st.info("시장에 접속하여 실시간 감시를 시작합니다. (중단하려면 브라우저를 새로고침하세요)")
    
    # 실시간 로그를 보여줄 빈 칸 생성
    log_area = st.empty()
    alert_area = st.container()
    
    # 기준 가격 설정 (프로그램 시작할 때의 가격)
    try:
        ticker = yf.Ticker(stock_code)
        init_data = ticker.history(period="1d", interval="1m")
        base_price = init_data['Close'].iloc[-1]
        st.success(f"✅ 연결 성공! 감시 시작 기준가: {base_price:,.0f}원")
    except Exception as e:
        st.error(f"종목코드를 확인해주세요. 에러: {e}")
        st.stop()

    # 무한 루프를 돌며 시장 감시
    while True:
        try:
            # 실시간 현재가 가져오기
            now = datetime.now().strftime('%H:%M:%S')
            current_data = ticker.history(period="1d", interval="1m")
            current_price = current_data['Close'].iloc[-1]
            
            # 상승률 계산
            change_rate = ((current_price - base_price) / base_price) * 100
            
            # 화면에 실시간 상태 업데이트
            with log_area:
                st.write(f"⏱️ [{now}] 현재가: {current_price:,.0f}원 | 기준가 대비 변동률: {change_rate:+.2f}%")
            
            # 조건 비교: 설정한 상승률을 넘어섰을 때
            if change_rate >= target_percent:
                with alert_area:
                    st.balloons() # 화면에 축하 폭죽 효과
                    st.error(f"🔔 [🔥급등 알림🔥] {stock_code} 종목이 기준가({base_price:,.0f}원) 대비 {change_rate:.2f}% 급등 중! 현재가: {current_price:,.0f}원")
                
                # [다음 단계] 여기에 대표님 스마트폰 텔레그램/카카오톡으로 메시지 쏘는 코드가 들어갑니다.
                # 알림을 보낸 후 현재가를 새로운 기준가로 갱신 (지속적인 상승 감시를 위해)
                base_price = current_price 
                
            # 설정한 시간만큼 대기 후 다시 확인
            time.sleep(check_interval)
            
        except Exception as e:
            st.warning(f"데이터를 가져오는 중 일시적 오류 발생, 재시도합니다... ({e})")
            time.sleep(5)
