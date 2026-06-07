import streamlit as st
import yfinance as yf
import pandas as pd
import time
from datetime import datetime

# 1. 국내 주식 코드를 야후 파이낸스 표준(.KS / .KQ)으로 바꿔주는 자동 변환기
def format_stock_code(code, market_type="KOSPI"):
    code = str(code).strip().zfill(6)
    if any(code.endswith(ext) for ext in ['.KS', '.KQ', '.ks', '.kq']):
        return code.upper()
    if market_type == "KOSDAQ":
        return f"{code}.KQ"
    return f"{code}.KS"

# 2. 앱 화면 설정
st.set_page_config(page_title="이원동 실시간 레이더", page_icon="📡", layout="wide")
st.title("📡 이원동의 '실시간 급등락 레이더' (Ver 1.0)")
st.caption("장중에 실시간으로 가격 변동을 감시하여 급등/급락 종목을 실시간으로 포착합니다.")

# 3. 한국거래소(KRX) 상장 종목 리스트 원격 수집 (이글아이와 동일한 안전 방식)
@st.cache_data(ttl=3600)
def load_krx_list():
    try:
        url = 'http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13'
        dfs = pd.read_html(url, header=0)
        df_krx = dfs[0][['회사명', '종목코드']].copy()
        df_krx.columns = ['Name', 'Code']
        df_krx['Code'] = df_krx['Code'].astype(str).str.zfill(6)
        return df_krx
    except:
        # 비상용 백업 리스트
        backup = [
            {"Name": "삼성전자", "Code": "005930"}, {"Name": "SK하이닉스", "Code": "000660"},
            {"Name": "현대차", "Code": "005380"}, {"Name": "네이버", "Code": "035420"},
            {"Name": "카카오", "Code": "035720"}, {"Name": "에코프로비엠", "Code": "247540"}
        ]
        return pd.DataFrame(backup)

krx_list = load_krx_list()

# 4. 제어판 (사이드바 설정)
st.sidebar.header("⚙️ 레이더 감시 설정")

# 감시 모드 선택 (전체 시장 스캔 vs 내 관심종목 1개 집중 감시)
watch_mode = st.sidebar.radio("👇 감시 모드 선택", ["🎯 선택 종목 집중 감시", "🛰️ 상위 종목 전체 스캔"])

if watch_mode == "🎯 선택 종목 집중 감시":
    krx_list['Name_Code'] = krx_list['Name'] + " (" + krx_list['Code'] + ")"
    selected_stock = st.sidebar.selectbox("🎯 감시할 종목 선택:", krx_list['Name_Code'].tolist())
    pure_code = selected_stock.split(" (")[1].replace(")", "").strip()
    final_codes = [format_stock_code(pure_code)]
    stock_names = {final_codes[0]: selected_stock.split(" (")[0]}
    
else:
    scan_limit = st.sidebar.slider("📊 스캔할 종목 수 (상위 N개)", min_value=10, max_value=200, value=50, step=10)
    subset_df = krx_list.head(scan_limit)
    final_codes = [format_stock_code(code) for code in subset_df['Code']]
    stock_names = {format_stock_code(row['Code']): row['Name'] for _, row in subset_df.iterrows()}

# 알림 기준 및 감시 주기 설정
target_percent = st.sidebar.number_input("🚨 알림 기준 변동률 (±%)", min_value=0.0, max_value=10.0, value=1.5, step=0.1)
detect_type = st.sidebar.selectbox("📈 감시 방향", ["우상향 급등만 포착", "우하향 급락만 포착", "급등/급락 둘 다 포착"])
check_interval = st.sidebar.slider("⏱️ 감시 주기 (초 단위)", min_value=5, max_value=120, value=30)

# 5. 메인 레이더 작동 구역
st.subheader("📡 레이더 가동 준비 완료")
if watch_mode == "🎯 선택 종목 집중 감시":
    st.write(f"📢 **[{stock_names[final_codes[0]]}]** 종목을 **{check_interval}초**마다 추적하여 **{target_percent}%** 이상 변동 시 사이렌을 울립니다.")
else:
    st.write(f"📢 시장 상위 **{len(final_codes)}개 종목**을 한 번에 그물망 스캔하여 단기 변동성 종목을 실시간 추출합니다.")

# 가동 버튼
if st.sidebar.button("🚀 실시간 레이더 가동"):
    st.info("⚡ 야후 파이낸스 실시간 위성망에 접속하여 주가 모니터링을 시작합니다...")
    
    log_area = st.empty()
    alert_container = st.empty()
    
    base_prices = {}
    detected_events = [] # 포착된 내역 누적 배열

    # 1회차: 시작 기준 가격 셋팅
    with st.spinner("⌛ 시스템 가동을 위해 기초 주가를 수집하고 있습니다..."):
        try:
            init_data = yf.download(final_codes, period="1d", interval="1m", group_by='ticker', progress=False)
            for y_code in final_codes:
                try:
                    if len(final_codes) == 1:
                        base_prices[y_code] = init_data['Close'].iloc[-1] if not init_data.empty else None
                    else:
                        if y_code in init_data and not init_data[y_code].empty:
                            base_prices[y_code] = init_data[y_code]['Close'].iloc[-1]
                except:
                    base_prices[y_code] = None
        except Exception as e:
            st.error(f"초기 데이터 연결 실패: {e}")
            st.stop()

    st.success("🎯 기준가 수집 완료! 레이더 회전을 시작합니다. (장중에 켜놓으시면 실시간 작동합니다)")

    # 무한 루프 실시간 감시 엔진
    while True:
        now_time = datetime.now().strftime('%H:%M:%S')
        with log_area:
            st.write(f"🔄 [{now_time}] 레이더가 실시간으로 주가 변동을 계산하는 중...")

        try:
            # 실시간 가격 리로드
            current_data = yf.download(final_codes, period="1d", interval="1m", group_by='ticker', progress=False)
            
            for y_code in final_codes:
                try:
                    if len(final_codes) == 1:
                        current_price = current_data['Close'].iloc[-1] if not current_data.empty else None
                    else:
                        current_price = current_data[y_code]['Close'].iloc[-1] if y_code in current_data else None
                        
                    if current_price is None or pd.isna(current_price): continue
                    
                    if y_code not in base_prices or base_prices[y_code] is None or pd.isna(base_prices[y_code]):
                        base_prices[y_code] = current_price
                        continue
                        
                    base_price = base_prices[y_code]
                    change_rate = ((current_price - base_price) / base_price) * 100
                    
                    # 조건 판단 (급등 / 급락)
                    is_detected = False
                    event_type = ""
                    
                    if detect_type in ["우상향 급등만 포착", "급등/급락 둘 다 포착"] and change_rate >= target_percent:
                        is_detected = True
                        event_type = "🔥 급등 포착"
                    elif detect_type in ["우하향 급락만 포착", "급등/급락 둘 다 포착"] and change_rate <= -target_percent:
                        is_detected = True
                        event_type = "📉 급락 경고"
                        
                    if is_detected:
                        # 동일 시간 중복 등록 방지
                        if not any(e['시간'] == now_time and e['종목명'] == stock_names[y_code] for e in detected_events):
                            detected_events.insert(0, {
                                "시간": now_time,
                                "구분": event_type,
                                "종목명": stock_names[y_code],
                                "코드": y_code.split('.')[0],
                                "감시기준가": f"{base_price:,.0f}원",
                                "현재가": f"{current_price:,.0f}원",
                                "단기변동률": f"{change_rate:+.2f}%"
                            })
                            if event_type == "🔥 급등 포착": st.balloons()
                            base_prices[y_code] = current_price
                except:
                    continue
                    
            # 6. 화면 전광판 표 출력
            if detected_events:
                df_events = pd.DataFrame(detected_events)
                with alert_container:
                    st.error("🚨 [실시간 레이더 포착 시그널 현황] 🚨")
                    st.dataframe(df_events, use_container_width=True)
            else:
                with alert_container:
                    st.info("📡 조건에 맞게 요동치는 종목이 아직 없습니다. 계속 주시 중...")
                    
            time.sleep(check_interval)
        except Exception as e:
            time.sleep(5)
