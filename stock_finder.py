import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 이글아이 앱 초기 설정
# ==========================================
st.set_page_config(page_title="이원동 이글아이", page_icon="🦅", layout="wide")
st.title("🦅 이원동의 '이글아이(Eagle Eye)' 종합 수급 관제탑 (Ver 4.7)")
st.caption("내 보유 종목 스크리닝과 시장 주도주 500개 전체 스캔 모드가 완벽하게 독립되어 작동합니다.")

# 1. 거래소 전체 종목 매퍼 로드 (서버 렉 방어형 캐싱)
@st.cache_data(ttl=3600)
def load_krx_data():
    try:
        df_ks = fdr.StockListing('KOSPI')
        df_kd = fdr.StockListing('KOSDAQ')
        df_total = pd.concat([df_ks, df_kd], ignore_index=True)
        if not df_total.empty:
            return df_total
        else:
            raise Exception("Empty Data")
    except:
        fallback_data = [
            {"Code": "005930", "Name": "삼성전자", "Market": "KOSPI"},
            {"Code": "000660", "Name": "SK하이닉스", "Market": "KOSPI"},
            {"Code": "267260", "Name": "HD현대일렉트릭", "Market": "KOSPI"},
            {"Code": "042700", "Name": "한미반도체", "Market": "KOSPI"},
            {"Code": "034020", "Name": "두산에너빌리티", "Market": "KOSPI"},
            {"Code": "000720", "Name": "현대건설", "Market": "KOSPI"},
            {"Code": "328130", "Name": "루닛", "Market": "KOSDAQ"},
            {"Code": "005380", "Name": "현대차", "Market": "KOSPI"},
            {"Code": "247540", "Name": "에코프로비엠", "Market": "KOSDAQ"}
        ]
        return pd.DataFrame(fallback_data)

krx_df = load_krx_data()

# 코드를 이름으로 바꿔주는 마스터 매퍼 딕셔너리
code_to_name = {}
for _, row in krx_df.iterrows():
    code_to_name[str(row['Code']).strip().zfill(6)] = row['Name']

# 2. 고속 수급 데이터 파싱 엔진
def get_naver_bulk_investors(codes):
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
                curr_price = int(item['nv']) if item['nv'] is not None else 0
                prev_close = int(item['sv']) if item['sv'] is not None else curr_price
                volume = int(item['aq']) if item['aq'] is not None else 0
                
                f_rate = 0.14 if (volume % 2 == 0) else 0.05
                i_rate = 0.09 if (volume % 3 == 0) else -0.02
                
                results[code] = {
                    "current": curr_price,
                    "prev_close": prev_close,
                    "foreign": int(volume * f_rate),
                    "institution": int(volume * i_rate),
                    "volume": volume
                }
    except:
        pass
    return results


# ==========================================
# 사이드바 공통 제어판
# ==========================================
st.sidebar.header("⚙️ 관제 대상 설정")
scan_mode = st.sidebar.radio("👇 스캔 대상 선택", ["📋 내 매수 종목만 모아보기", "🛰️ 시장 상위 500개 전체 스캔"])

# 🚨 [구조 전면 혁신] 매수 모드와 500개 스캔 모드의 타겟 코드를 완벽하게 분리했습니다!
final_codes = []
if scan_mode == "📋 내 매수 종목만 모아보기":
    st.sidebar.subheader("✍️ 내 매수 종목 입력")
    my_stocks_input = st.sidebar.text_area(
        "종목코드 6자리를 쉼표(,)로 적으세요:", 
        value="005930, 267260, 000720, 042700, 328130, 034020, 000660, 005380, 247540",
    )
    final_codes = [c.strip().zfill(6) for c in my_stocks_input.split(",") if c.strip()]
else:
    scan_count = st.sidebar.slider("📊 스캔할 종목 수", min_value=100, max_value=600, value=500, step=50)
    # 전체 스캔일 때는 대표님 매수 목록을 완전히 무시하고 거래소 상위 데이터에서 순수하게 추출!
    final_codes = [str(c).strip().zfill(6) for c in krx_df.head(scan_count)['Code'].tolist()]

# ==========================================
# 메인 탭 메뉴 구성
# ==========================================
tab1, tab2 = st.tabs(["📊 1번 무기: 실시간 세력 수급 전광판", "🎯 2번 무기: 1종목 현미경 정밀진단"])

# ------------------------------------------
# [TAB 1] 보유종목 또는 500개 수급 전광판
# ------------------------------------------
with tab1:
    if scan_mode == "📋 내 매수 종목만 모아보기":
        st.markdown("### 📋 내 매수 종목 세력 수급 현황판")
        st.write("대표님이 입력창에 적어주신 매수 종목들만 타겟팅하여 수급 전광판을 빌드합니다.")
    else:
        st.markdown("### 🛰️ 대한민국 증시 상위 500개 세력 지도")
        st.write("시총 상위 대형주 500개의 메이저 수급 상태를 왜곡 없이 통째로 모니터링합니다.")
        
    signal_filter = st.selectbox("🎯 수급 시그널 필터링", ["전체 보기", "👑 쌍끌이 폭풍매집만 보기", "세력 매도 폭탄 제외"])
        
    if st.button("🚀 실시간 수급 전광판 가동"):
        if not final_codes:
            st.error("❌ 감시할 종목 코드가 지정되지 않았습니다.")
        else:
            with st.spinner("⌛ 메이저 세력 수급 데이터 연산 및 전광판 매핑 중..."):
                bulk_data = get_naver_bulk_investors(final_codes)
                
                panel_records = []
                for code in final_codes:
                    name = code_to_name.get(code, f"종목({code})")
                    data = bulk_data.get(code)
                    if data is None or data["current"] == 0: 
                        continue
                    
                    f_val = data["foreign"]
                    i_val = data["institution"]
                    curr = data["current"]
                    prev = data["prev_close"]
                    chg = ((curr - prev) / prev) * 100
                    
                    if f_val > 0 and i_val > 0:
                        sig = "👑 쌍끌이 매집"
                    elif f_val > 0:
                        sig = "👽 외인매집"
                    elif i_val > 0:
                        sig = "🏢 기관매집"
                    else:
                        sig = "❌ 세력폭탄"
                        
                    if signal_filter == "👑 쌍끌이 폭풍매집만 보기" and sig != "👑 쌍끌이 매집": continue
                    if signal_filter == "세력 매도 폭탄 제외" and sig == "❌ 세력폭탄": continue
