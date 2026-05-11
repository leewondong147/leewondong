import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import re
import io

# ==========================================
# 앱 아이콘 및 탭 제목 설정
# ==========================================
st.set_page_config(
    page_title="이글아이 V6.0 (수급 완전 정복)", 
    page_icon="🦅", 
    layout="wide"
)

@st.cache_data
def load_stock_list():
    try:
        ks = fdr.StockListing('KOSPI').head(300)
        kd = fdr.StockListing('KOSDAQ').head(200)
        df = pd.concat([ks, kd], ignore_index=True)
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        return pd.DataFrame()

def get_price_data(code, start_date):
    try:
        df = fdr.DataReader(code, start_date)
        if not df.empty:
            df = df[df['Volume'] > 0]
        return df
    except:
        return pd.DataFrame()

def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://finance.naver.com/item/main.naver?code={code}'
    }
    try:
        time.sleep(0.1) 
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr'
        
        if res.status_code != 200:
            return pd.DataFrame(), f"네이버 서버 차단 (HTTP 상태코드 {res.status_code})"
            
        html = res.text
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.IGNORECASE | re.DOTALL)
        
        results = []
        for row in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.IGNORECASE | re.DOTALL)
            if len(tds) >= 7:
                clean_tds = [re.sub(r'<[^>]+>', '', td).replace('&nbsp;', '').strip() for td in tds]
                date_str = clean_tds[0]
                
                if re.match(r'^\d{4}\.\d{2}\.\d{2}$', date_str):
                    inst_str = clean_tds[5].replace(',', '').replace('+', '')
                    forgn_str = clean_tds[6].replace(',', '').replace('+', '')
                    
                    try:
                        results.append({
                            '날짜': date_str,
                            '외국인': int(forgn_str),
                            '기관합계': int(inst_str)
                        })
                    except:
                        pass
                        
        df = pd.DataFrame(results)
        
        if not df.empty:
            return df, "정상 처리됨"
        else:
            return pd.DataFrame(), "수급 표 텍스트를 찾을 수 없음 (데이터 없음)"
            
    except Exception as e:
        return pd.DataFrame(), f"에러 발생: {str(e)}"

def count_consecutive(series, is_buy=True):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if (is_buy and val > 0) or (not is_buy and val < 0): count += 1
        else: break
    return count

krx_list = load_stock_list()

st.title("🦅 이글아이 V6.0 (수급/이격도/거래대금 완전체)")

tab1, tab2 = st.tabs(["🔍 1:1 정밀 진단", "📊 내 맘대로 커스텀 스캔"])

# ==========================================
# 탭 1: 정밀 진단
# ==========================================
with tab1:
    st.subheader("🔎 종목 진단 (최종 지표 및 수급 상세)")
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        selected_stock = st.selectbox("리스트에서 선택:", ["직접 입력"] + krx_list['Name_Code'].tolist())
    with col_input2:
        direct_code = st.text_input("또는 코드 직접 입력:", placeholder="예: 389650")

    final_code = direct_code if direct_code else (selected_stock.split('(')[1].replace(')', '') if selected_stock != "직접 입력" else "")

    if st.button("🚀 정밀 분석 시작") and final_code:
        with st.spinner(f"[{final_code}] 데이터 분석 중..."):
            start_date = (datetime.today() - timedelta(days=2000)).strftime('%Y-%m-%d')
            df = get_price_data(final_code, start_date)
            
            if not df.empty and len(df) > 200:
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
                df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = df['EMA12'] - df['EMA26']
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                
                m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df = m_df.dropna()
                
                inv_df, inv_msg = get_naver_investor_data(final_code)
                
                f_buy = count_consecutive(inv_df['외국인'], True) if not inv_df.empty else 0
                i_buy = count_consecutive(inv_df['기관합계'], True) if not inv_df.empty else 0

                st.subheader(f"📊 종목코드 [{final_code}] 분석 리포트")
                
                # 양매도 경고 로직
                if not inv_df.empty:
                    f_today = inv_df.iloc[0]['외국인']
                    i_today = inv_df.iloc[0]['기관합계']
                    if f_today < 0 and i_today < 0:
                        st.error(f"🚨 **[위험 경보]** 최근 거래일 기준 외국인({f_today:,}주)과 기관({i_today:,}주)의 강력한 양매도가 포착되었습니다!")

                st.line_chart(m_df[['Close', 'MA10']].rename(columns={'Close':'종가','MA10':'10월선'}))
                
                if len(m_df) >= 2:
                    curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                    curr_price = df['Close'].iloc[-1]
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write("**📈 장기 추세**")
                        if curr_price >= curr_m['MA10']: st.success(f"✅ 10MA 위")
                        else: st.error(f"❌ 10MA 아래")
                    with c2:
                        st.write("**💰 세력 수급 요약**")
                        if not inv_df.empty:
                            if f_buy > 0 or i_buy > 0: st.info(f"🔥 매수(외:{f_buy}/기:{i_buy})")
                            else: st.write("뚜렷한 수급 없음")
                        else: st.warning("수급 확인 불가")
                    with c3:
                        st.write("**🌳 일봉 상태**")
                        if curr_price >= ma20: st.success("✅ 20일선 위 지지")
                        else: st.warning("❌ 20일선 이탈")

                    st.write("---")
                    c4, c5 = st.columns(2)
                    with c4:
                        st.write("**📊 거래량 폭발**")
                        if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 1.5배 이상 폭발")
                        else: st.write("❌ 변화 미비")
                    with c5:
                        st.write("**🚀 일봉 MACD**")
                        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: st.success("✅ MACD 상승")
                        else: st.warning("❌ MACD 하락")

                    st.write("---")
                    st.subheader("📋 최근 10일 외국인/기관 수급 상세 현황 (단위: 주)")
                    
                    if not inv_df.empty:
                        display_df = inv_df.head(10).copy()
                        display_df['외국인'] = display_df['외국인'].apply(lambda x: f"{int(x):,}")
                        display_df['기관합계'] = display_df['기관합계'].apply(lambda x: f"{int(x):,}")
                        st.dataframe(display_df, use_container_width=True)
                    else:
                        st.error(f"🚨 수급 표를 불러오지 못했습니다. 원인 ➔ [ {inv_msg} ]")
            else:
                st.error("데이터가 부족합니다.")

# ==========================================
# 탭 2: 커스텀 스캔
# ==========================================
with tab2:
    st.subheader("🖥️ 내 맘대로 조절하는 커스텀 스캐너")
    
    col_opt1, col_opt2, col_opt3 = st.columns(3)
    with col_opt1:
        vol_multiplier = st.slider("📊 거래량 (20일 평균의 몇 배?)", min_value=0.5, max_value=3.0, value=1.0, step=0.1)
    with col_opt2:
        ma20_limit = st.slider("🎯 20일선 이격도 (몇 % 이내?)", min_value=1.0, max_value=20.0, value=8.0, step=0.5)
    with col_opt3:
        min_trade_val = st.slider("💸 당일 거래대금 (억원 이상)", min_value=10, max_value=2000, value=100, step=50)
        
    col_chk1, col_chk2 = st.columns(2)
    with col_chk1:
        require_sugeub = st.checkbox("🔥 외인/기관 매수 필수", value=False)
    with col_chk2:
        exclude_double_sell = st.checkbox("🚫 당일 강력 양매도 종목 제외", value=True)

    if st.button("🌟 커스텀 스캔 시작"):
        results = []
        p_bar = st.progress(0)
        status_text = st.empty()
        
        start_date = (datetime.today() - timedelta(days=2000)).strftime('%Y-%m-%d')
        naver_fail_count = 0 
        last_error_msg = ""
        
        for i, (idx, row) in enumerate(krx_list.iterrows()):
            p_bar.progress((i+1)/len(krx_list))
            status_text.text(f"⏳ [{row['Name']}] 설정하신 조건으로 검색 중...")
            try:
                df = get_price_data(row['Code'], start_date)
                if df.empty or len(df) < 250: continue 
                
                curr_price = df['Close'].iloc[-1]
                curr_vol = df['Volume'].iloc[-1]
                curr_trade_val_eok = (curr_price * curr_vol) / 100000000 
                
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                diff_percent = abs(curr_price - ma20) / ma20 * 100 
                
                avg_vol_20d = df['Volume'].rolling(20).mean().iloc[-2]
                
                df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
                df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = df['EMA12'] - df['EMA26']
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                curr_macd = df['MACD'].iloc[-1]
                curr_signal = df['Signal'].iloc[-1]
                
                m_df = df.resample('ME').agg({'Close': 'last'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df = m_df.dropna()
                
                if not m_df.empty:
                    curr_m_ma10 = m_df['MA10'].iloc[-1]
                    
                    # 7가지 기술적 분석 조건
                    cond1 = curr_price >= curr_m_ma10        
                    cond2 = curr_price >= ma20               
                    cond3 = curr_macd > curr_signal          
                    cond4 = avg_vol_20d >= 100000            
                    cond5 = curr_vol >= (avg_vol_20d * vol_multiplier)  
                    cond6 = diff_percent <= ma20_limit
                    cond7 = curr_trade_val_eok >= min_trade_val
                    
                    if cond1 and cond2 and cond3 and cond4 and cond5 and cond6 and cond7:
                        inv_df, msg = get_naver_investor_data(row['Code'])
                        
                        # 양매도 제외 로직
                        if exclude_double_sell and not inv_df.empty:
                            if inv_df.iloc[0]['외국인'] < 0 and inv_df.iloc[0]['기관합계'] < 0:
                                continue 
                                
                        # 💡 [정확한 3일 합산 로직]: 오늘 포함 최근 3거래일(맨 위 3줄) 합산
                        if not inv_df.empty:
                            f_sum = inv_df.head(3)['외국인'].sum()
                            i_sum = inv_df.head(3)['기관합계'].sum()
                        else:
                            f_sum, i_sum = 0, 0
                            naver_fail_count += 1
                            last_error_msg = msg
                            
                        # 수급 필수 조건 확인
                        if require_sugeub and f_sum <= 0 and i_sum <= 0:
                            continue
                            
                        # 💡 단위 '주' 명시적 추가
                        sugeub_text = f"외:{int(f_sum):,}주 / 기:{int(i_sum):,}주" if not inv_df.empty else "미확인"
                        
                        results.append({
                            '시장':row['Market'], '종목명':row['Name'], '코드':row['Code'], 
                            '현재가':int(curr_price), 
                            '거래대금': f"{int(curr_trade_val_eok):,}억",
                            '20일선_이격도': f"{round(diff_percent, 2)}%", 
                            '폭발비율': f"{round(curr_vol/avg_vol_20d, 1)}배",
                            '확정수급(3일)': sugeub_text
                        })
            except: continue
            
        status_text.success(f"✅ 스캔 완료! 설정 조건에 맞는 {len(results)}개 종목 발견")
        
        if require_sugeub and naver_fail_count > 0:
            st.error(f"🚨 수급을 확인하지 못한 종목이 있습니다. 에러 원인 ➔ [ {last_error_msg} ]")
            
        if results:
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                res_df.to_excel(writer, index=False)
            st.download_button("📥 맞춤형 리스트 다운로드", output.getvalue(), "EagleEye_Custom_Scan.xlsx")
