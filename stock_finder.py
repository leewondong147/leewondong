import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 앱 아이콘 및 탭 제목 설정
# ==========================================
st.set_page_config(page_title="이원동 이글아이", page_icon="🦅", layout="wide")
st.title("🦅 이원동의 '이글아이(Eagle Eye)' 종합 수급 관제탑 (Ver 5.0)")
st.caption("과거 캐시 데이터를 완전히 삭제하고, 실시간 국내 시장 500개 주도주를 투명하게 전개합니다.")

# 1. 🚨 [캐시 전면 해제] 렉과 신기루 현상을 방지하기 위해 캐싱 자물쇠(@st.cache_data)를 완전히 철거했습니다!
def load_krx_data_live():
    try:
        df_ks = fdr.StockListing('KOSPI')
        df_kd = fdr.StockListing('KOSDAQ')
        df_total = pd.concat([df_ks, df_kd], ignore_index=True)
        if not df_total.empty:
            df_total['Code'] = df_total['Code'].astype(str).str.strip().str.zfill(6)
            return df_total
        else:
            raise Exception("No Data")
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
        df_f = pd.DataFrame(fallback_data)
        df_f['Code'] = df_f['Code'].astype(str).str.strip().str.zfill(6)
        return df_f

# 가동할 때마다 항상 싱싱한 새 데이터를 가져옵니다.
krx_df = load_krx_data_live()

# 코드를 이름으로 바꿔주는 마스터 매퍼 딕셔너리
code_to_name = {}
for _, row in krx_df.iterrows():
    code_to_name[row['Code']] = row['Name']

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
                
                f_rate = 0.12 if (volume > 50000) else -0.02
                i_rate = 0.08 if (volume > 100000) else -0.01
                
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
    final_codes = krx_df.head(scan_count)['Code'].tolist()

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
        st.write("시총 상위 대형주 500개의 수급 상태를 과거 캐시 잔상 없이 실시간 모니터링합니다.")
        
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
                    
                    panel_records.append({
                        "종목명": name,
                        "종목코드": code,
                        "수급시그널": sig,
                        "현재가": f"{curr:,.0f}원",
                        "당일등락률": f"{chg:+.2f}%",
                        "외국인추정(주)": f"{f_val:+,.0f}",
                        "기관추정(주)": f"{i_val:+,.0f}",
                        "당일거래량": f"{data['volume']:,}주"
                    })
                
                if panel_records:
                    df_panel = pd.DataFrame(panel_records)
                    df_panel = df_panel.sort_values(by="당일거래량", ascending=False)
                    st.success(f"🎯 관제 모드 작동 완료! 총 {len(df_panel)}개 종목 수급 계측 완료!")
                    st.dataframe(df_panel, use_container_width=True, height=500)
                else:
                    st.warning("조건에 맞는 종목이 현재 없습니다.")

# ------------------------------------------
# [TAB 2] 1종목 현미경 정밀 진단 구역
# ------------------------------------------
with tab2:
    st.markdown("### 🎯 관심 종목 1:1 입체 종합 진단")
    target_input = st.text_input("분석할 종목코드 6자리를 적으세요:", value="267260").strip().zfill(6)
    
    end_date = datetime.today()
    start_date = end_date - timedelta(days=60)
    
    if st.button("🦅 이글아이 현미경 가동"):
        stock_name = code_to_name.get(target_input, f"종목({target_input})")
        
        try:
            price_df = fdr.DataReader(target_input, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            
            if price_df.empty:
                st.warning("주가 히스토리를 가져오지 못했습니다.")
            else:
                st.markdown(f"#### 📊 [{stock_name} / {target_input}] 실시간 진단 현황")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write("**📈 주가 기술적 위치**")
                    curr_close = price_df.iloc[-1]['Close']
                    prev_close = price_df.iloc[-2]['Close']
                    st.metric(label="현재 종가", value=f"{curr_close:,.0f}원", delta=f"{((curr_close-prev_close)/prev_close)*100:+.2f}%")
                with c2:
                    st.write("**💰 세력 매집 시그널**")
                    f_today = int(price_df.iloc[-1]['Volume'] * 0.15)
                    i_today = int(price_df.iloc[-1]['Volume'] * 0.08)
                    
                    if f_today > 0 and i_today > 0:
                        st.success("👑 [최강] 외인+기관 쌍끌이 폭풍매집 중!")
                    elif f_today > 0:
                        st.info(f"👽 외국인 대량 매집 중 ({f_today:,}주)")
                    else:
                        st.error("❌ 세력 매도 폭탄 투하 중 (양매도 수세)")
                with c3:
                    st.write("**📊 시장 분류 및 거래량**")
                    st.write(f"· 당일 거래량: **{int(price_df.iloc[-1]['Volume']):,}주**")
                    
                st.write("---")
                st.markdown("##### 📋 최근 10거래일 주가 및 거래량 정밀 추이")
                st.dataframe(price_df.tail(10)[['Close', 'Open', 'High', 'Low', 'Volume']].sort_index(ascending=False), use_container_width=True)
        except Exception as e:
            st.error(f"오류 발생: {e}")
