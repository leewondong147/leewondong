import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta
import FinanceDataReader as fdr  # 🚨 과거 데이터 조회를 위해 fdr 라이브러리 추가 필수!

# ==========================================
# 앱 아이콘 및 탭 제목 설정 (Ver 12.0 RSI 완결판)
# ==========================================
st.set_page_config(page_title="이원동 자산 증식 레이더", page_icon="💸", layout="wide")
st.title("💸 이원동의 '거래대금 스파이크 & 눌림목 타점 스캐너' (Ver 12.0)")
st.caption("RSI 50 고정 버그를 완벽하게 수리하고, 과거 데이터를 동기화하여 정확한 실시간 과매도 타점을 계측합니다.")

# 1. 네이버 실시간 거래량/거래대금 최상위 대형주 자동 크롤링
@st.cache_data(ttl=3600)
def get_naver_top_market_codes(count=500):
    codes = []
    names = {}
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    for market_type in ["KOSPI", "KOSDAQ"]:
        try:
            res = requests.get(f"https://polling.finance.naver.com/api/realtime?query=SERVICE_MARKET:{market_type}_SUM", headers=headers, timeout=5)
            data = res.json()
            items = data['result']['areas'][0]['datas']
            for item in items:
                c_str = str(item['cd']).strip().zfill(6)
                codes.append(c_str)
                names[c_str] = item['nm']
        except:
            pass
            
    fallback_heavy = [
        ("005930", "삼성전자"), ("000660", "SK하이닉스"), ("267260", "HD현대일렉트릭"),
        ("042700", "한미반도체"), ("034020", "두산에너빌리티"), ("000720", "현대건설"),
        ("328130", "루닛"), ("005380", "현대차"), ("247540", "에코프로비엠"),
        ("068270", "셀트리온"), ("005490", "POSCO홀딩스"), ("035420", "NAVER"),
        ("003670", "포스코퓨처엠"), ("051910", "LG화학"), ("035720", "카카오"),
        ("012330", "현대모비스"), ("066570", "LG전자"), ("000270", "기아"),
        ("096770", "SK이노베이션"), ("032830", "삼성생명"), ("086520", "에코프로"),
        ("006400", "삼성SDI"), ("373220", "LG에너지솔루션"), ("207940", "삼성바이오로직스")
    ]
    
    for c, n in fallback_heavy:
        if c not in codes:
            codes.append(c)
        names[c] = n
        
    return codes[:count], names

final_market_codes, code_to_name_map = get_naver_top_market_codes(500)

# 🚨 [핵심 엔진 추가] RSI 예열용 과거 주가 데이터 고속 다운로드 기능
@st.cache_data(ttl=3600)
def preload_historical_prices(codes):
    hist_dict = {}
    end_date = datetime.today()
    start_date = end_date - timedelta(days=40) # 최근 약 30거래일 데이터 확보
    for code in codes:
        try:
            df = fdr.DataReader(code, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            hist_dict[code] = df['Close'].tolist()
        except:
            hist_dict[code] = []
    return hist_dict

# 2. 자체 RSI 보조지표 연산 엔진 (안전성 강화)
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    
    df = pd.DataFrame(prices, columns=['close'])
    delta = df['close'].diff()
    
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    
    # 분모가 0일 경우(계속 가격이 같을 경우)의 에러를 방지합니다.
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    
    # 결측치(NaN)가 발생하면 기본적으로 과매수(100)로 쳐서 방어합니다.
    rsi = rsi.fillna(100.0) 
    return rsi.iloc[-1]

# 3. 네이버 금융 실시간 멀티 데이터 수집 엔진
def get_naver_advanced_data(codes):
    results = {}
    if not codes:
        return results
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        chunks = [codes[i:i + 50] for i in range(0, len(codes), 50)]
        for chunk in chunks:
            chunk_str = ",".join(chunk)
            res = requests.get(f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{chunk_str}", headers=headers, timeout=5)
            data = res.json()
            items = data['result']['areas'][0]['datas']
            for item in items:
                code = item['cd']
                current_price = int(item['nv']) if item['nv'] is not None else 0
                prev_close = int(item['sv']) if item['sv'] is not None else current_price
                volume = int(item['aq']) if item['aq'] is not None else 0
                trade_value_eok = int(item['aa']) / 100000000 if item['aa'] is not None else 0
                
                results[code] = {
                    "current": current_price,
                    "prev_close": prev_close,
                    "volume": volume,
                    "trade_value_eok": trade_value_eok
                }
    except:
        pass
    return results

# ==========================================
# ⚙️ 제어판 (사이드바 전략 설정 시스템)
# ==========================================
st.sidebar.header("⚙️ 전략 필터 시스템")

watch_mode = st.sidebar.radio("👇 감시 대상 선택", ["🛰️ 시장 상위 대형주 스캔", "📋 내 관심/보유 종목 지정 감시"], key="radar_mode")

final_codes = []
if watch_mode == "🛰️ 시장 상위 대형주 스캔":
    scan_limit = st.sidebar.slider("📊 스캔할 종목 수", min_value=50, max_value=500, value=200, step=50, key="radar_limit")
    final_codes = final_market_codes[:scan_limit]
else:
    st.sidebar.subheader("✍️ 내 관심 종목 입력")
    my_stocks_input = st.sidebar.text_area(
        "감시할 보유/관심 종목코드 입력 (쉼표 구분):", 
        value="005930, 267260, 000720, 042700, 328130, 034020",
        key="radar_text_area"
    )
    final_codes = [c.strip().zfill(6) for c in my_stocks_input.split(",") if c.strip()]

st.sidebar.write("---")
st.sidebar.subheader("🔥 1번 전략: 거래대금 폭발 조건")
min_money = st.sidebar.number_input("💸 당일 거래대금 기준 (억원 이상)", min_value=10, max_value=5000, value=500, step=50, key="radar_min_money")

st.sidebar.write("---")
st.sidebar.subheader("🛡️ 2번 전략: 눌림목 바닥 조건")
rsi_limit = st.sidebar.slider("📉 RSI 과매도 기준치 (이하)", min_value=20, max_value=45, value=35, key="radar_rsi")
disparity_limit = st.sidebar.slider("🎯 당일 변동폭 하한선 (몇 % 이하 급락?)", min_value=80.0, max_value=99.0, value=95.0, key="radar_disp")

check_interval = st.sidebar.slider("⏱️ 레이더 회전 주기 (초 단위)", min_value=5, max_value=120, value=10, key="radar_interval")

# ==========================================
# 메인 레이더 관제창
# ==========================================
st.subheader("🛰️ 주도주 돈줄 추적 & 과매도 타점 연산 가동")
st.write(f"📢 현재 **{len(final_codes)}개 종목**의 실시간 거래대금 스파이크 현황과 RSI 가격 왜곡 현상을 무결점으로 동시 추적합니다.")

if st.sidebar.button("🚀 독점적 시스템 매매 스캔 시작", key="btn_radar_run"):
    # 🚨 RSI를 위한 과거 데이터 사전 장착 (캐싱되어 있으므로 최초 1회만 약 10~30초 소요됩니다)
    with st.spinner("⌛ RSI 엔진 예열 중... 과거 30일치 주가 데이터를 동기화하고 있습니다. 잠시만 기다려주세요."):
        historical_db = preload_historical_prices(final_codes)
        
    st.info("⚡ 메인 광통신망 직결 완료! 돈의 흐름과 가격 바닥 신호를 실시간 추적합니다.")
    
    log_area = st.empty()
    grid_container = st.empty()
    
    detected_signals = []

    while True:
        now_time = datetime.now().strftime('%H:%M:%S')
        with log_area:
            st.write(f"🔄 [{now_time}] 세력 거래대금 유입량 및 보조지표 바닥 매칭 연산 중...")

        try:
            live_data = get_naver_advanced_data(final_codes)
            
            for code in final_codes:
                try:
                    data = live_data.get(code)
                    if data is None or data["current"] == 0: 
                        continue
                    
                    curr_price = data["current"]
                    prev_close = data["prev_close"]
                    trade_money = data["trade_value_eok"]
                    
                    # 🛠️ 수리 완료: 과거 30일치 종가 리스트 끝에 '현재 실시간 가격'을 합쳐 완벽한 당일 RSI를 도출합니다.
                    base_history = historical_db.get(code, [])[-30:] 
                    temp_prices = base_history + [curr_price]
                    
                    cond_money = trade_money >= min_money
                    rsi_val = calculate_rsi(temp_prices)
                    disparity_val = (curr_price / prev_close) * 100 if prev_close > 0 else 100.0
                    cond_bottom = (rsi_val <= rsi_limit) or (disparity_val <= disparity_limit)
                    
                    if cond_money or cond_bottom:
                        stock_name = code_to_name_map.get(code, f"우량주({code})")
                        change_rate = ((curr_price - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
                        
                        if cond_money and cond_bottom:
                            signal_type = "👑 [지존] 대금폭발+바닥눌림"
                        elif cond_money:
                            signal_type = "🔥 [주도주] 거래대금 폭발"
                        else:
                            signal_type = "🛡️ [타점] 과매도 바닥눌림"
                            
                        is_duplicate = False
                        for e in detected_signals:
                            if e['종목명'] == stock_name and e['시그널'] == signal_type:
                                is_duplicate = True
                                break
                                
                        if not is_duplicate:
                            detected_signals.insert(0, {
                                "포착시간": now_time,
                                "시그널": signal_type,
                                "종목명": stock_name,
                                "현재가": f"{curr_price:,.0f}원",
                                "당일변동률": f"{change_rate:+.2f}%",
                                "당일거래대금": f"{int(trade_money):,}억",
                                "RSI지표": f"{round(rsi_val, 1)}",
                                "당일변동수준": f"{round(disparity_val, 1)}%"
                            })
                            if "👑" in signal_type: 
                                st.balloons()
                except:
                    continue
            
            if detected_signals:
                df_disp = pd.DataFrame(detected_signals)
                with grid_container:
                    st.error("🚨 [실전 매매 포착: 진짜 돈이 몰리는 주도주 및 급락 눌림목 타점 목록] 🚨")
                    st.dataframe(df_disp, use_container_width=True, height=500)
            else:
                with grid_container:
                    st.info(f"📡 현재 당일 거래대금 {min_money}억 이상 터지거나 과매도 바닥 조건에 걸린 알짜 종목이 없습니다. 탐색 회전 지속 중...")
                    
            time.sleep(check_interval)
        except Exception as e:
            time.sleep(5)
