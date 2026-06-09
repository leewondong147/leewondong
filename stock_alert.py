import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time
from datetime import datetime

# ==========================================
# 앱 아이콘 및 탭 제목 설정
# ==========================================
st.set_page_config(page_title="이원동 자산 증식 레이더", page_icon="💸", layout="wide")
st.title("💸 이원동의 '거래대금 스파이크 & 눌림목 타점 스캐너' (Ver 10.1)")
st.caption("시장의 진짜 돈줄(거래대금)을 추적하고, 보조지표(RSI/이격도) 기반 단기 바닥 타점을 실시간 엄선합니다.")

# 1. 거래소 전체 종목 매퍼 로드
@st.cache_data(ttl=3600)
def load_krx_mapper():
    try:
        df_ks = fdr.StockListing('KOSPI')
        df_kd = fdr.StockListing('KOSDAQ')
        df_total = pd.concat([df_ks, df_kd], ignore_index=True)
        
        mapper = {}
        for _, row in df_total.iterrows():
            code = str(row['Code']).strip().zfill(6)
            mapper[code] = row['Name']
        return mapper, df_total
    except:
        fallback = {"005930": "삼성전자", "000660": "SK하이닉스", "267260": "HD현대일렉트릭", "042700": "한미반도체", "034020": "두산에너빌리티"}
        return fallback, pd.DataFrame()

code_to_name_map, raw_df = load_krx_mapper()

# 2. 자체 RSI 보조지표 계산 함수
def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50 # 데이터 부족 시 중간값 반환
    df = pd.DataFrame(prices, columns=['close'])
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not rsi.empty else 50

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

# 4. 제어판 (사이드바 설정)
st.sidebar.header("⚙️ 전략 필터 시스템")

watch_mode = st.sidebar.radio("👇 감시 대상 선택", ["🛰️ 시장 상위 대형주 스캔", "📋 내 관심/보유 종목 지정 감시"])

final_codes = []
if watch_mode == "🛰️ 시장 상위 대형주 스캔":
    scan_limit = st.sidebar.slider("📊 스캔할 종목 수", min_value=30, max_value=300, value=200, step=10)
    if not raw_df.empty:
        final_codes = [str(c).strip().zfill(6) for c in raw_df.head(scan_limit)['Code']]
    else:
        final_codes = list(code_to_name_map.keys())
else:
    my_stocks_input = st.sidebar.text_area(
        "감시할 보유/관심 종목코드 입력 (쉼표 구분):", 
        value="005930, 267260, 000720, 042700, 328130, 034020"
    )
    final_codes = [c.strip().zfill(6) for c in my_stocks_input.split(",") if c.strip()]

st.sidebar.write("---")
st.sidebar.subheader("🔥 1번 전략: 거래대금 폭발 조건")
min_money = st.sidebar.number_input("💸 당일 거래대금 기준 (억원 이상)", min_value=10, max_value=5000, value=500, step=50)

st.sidebar.write("---")
st.sidebar.subheader("🛡️ 2번 전략: 눌림목 바닥 조건")
rsi_limit = st.sidebar.slider("📉 RSI 과매도 기준치 (이하)", min_value=20, max_value=45, value=35)
disparity_limit = st.sidebar.slider("🎯 20일선 이격도 하한선 (몇 % 이탈?)", min_value=80.0, max_value=99.0, value=95.0)

check_interval = st.sidebar.slider("⏱️ 레이더 회전 주기 (초 단위)", min_value=10, max_value=120, value=20)

# 5. 메인 레이더 관제창
st.subheader("🛰️ 주도주 돈줄 추적 & 과매도 타점 연산 가동")
st.write(f"📢 현재 **{len(final_codes)}개 종목**의 실시간 거래대금 스파이크 현황과 RSI 가격 왜곡 현상을 동시에 추적하고 있습니다.")

if st.sidebar.button("🚀 독점적 시스템 매매 스캔 시작"):
    st.info("⚡ 메인 광통신망에 연결되었습니다. 돈의 흐름과 가격 바닥 신호를 실시간 추적합니다.")
    
    log_area = st.empty()
    grid_container = st.empty()
    
    price_history = {code: [] for code in final_codes}
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
                    if data is None or data["current"] == 0: continue
                    
                    curr_price = data["current"]
                    prev_close = data["prev_close"]
                    trade_money = data["trade_value_eok"]
                    
                    price_history[code].append(curr_price)
                    if len(price_history[code]) > 30:
                        price_history[code].pop(0)
                        
                    cond_money = trade_money >= min_money
                    rsi_val = calculate_rsi(price_history[code])
                    disparity_val = (curr_price / prev_close) * 100
                    cond_bottom = (rsi_val <= rsi_limit) or (disparity_val <= disparity_limit)
                    
                    if cond_money or (watch_mode == "📋 내 관심/보유 종목 지정 감시" and cond_bottom):
                        stock_name = code_to_name_map.get(code, f"미등록({code})")
                        change_rate = ((curr_price - prev_close) / prev_close) * 100
                        
                        if cond_money and cond_bottom:
                            signal_type = "👑 [지존] 대금폭발+바닥눌림"
                        elif cond_money:
                            signal_type = "🔥 [주도주] 거래대금 폭발"
                        else:
                            signal_type = "🛡️ [타점] 과매도 바닥눌림"
                            
                        # 🚨 [깔끔하게 수정 완료] 복잡한 구문 대신 가장 안정적인 중복 검증 로직으로 변경했습니다.
                        is_duplicate = False
                        for e in detected_signals:
                            if e['종목명'] == stock_name and e['현재가'] == f"{curr_price:,.0f}원":
                                is_duplicate = True
                                break
                                
                        if not is_duplicate:
                            detected_signals.insert(0, {
                                "포착시간": now_time,
                                "시그널": signal_type,
                                "종목명": stock_name,
                                "현재가": f"{curr_price:,.0f}원",
                                "당일변동률": f"{change_rate:+.2f}%",
                                "당일거래대금": f"{int(trade_money):
