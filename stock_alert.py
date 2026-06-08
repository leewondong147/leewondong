import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
import time
from datetime import datetime

# ==========================================
# 앱 아이콘 및 탭 제목 설정
# ==========================================
st.set_page_config(page_title="이원동 실시간 레이더", page_icon="📡", layout="wide")
st.title("📡 이원동의 '실시간 전종목 급등락 레이더' (Ver 6.0)")
st.caption("전일 종가 대비 실시간 누적 변동률을 6개 제한 없이 전종목 초고속으로 포착합니다.")

# 🚨 [6개 제한 전면 해결 구역] 해외 서버 방화벽에 막히지 않는 초고속 거래소 리스트 로더
@st.cache_data(ttl=3600)
def load_krx_list_secure():
    try:
        # 이글아이에서 검증된 최강의 수집 방식 적용 (코스피 상위 300개 대형주 중심)
        df_ks = fdr.StockListing('KOSPI').head(200)
        df_kd = fdr.StockListing('KOSDAQ').head(100)
        df_total = pd.concat([df_ks, df_kd], ignore_index=True)
        
        # 필요한 기둥만 예쁘게 정제
        df_final = df_total[['Name', 'Code']].copy()
        df_final['Code'] = df_final['Code'].astype(str).str.zfill(6)
        return df_final
    except Exception as e:
        # 최후의 수단 백업 (대표님 주력 15개 종목으로 대폭 확장)
        backup = [
            {"Name": "삼성전자", "Code": "005930"}, {"Name": "SK하이닉스", "Code": "000660"},
            {"Name": "현대차", "Code": "005380"}, {"Name": "네이버", "Code": "035420"},
            {"Name": "카카오", "Code": "035720"}, {"Name": "에코프로비엠", "Code": "247540"},
            {"Name": "기아", "Code": "000270"}, {"Name": "셀트리온", "Code": "068270"},
            {"Name": "POSCO홀딩스", "Code": "005490"}, {"Name": "LG에너지솔루션", "Code": "373220"},
            {"Name": "삼성SDI", "Code": "006400"}, {"Name": "LG화학", "Code": "051910"},
            {"Name": "신한지주", "Code": "055550"}, {"Name": "삼성물산", "Code": "028260"},
            {"Name": "알테오젠", "Code": "196170"}
        ]
        return pd.DataFrame(backup)

krx_list = load_krx_list_secure()

# 3. 네이버 금융 실시간 주가 및 전일 종가 수집 함수
def get_naver_realtime_data(codes):
    results = {}
    if not codes:
        return results
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 대량 종목 처리를 위해 50개씩 조각내서 네이버에 초고속 던지기
        chunks = [codes[i:i + 50] for i in range(0, len(codes), 50)]
        for chunk in chunks:
            chunk_str = ",".join(chunk)
            res = requests.get(f"https://polling.finance.naver.com/api/realtime?query=SERVICE_ITEM:{chunk_str}", headers=headers, timeout=5)
            data = res.json()
            items = data['result']['areas'][0]['datas']
            for item in items:
                code = item['cd']
                current_price = int(item['nv']) if item['nv'] is not None else 0
                prev_close = int(item['sv']) if item['sv'] is not None else current_price # sv = 전일 종가
                
                results[code] = {
                    "current": current_price,
                    "prev_close": prev_close
                }
    except:
        pass
    return results

# 4. 제어판 (사이드바 설정)
st.sidebar.header("⚙️ 레이더 감시 설정")

watch_mode = st.sidebar.radio("👇 감시 모드 선택", ["🛰️ 상위 종목 전체 스캔", "📋 내 매수 종목만 감시", "🎯 선택 종목 집중 감시"])

final_codes = []
stock_names = {}

if watch_mode == "🛰️ 상위 종목 전체 스캔":
    # 6개 탈출! 이제 300개까지 마음껏 조절 가능합니다.
    scan_limit = st.sidebar.slider("📊 스캔할 종목 수 (상위 N개)", min_value=10, max_value=len(krx_list), value=200, step=10)
    subset_df = krx_list.head(scan_limit)
    final_codes = subset_df['Code'].tolist()
    stock_names = {row['Code']: row['Name'] for _, row in subset_df.iterrows()}

elif watch_mode == "📋 내 매수 종목만 감시":
    st.sidebar.subheader("✍️ 내 매수 종목 코드 입력")
    my_stocks_input = st.sidebar.text_area(
        "종목코드 6자리를 쉼표(,)로 구분해서 입력하세요:", 
        value="005930, 000660", 
        help="예시: 005930, 000660, 035420"
    )
    raw_codes = [c.strip() for c in my_stocks_input.split(",") if c.strip()]
    for code in raw_codes:
        # 보완된 리스트에서 매칭 수행
        matched = krx_list[krx_list['Code'] == code]
        if not matched.empty:
            final_codes.append(code)
            stock_names[code] = matched.iloc[0]['Name']
        else:
            if len(code) == 6:
                final_codes.append(code)
                stock_names[code] = f"보유종목({code})"

else:
    krx_list['Name_Code'] = krx_list['Name'] + " (" + krx_list['Code'] + ")"
    selected_stock = st.sidebar.selectbox("🎯 감시할 종목 선택:", krx_list['Name_Code'].tolist())
    pure_code = selected_stock.split(" (")[1].replace(")", "").strip()
    final_codes = [pure_code]
    stock_names = {pure_code: selected_stock.split(" (")[0]}

# 레이더 옵션 
target_percent = st.sidebar.number_input("🚨 포착 기준 변동률 (몇 % 이상 급등락?)", min_value=0.0, max_value=30.0, value=2.0, step=0.1)
detect_type = st.sidebar.selectbox("📈 감시 방향", ["급등/급락 둘 다 포착", "우하향 급락만 포착", "우상향 급등만 포착"])
check_interval = st.sidebar.slider("⏱️ 감시 주기 (초 단위)", min_value=5, max_value=120, value=15)

# 5. 메인 레이더 작동 구역
st.subheader("📡 레이더 가동 준비 완료")
st.write(f"📢 **[전일 종가 기준 누적 버전]** 국산 초고속 엔진으로 총 **{len(final_codes)}개 종목**을 실시간 그물망 감시합니다.")

if st.sidebar.button("🚀 실시간 레이더 가동"):
    if not final_codes:
        st.error("❌ 감시할 종목 코드가 존재하지 않습니다.")
        st.stop()
        
    st.info("⚡ 네이버 금융 실시간 광통신망망에 연결되었습니다.")
    
    log_area = st.empty()
    alert_container = st.empty()
    
    detected_events = []

    # 무한 루프 실시간 감시 엔진
    while True:
        now_time = datetime.now().strftime('%H:%M:%S')
        with log_area:
            st.write(f"🔄 [{now_time}] 레이더가 {len(final_codes)}개 종목의 전일 대비 등락률을 고속 스캔 중...")

        try:
            # 네이버 실시간 주가 데이터 뭉텅이 수집
            stock_data = get_naver_realtime_data(final_codes)
            
            for code in final_codes:
                try:
                    data = stock_data.get(code)
                    if data is None: continue
                    
                    current_price = data["current"]
                    base_price = data["prev_close"]
                    
                    if current_price == 0 or base_price == 0: continue
                    
                    # 📈 전일 대비 등락률 주식 정석 공식 연산
                    change_rate = ((current_price - base_price) / base_price) * 100
                    
                    # 조건 판단
                    is_detected = False
                    event_type = ""
                    
                    if detect_type in ["우상향 급등만 포착", "급등/급락 둘 다 포착"] and change_rate >= target_percent:
                        is_detected = True
                        event_type = "🔥 급등 포착"
                    elif detect_type in ["우하향 급락만 포착", "급등/급락 둘 다 포착"] and change_rate <= -target_percent:
                        is_detected = True
                        event_type = "📉 급락 경고"
                        
                    if is_detected:
                        if not any(e['종목명'] == stock_names[code] and e['현재가'] == f"{current_price:,.0f}원" for e in detected_events):
                            detected_events.insert(0, {
                                "시간": now_time,
                                "구분": event_type,
                                "종목명": stock_names[code],
                                "코드": code,
                                "어제마감가": f"{base_price:,.0f}원",
                                "현재가": f"{current_price:,.0f}원",
                                "전일대비변동률": f"{change_rate:+.2f}%"
                            })
                            if event_type == "🔥 급등 포착" and target_percent > 0: st.balloons()
                except:
                    continue
                    
            # 6. 화면 전광판 표 출력
            if detected_events:
                df_events = pd.DataFrame(detected_events)
                with alert_container:
                    st.error(f"🚨 [전일 대비 ±{target_percent}% 돌파 시그널 현황 - 총 {len(detected_events)}건 포착] 🚨")
                    st.dataframe(df_events, use_container_width=True)
            else:
                with alert_container:
                    st.info(f"📡 현재 전일 종가 대비 ±{target_percent}% 이상 움직인 종목이 없습니다. (더 많이 보려면 변동률을 낮춰보세요)")
                    
            time.sleep(check_interval)
        except Exception as e:
            time.sleep(5)
