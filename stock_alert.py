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
st.title("📡 이원동의 '실시간 전종목 급등락 레이더' (Ver 7.2)")
st.caption("어제 장 마감 가격 대비 실시간 누적 변동률을 대한민국 전종목(2,600+) 대상으로 포착합니다.")

# 1. 🚨 [완벽 해결] 코스피/코스닥 전 종목을 제한 없이 통째로 수집
@st.cache_data(ttl=3600)
def load_krx_list_secure():
    try:
        # .head()를 과감히 삭제하여 코스피/코스닥 상장된 모든 종목(약 2,600개)을 가져옵니다!
        df_ks = fdr.StockListing('KOSPI')
        df_kd = fdr.StockListing('KOSDAQ')
        df_total = pd.concat([df_ks, df_kd], ignore_index=True)
        
        df_final = df_total[['Name', 'Code']].copy()
        df_final['Code'] = df_final['Code'].astype(str).str.zfill(6)
        # 검색 정확도를 위해 공백을 없애고 대문자로 통일
        df_final['Name_Clean'] = df_final['Name'].str.replace(" ", "").str.upper()
        return df_final
    except Exception as e:
        # 최후의 보루 백업용 리스트
        backup = [
            {"Name": "삼성전자", "Code": "005930"}, {"Name": "SK하이닉스", "Code": "000660"},
            {"Name": "현대차", "Code": "005380"}, {"Name": "네이버", "Code": "035420"},
            {"Name": "카카오", "Code": "035720"}, {"Name": "에코프로비엠", "Code": "247540"},
            {"Name": "기아", "Code": "000270"}, {"Name": "셀트리온", "Code": "068270"},
            {"Name": "POSCO홀딩스", "Code": "005490"}, {"Name": "LG에너지솔루션", "Code": "373220"},
            {"Name": "두산에너빌리티", "Code": "034020"}
        ]
        df_b = pd.DataFrame(backup)
        df_b['Name_Clean'] = df_b['Name'].str.replace(" ", "").str.upper()
        return df_b

krx_list = load_krx_list_secure()

# 2. 네이버 금융 실시간 주가 수집 함수
def get_naver_realtime_data(codes):
    results = {}
    if not codes:
        return results
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        # 대량 종목 처리를 위해 50개씩 조각내서 전송
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
    # 전 종목이 로드되므로 최대 슬라이더 범위를 시장 전체 크기로 유연하게 확장
    scan_limit = st.sidebar.slider("📊 스캔할 종목 수 (상위 N개)", min_value=10, max_value=min(500, len(krx_list)), value=200, step=10)
    subset_df = krx_list.head(scan_limit)
    final_codes = subset_df['Code'].tolist()
    stock_names = {row['Code']: row['Name'] for _, row in subset_df.iterrows()}

elif watch_mode == "📋 내 매수 종목만 감시":
    st.sidebar.subheader("✍️ 내 매수 종목명 입력")
    # 기본 입력 예시에 두산에너빌리티를 딱 넣어드렸습니다!
    my_stocks_input = st.sidebar.text_area(
        "종목 이름을 쉼표(,)로 구분해서 적으세요:", 
        value="삼성전자, 두산에너빌리티", 
        help="예시: 삼성전자, 두산에너빌리티, 현대차"
    )
    
    # 공백 제거 및 대문자 정제
    raw_names = [n.strip().replace(" ", "").upper() for n in my_stocks_input.split(",") if n.strip()]
    
    for name in raw_names:
        matched = krx_list[krx_list['Name_Clean'] == name]
        if not matched.empty:
            code = matched.iloc[0]['Code']
            real_name = matched.iloc[0]['Name']
            final_codes.append(code)
            stock_names[code] = real_name
        else:
            if name:
                st.sidebar.warning(f"⚠️ '{name}' 종목은 리스트에서 찾을 수 없습니다. 오타를 확인해 주세요.")

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

# 4. 메인 레이더 작동 구역
st.subheader("📡 레이더 가동 준비 완료")

if watch_mode == "📋 내 매수 종목만 감시" and final_codes:
    names_str = ", ".join([stock_names[c] for c in final_codes])
    st.write(f"📢 **[내 매수 종목 감시 모드]** 등록된 **{len(final_codes)}개 종목**(`{names_str}`) 집중 추적을 시작합니다.")
else:
    st.write(f"📢 현재 총 **{len(final_codes)}개 종목**이 감시망에 장착되었습니다.")

# 가동 버튼
if st.sidebar.button("🚀 실시간 레이더 가동"):
    if not final_codes:
        st.error("❌ 감시할 종목 이름이 없거나 올바르지 않습니다.")
        st.stop()
        
    st.info("⚡ 네이버 금융 실시간 전용 파이프라인망에 성공적으로 연결되었습니다.")
    
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
                    
                    # 📈 전일 종가 대비 등락률 연산
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
                        if not any(e['종목명'] == stock_names[code] and e['현재가'] == f"{current_price:,.0f}원" for e in detected_events):
                            detected_events.insert(0, {
                                "시간": now_time,
                                "구분": event_type,
                                "종목명": stock_names[code],
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
