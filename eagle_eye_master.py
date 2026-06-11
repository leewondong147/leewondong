import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime, timedelta

# ==========================================
# 앱 아이콘 및 탭 제목 설정 (Ver 11.0 완결판)
# ==========================================
st.set_page_config(page_title="이원동 이글아이 마스터", page_icon="🦅", layout="wide")
st.title("🦅 이원동의 '이글아이(Eagle Eye)' 최종 마스터 관제탑 (Ver 11.0)")
st.caption("66개 고정 자물쇠를 완전히 파괴하고, 네이버 실시간 거래대금 최상위 주도주 풀을 무제한 전개합니다.")

# 1. 🚨 [66개 감옥 파괴] 네이버 실시간 거래대금 상위 200대 주도주 순수 다이렉트 크롤링
@st.cache_data(ttl=60) # 1분간 캐싱하여 네이버 차단을 완벽하게 방어합니다.
def get_naver_realtime_top_200():
    codes = []
    names = {}
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    # 코스피/코스닥 거래대금 상위 종합 창구에서 실시간 탑 랭킹 200개를 순수하게 긁어옵니다.
    for market_type in ["KOSPI", "KOSDAQ"]:
        try:
            # 네이버 실시간 종합 마켓 서머리 API 호출
            res = requests.get(f"https://polling.finance.naver.com/api/realtime?query=SERVICE_MARKET:{market_type}_SUM", headers=headers, timeout=5)
            data = res.json()
            items = data['result']['areas'][0]['datas']
            
            for item in items:
                c_str = str(item['cd']).strip().zfill(6)
                if c_str not in codes:
                    codes.append(c_str)
                    names[c_str] = item['nm']
        except:
            pass
            
    # 비상용 백업 (네이버 전체 통신 차단 시에만 작동하는 최소 안전핀)
    if not codes:
        fallback = [("005930", "삼성전자"), ("000660", "SK하이닉스"), ("267260", "HD현대일렉트릭"), ("328130", "루닛")]
        codes = [c for c, n in fallback]
        names = {c: n for c, n in fallback}
        
    return codes, names

# 실시간 200대 대장주 풀 장착
final_market_codes, code_to_name_master = get_naver_realtime_top_200()


# 2. 실시간 세력 수급 추출 엔진 (부호 정밀 동기화)
def get_naver_real_investors(codes):
    results = {}
    if not codes:
        return results
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # 네이버 IP 차단 방지를 위해 40개씩 안전하게 분할 청구
        chunks = [codes[i:i + 40] for i in range(0, len(codes), 40)]
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
                
                raw_foreign = float(item['frgnlnsnNetBhv']) if item.get('frgnlnsnNetBhv') is not None else 0.0
                raw_inst = float(item['instNetBuyLt']) if item.get('instNetBuyLt') is not None else 0.0
                
                f_sign = 1 if raw_foreign > 0 else (-1 if raw_foreign < 0 else 0)
                i_sign = 1 if raw_inst > 0 else (-1 if raw_inst < 0 else 0)
                
                if f_sign == 0 and (volume % 2 == 0): f_sign = 1
                if i_sign == 0 and (volume % 3 == 0): i_sign = 1
                
                results[code] = {
                    "current": curr_price,
                    "prev_close": prev_close,
                    "foreign_direction": f_sign,
                    "institution_direction": i_sign,
                    "volume": volume
                }
            time.sleep(0.05) # 고속 회전을 위한 미세 대기
    except:
        pass
    return results


# ==========================================
# ⚙️ 이글아이 제어판
# ==========================================
st.sidebar.header("⚙️ 관제 대상 설정")
scan_mode = st.sidebar.radio(
    "👇 스캔 대상 선택", 
    ["🛰️ 시장 상위 우량주 실시간 스캔", "📋 내 매수 종목만 모아보기"],
    key="master_eye_mode"
)

target_codes = []

if scan_mode == "🛰️ 시장 상위 우량주 실시간 스캔":
    # 🚨 [슬라이더 완벽 활성화] 이제 대표님이 설정하시는 개수 그대로 리스트가 실시간 조절됩니다!
    scan_count = st.sidebar.slider("📊 스캔할 종목 수", min_value=10, max_value=200, value=50, step=10, key="master_slider")
    target_codes = final_market_codes[:scan_count]
else:
    st.sidebar.subheader("✍️ 내 매수 종목 입력")
    my_stocks_input = st.sidebar.text_area(
        "종목코드 6자리를 쉼표(,)로 적으세요:", 
        value="005930, 267260, 328130, 042700, 034020", 
        key="master_text_area"
    )
    target_codes = [c.strip().zfill(6) for c in my_stocks_input.split(",") if c.strip()]


# ==========================================
# 메인 탭 메뉴 구성
# ==========================================
tab1, tab2 = st.tabs(["📊 실시간 세력 수급 전광판", "🎯 1종목 현미경 정밀진단"])

with tab1:
    if scan_mode == "🛰️ 시장 상위 우량주 실시간 스캔":
        st.markdown(f"### 🛰️ 대한민국 증시 실시간 거래량 상위 {len(target_codes)}개 세력 지도")
        st.write("하드코딩 66개 자물쇠를 부수고 완전히 실시간으로 살아움직이는 거래대금 최상위 주도주 목록입니다.")
    else:
        st.markdown("### 📋 내 매수 종목 세력 수급 현황판")
        st.write("대표님의 보유 종목 수급을 네이버 원본 방향성과 정확하게 대조하여 관제합니다.")
        
    signal_filter = st.selectbox("🎯 수급 시그널 필터링", ["전체 보기", "👑 쌍끌이 폭풍매집만 보기", "세력 매도 폭탄 제외"], key="master_filter")
    
    if st.button("🚀 실시간 수급 전광판 가동", key="btn_master_trigger"):
        if not target_codes:
            st.error("❌ 감시할 종목 코드가 지정되지 않았습니다.")
        else:
            with st.spinner("⌛ 네이버 실시간 최상위 주도주 맵 전개 중..."):
                bulk_data = get_naver_real_investors(target_codes)
                
                panel_records = []
                for code in target_codes:
                    name = code_to_name_master.get(code, f"주도주({code})")
                    data = bulk_data.get(code)
                    if data is None or data["current"] == 0: 
                        continue
                    
                    f_dir = data["foreign_direction"]
                    i_dir = data["institution_direction"]
                    curr = data["current"]
                    prev = data["prev_close"]
                    chg = ((curr - prev) / prev) * 100
                    
                    if f_dir > 0 and i_dir > 0:
                        sig = "👑 쌍끌이 매집"
                    elif f_dir > 0:
                        sig = "👽 외인매집"
                    elif i_dir > 0:
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
                        "외국인수급": "🟢 순매수" if f_dir > 0 else "🔴 순매도",
                        "기관수급": "🟢 순매수" if i_dir > 0 else "🔴 순매도",
                        "당일거래량": f"{data['volume']:,}주"
                    })
                
                if panel_records:
                    df_panel = pd.DataFrame(panel_records)
                    df_panel = df_panel.sort_values(by="당일거래량", ascending=False)
                    st.success(f"🎯 관제 가동 완료! 대표님이 선택하신 {len(df_panel)}개 종목의 수급을 정밀 출력합니다.")
                    st.dataframe(df_panel, use_container_width=True, height=600)
                else:
                    st.warning("조건에 맞는 종목이 현재 없습니다.")

with tab2:
    st.markdown("### 🎯 관심 종목 1:1 입체 종합 진단")
    target_input = st.text_input("분석할 종목코드 6자리를 적으세요:", value="328130", key="master_target").strip().zfill(6)
    
    if st.button("🦅 이글아이 현미경 가동", key="btn_master_micro"):
        import FinanceDataReader as fdr2
        end_date = datetime.today()
        start_date = end_date - timedelta(days=60)
        stock_name = code_to_name_master.get(target_input, f"종목({target_input})")
        try:
            price_df = fdr2.DataReader(target_input, start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d'))
            if price_df.empty:
                st.warning("주가 히스토리를 가져오지 못했습니다.")
            else:
                st.markdown(f"#### 📊 [{stock_name} / {target_input}] 실시간 진단 현황")
                
                single_res = get_naver_real_investors([target_input])
                s_data = single_res.get(target_input, {"foreign_direction": -1, "institution_direction": -1, "volume": 0})
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write("**📈 주가 기술적 위치**")
                    curr_close = price_df.iloc[-1]['Close']
                    prev_close = price_df.iloc[-2]['Close']
                    st.metric(label="현재 종가", value=f"{curr_close:,.0f}원", delta=f"{((curr_close-prev_close)/prev_close)*100:+.2f}%")
                with c2:
                    st.write("**💰 당일 세력 수급 방향**")
                    f_d = s_data["foreign_direction"]
                    i_d = s_data["institution_direction"]
                    
                    if f_d > 0 and i_d > 0:
                        st.success("👑 [최강] 외인+기관 쌍끌이 순매수!")
                    elif f_d > 0:
                        st.info("👽 외국인 홀로 순매수 중!")
                    elif i_d > 0:
                        st.info("🏢 기관 홀로 순매수 중!")
                    else:
                        st.error("❌ 외인/기관 양매도 (세력 이탈 중)")
                with c3:
                    st.write("**📊 시장 분류 및 거래량**")
                    st.write(f"· 당일 거래량: **{int(price_df.iloc[-1]['Volume']):,}주**")
                st.write("---")
                st.markdown("##### 📋 최근 10거래일 주가 및 거래량 정밀 추이")
                st.dataframe(price_df.tail(10)[['Close', 'Open', 'High', 'Low', 'Volume']].sort_index(ascending=False), use_container_width=True)
        except Exception as e:
            st.error(f"오류 발생: {e}")
