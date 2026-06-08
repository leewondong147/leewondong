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
st.title("📡 이원동의 '실시간 전종목 급등락 레이더' (Ver 9.0)")
st.caption("6자리 종목코드로 정확하게 입력하고, 포착 결과는 친숙한 '한글 종목명'으로 확인합니다.")

# 1. 거래소 전종목 코드-이름 매칭용 마스터 데이터 로드
@st.cache_data(ttl=3600)
def load_krx_mapper():
    try:
        # 코스피/코스닥 전 종목 수집
        df_ks = fdr.StockListing('KOSPI')
        df_kd = fdr.StockListing('KOSDAQ')
        df_total = pd.concat([df_ks, df_kd], ignore_index=True)
        
        # 코드와 이름 매칭용 딕셔너리 생성
        mapper = {}
        for _, row in df_total.iterrows():
            code = str(row['Code']).strip().zfill(6)
            mapper[code] = row['Name']
            
        # 대표님 주력주 치트키 백업 (네트워크 렉 대비)
        cheat_sheet = {
            "005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", 
            "000720": "현대건설", "267260": "HD현대일렉트릭", "042700": "한미반도체", 
            "328130": "루닛", "034020": "두산에너빌리티", "247540": "에코프로비엠"
        }
        # 백업 데이터 합성
        for k, v in cheat_sheet.items():
            if k not in mapper:
                mapper[k] = v
        return mapper, df_total
    except:
        # 최악의 경우 비상용 딕셔너리
        fallback = {
            "005930": "삼성전자", "000660": "SK하이닉스", "005380": "현대차", 
            "000720": "현대건설", "267260": "HD현대일렉트릭", "042700": "한미반도체", 
            "328130": "루닛", "034020": "두산에너빌리티", "247540": "에코프로비엠",
            "035420": "네이버", "035720": "카카오", "028260": "삼성물산"
        }
        return fallback, pd.DataFrame()

# 마스터 매퍼(딕셔너리) 구축
code_to_name_map, raw_df = load_krx_mapper()

# 2. 네이버 금융 실시간 주가 수집 함수
def get_naver_realtime_data(codes):
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
                
                results[code] = {
                    "current": current_price,
                    "prev_close": prev_close
                }
    except:
        pass
    return results

# 3. 제어판 (사이드바 설정)
st.sidebar.header("⚙️ 레이더 감시 설정")

watch_mode = st.sidebar.radio("👇 감시 모드 선택", ["🛰️ 상위 종목 전체 스캔", "📋 내 매수 종목만 감시", "🎯 선택 종목 집중 감시"])

final_codes = []
stock_names = {}

if watch_mode == "🛰️ 상위 종목 전체 스캔":
    # 전체 스캔용 개수 조절
    scan_limit = st.sidebar.slider("📊 스캔할 종목 수 (상위 N개)", min_value=10, max_value=300, value=200, step=10)
    if not raw_df.empty:
        subset_df = raw_df.head(scan_limit)
        for _, row in subset_df.iterrows():
            c = str(row['Code']).strip().zfill(6)
            final_codes.append(c)
            stock_names[c] = row['Name']
    else:
        # 백업 모드 시 기본 코드 적용
        final_codes = list(code_to_name_map.keys())[:scan_limit]
        stock_names = {c: code_to_name_map[c] for c in final_codes}

elif watch_mode == "📋 내 매수 종목만 감시":
    st.sidebar.subheader("✍️ 내 매수 종목코드 입력")
    # ⭐ [대표님 아이디어 적용] 이제 한글 말고 편리하고 정확한 6자리 숫자를 입력합니다!
    # 기본값으로 대표님의 지존 포트폴리오 5개 코드를 깔끔하게 넣어드렸습니다.
    # 순서대로: 삼성전자, HD현대일렉트릭, 현대건설, 한미반도체, 루닛, 두산에너빌리티
    my_stocks_input = st.sidebar.text_area(
        "종목코드 6자리를 쉼표(,)로 구분해서 적으세요:", 
        value="005930, 267260, 000720, 042700, 328130, 034020", 
        help="예시: 005930, 267260, 000720"
    )
    
    # 대표님이 입력하신 숫자 코드들 정제
    raw_codes = [c.strip().zfill(6) for c in my_stocks_input.split(",") if c.strip()]
    
    for code in raw_codes:
        # 입력된 코드가 마스터 맵에 존재하는지 확인하여 한글 이름 매칭
        if code in code_to_name_map:
            final_codes.append(code)
            stock_names[code] = code_to_name_map[code] # 코드를 바탕으로 한글명 셋팅!
        else:
            if len(code) == 6:
                final_codes.append(code)
                stock_names[code] = f"미등록코드({code})"

else: # 🎯 선택 종목 집중 감시
    if not raw_df.empty:
        raw_df['Name_Code'] = raw_df['Name'] + " (" + raw_df['Code'] + ")"
        selected_stock = st.sidebar.selectbox("🎯 감시할 종목 선택:", raw_df['Name_Code'].tolist())
        pure_code = selected_stock.split(" (")[1].replace(")", "").strip().zfill(6)
        final_codes = [pure_code]
        stock_names[pure_code] = selected_stock.split(" (")[0]
    else:
        final_codes = ["005930"]
        stock_names["005930"] = "삼성전자"

# 레이더 옵션
target_percent = st.sidebar.number_input("🚨 포착 기준 변동률 (몇 % 이상 급등락?)", min_value=0.0, max_value=30.0, value=2.0, step=0.1)
detect_type = st.sidebar.selectbox("📈 감시 방향", ["급등/급락 둘 다 포착", "우하향 급락만 포착", "우상향 급등만 포착"])
check_interval = st.sidebar.slider("⏱️ 감시 주기 (초 단위)", min_value=5, max_value=120, value=15)

# 4. 메인 레이더 작동 구역
st.subheader("📡 레이더 가동 준비 완료")

if watch_mode == "📋 내 매수 종목만 감시" and final_codes:
    names_str = ", ".join([stock_names[c] for c in final_codes])
    st.write(f"📢 **[내 매수 종목 감시 모드]** 입력된 **{len(final_codes)}개 코드**를 기반으로 오차 없이 감시망을 전개합니다.")
    st.info(f"🔍 추적 대상 한글 종목명 확인 ➔ [ {names_str} ]")
else:
    st.write(f"📢 현재 총 **{len(final_codes)}개 종목**이 실시간 전용 감시망에 장착되었습니다.")

# 가동 버튼
if st.sidebar.button("🚀 실시간 레이더 가동"):
    if not final_codes:
        st.error("❌ 감시할 종목 코드가 입력되지 않았습니다.")
        st.stop()
        
    st.info("⚡ 네이버 금융 실시간 전용 광통신망망에 안심 연결되었습니다.")
    
    log_area = st.empty()
    alert_container = st.empty()
    
    detected_events = []

    # 무한 루프 실시간 감시 엔진
    while True:
        now_time = datetime.now().strftime('%H:%M:%S')
        with log_area:
            st.write(f"🔄 [{now_time}] 레이더가 전일 대비 변동률을 실시간 연산 중...")

        try:
            stock_data = get_naver_realtime_data(final_codes)
            
            for code in final_codes:
                try:
                    data = stock_data.get(code)
                    if data is None: continue
                    
                    current_price = data["current"]
                    base_price = data["prev_close"]
                    
                    if current_price == 0 or base_price == 0: continue
                    
                    # 📈 전일 종가 대비 등락률 정석 연산
                    change_rate = ((current_price - base_price) / base_price) * 100
                    
                    is_detected = False
                    event_type = ""
                    
                    if detect_type in ["우상향 급등만 포착", "급등/급락 둘 다 포착"] and change_rate >= target_percent:
                        is_detected = True
                        event_type = "🔥 급등 포착"
                    elif detect_type in ["우하향 급락만 포착", "급등/급락 둘 다 포착"] and change_rate <= -target_percent:
                        is_detected = True
                        event_type = "📉 급락 경고"
                        
                    if is_detected:
                        # 🚨 [완벽 구현] 표에 누적 출력할 때는 코드를 가리고, 매핑된 한글 이름만 깔끔하게 던집니다!
                        if not any(e['종목명'] == stock_names[code] and e['현재가'] == f"{current_price:,.0f}원" for e in detected_events):
                            detected_events.insert(0, {
                                "시간": now_time,
                                "구분": event_type,
                                "종목명": stock_names[code],  # 지존의 한글 이름 출력 구역!
                                "어제마감가": f"{base_price:,.0f}원",
                                "현재가": f"{current_price:,.0f}원",
                                "전일대비변동률": f"{change_rate:+.2f}%"
                            })
                            if event_type == "🔥 급등 포착" and target_percent > 0: st.balloons()
                except:
                    continue
                    
            # 5. 화면 전광판 표 출력
            if detected_events:
                df_events = pd.DataFrame(detected_events)
                with alert_container:
                    st.error(f"🚨 [전일 대비 ±{target_percent}% 돌파 시그널 현황 - 총 {len(detected_events)}건 포착] 🚨")
                    st.dataframe(df_events, use_container_width=True)
            else:
                with alert_container:
                    st.info(f"📡 선택하신 매수 종목 중 전일 대비 ±{target_percent}% 이상 움직인 종목이 없습니다.")
                    
            time.sleep(check_interval)
        except Exception as e:
            time.sleep(5)
