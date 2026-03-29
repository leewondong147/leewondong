import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time

st.set_page_config(page_title="궁극의 스마트 주식 진단기 V2", layout="wide") # 화면을 넓게 쓰도록 'wide'로 변경!

# =====================================================================
# [엔진 1] 종목 리스트 (한국거래소 우회 통로 포함)
# =====================================================================
@st.cache_data
def load_stock_list():
    try:
        krx = fdr.StockListing('KRX')
        krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
        return krx
    except Exception:
        kospi_url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt'
        kosdaq_url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=kosdaqMkt'
        headers = {'User-Agent': 'Mozilla/5.0'}
        res_kospi = requests.get(kospi_url, headers=headers)
        res_kospi.encoding = 'euc-kr'
        kospi = pd.read_html(res_kospi.text, header=0)[0]
        res_kosdaq = requests.get(kosdaq_url, headers=headers)
        res_kosdaq.encoding = 'euc-kr'
        kosdaq = pd.read_html(res_kosdaq.text, header=0)[0]
        krx = pd.concat([kospi, kosdaq])
        krx = krx[['회사명', '종목코드']].rename(columns={'회사명': 'Name', '종목코드': 'Code'})
        krx['Code'] = krx['Code'].astype(str).str.zfill(6)
        krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
        return krx

# =====================================================================
# [엔진 2 & 3] 주가 데이터 및 네이버 수급 크롤링
# =====================================================================
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

@st.cache_data(ttl=3600, show_spinner=False)
def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res.encoding = 'euc-kr'
    try:
        dfs = pd.read_html(res.text)
        for df in dfs:
            cols = df.columns
            if isinstance(cols, pd.MultiIndex): cols = [''.join(c) for c in cols]
            else: cols = cols.astype(str)
            if any('날짜' in c for c in cols) and any('기관' in c for c in cols) and any('외국인' in c for c in cols):
                df.columns = cols
                df = df.dropna(subset=[cols[0]]) 
                date_col = [c for c in cols if '날짜' in c][0]
                inst_col = [c for c in cols if '기관' in c][0]
                forgn_col = [c for c in cols if '외국인' in c and '순매매' in c]
                forgn_col = forgn_col[0] if forgn_col else [c for c in cols if '외국인' in c][0]
                df = df[df[date_col] != '날짜'].reset_index(drop=True)
                for col in [inst_col, forgn_col]:
                    df[col] = df[col].astype(str).str.replace(',', '').str.replace('+', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                df = df.rename(columns={date_col: '날짜', inst_col: '기관합계', forgn_col: '외국인'})
                return df[['날짜', '외국인', '기관합계']]
    except Exception: pass
    return pd.DataFrame()

def count_consecutive_buys(series):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if val > 0: count += 1
        else: break
    return count

def count_consecutive_sells(series):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if val < 0: count += 1
        else: break
    return count

krx_list = load_stock_list()

st.title("🦅 궁극의 스마트 주식 진단기 V2")
st.write("월봉 10이평선, 수급, 거래량, MACD, 일봉 정배열까지 5가지 핵심 지표를 모두 분석합니다.")

tab1, tab2 = st.tabs(["🔍 5대 지표 정밀 진단", "🌟 황금 종목 자동 스캐너"])

# =====================================================================
# [탭 1] 5대 지표 정밀 진단
# =====================================================================
with tab1:
    default_index = krx_list[krx_list['Code'] == '005930'].index[0] if '005930' in krx_list['Code'].values else 0
    selected_stock = st.selectbox("분석할 종목명 검색:", krx_list['Name_Code'].tolist(), index=int(default_index))
    user_code = selected_stock.split('(')[1].replace(')', '')
    user_name = selected_stock.split(' (')[0]

    if st.button("🚀 정밀 진단 시작", key="btn_single"):
        status_msg = st.empty()
        status_msg.info(f"▶️ [{user_name}] 5대 지표를 심층 분석 중입니다...")
        
        # 💡 MACD 계산을 위해 넉넉하게 3년 치(1095일) 데이터를 가져옵니다.
        end_date = datetime.today()
        start_date_3yr = end_date - timedelta(days=1095)
        df = get_price_data(user_code, start_date_3yr.strftime('%Y-%m-%d'))
        
        # --- [지표 1] 일봉 정배열 확인 ---
        is_daily_aligned = False
        if not df.empty and len(df) > 60:
            daily_df = df.copy()
            daily_df['MA20'] = daily_df['Close'].rolling(window=20).mean()
            daily_df['MA60'] = daily_df['Close'].rolling(window=60).mean()
            last_day = daily_df.iloc[-1]
            if last_day['Close'] > last_day['MA20'] > last_day['MA60']:
                is_daily_aligned = True

        # --- 월봉 데이터 변환 및 [지표 2, 3, 4] 계산 ---
        monthly_df = pd.DataFrame()
        vol_surge = False
        macd_bull = False
        is_golden_cross = False
        is_dead_cross = False
        
        if not df.empty and len(df) >= 200:
            # 주가와 거래량을 같이 가져옵니다.
            monthly_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            
            # MACD 계산 (12개월, 26개월 지수이동평균)
            monthly_df['EMA12'] = monthly_df['Close'].ewm(span=12, adjust=False).mean()
            monthly_df['EMA26'] = monthly_df['Close'].ewm(span=26, adjust=False).mean()
            monthly_df['MACD'] = monthly_df['EMA12'] - monthly_df['EMA26']
            monthly_df['Signal'] = monthly_df['MACD'].ewm(span=9, adjust=False).mean()
            monthly_df = monthly_df.dropna()
            
            if len(monthly_df) >= 2:
                prev_m = monthly_df.iloc[-2]
                curr_m = monthly_df.iloc[-1]
                
                # 10이평선 돌파 여부
                is_golden_cross = prev_m['Close'] < prev_m['MA10'] and curr_m['Close'] > curr_m['MA10']
                is_dead_cross = prev_m['Close'] > prev_m['MA10'] and curr_m['Close'] < curr_m['MA10']
                
                # 거래량 1.5배 폭발 여부
                if prev_m['Volume'] > 0 and curr_m['Volume'] > (prev_m['Volume'] * 1.5):
                    vol_surge = True
                    
                # MACD 상승 추세 여부 (MACD가 Signal 위에 있는지)
                if curr_m['MACD'] > curr_m['Signal']:
                    macd_bull = True

        # --- [지표 5] 수급 분석 ---
        investor_df = get_naver_investor_data(user_code)
        f_buy, f_sell, i_buy, i_sell = 0, 0, 0, 0
        if not investor_df.empty:
            f_buy = count_consecutive_buys(investor_df['외국인'])
            f_sell = count_consecutive_sells(investor_df['외국인'])
            i_buy = count_consecutive_buys(investor_df['기관합계'])
            i_sell = count_consecutive_sells(investor_df['기관합계'])

        # --- 화면 출력 ---
        status_msg.empty()
        st.subheader(f"📊 {user_name} ({user_code}) 5대 지표 진단 결과")
        
        if not monthly_df.empty and len(monthly_df) >= 2:
            chart_df = monthly_df[['Close', 'MA10']].rename(columns={'Close': '월봉 종가', 'MA10': '10개월 이평선'})
            st.line_chart(chart_df)
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.write("**① 장기 추세 (월봉 10MA)**")
            if is_golden_cross: st.success("🔥 상향 돌파! (매수 신호)")
            elif is_dead_cross: st.error("❄️ 하향 이탈! (매도 신호)")
            else: st.info("돌파/이탈 없음")
            
            st.write("**② 세력 수급**")
            if f_buy > 0 or i_buy > 0: st.success(f"🔥 매수 중 (외인:{f_buy}일/기관:{i_buy}일)")
            elif f_sell > 0 or i_sell > 0: st.error(f"❄️ 매도 중 (외인:{f_sell}일/기관:{i_sell}일)")
            else: st.info("뚜렷한 수급 없음")
            
        with col2:
            st.write("**③ 거래량 폭발 (전월비 1.5배)**")
            if vol_surge: st.success("✅ 거래량 대폭발! (신뢰도 떡상)")
            else: st.write("❌ 평이한 거래량")
            
            st.write("**④ MACD (월봉 상승 에너지)**")
            if macd_bull: st.success("✅ MACD > Signal (상승 추세)")
            else: st.warning("❌ MACD 약세 (하락/조정)")
            
        with col3:
            st.write("**⑤ 단기 추세 (일봉 정배열)**")
            if is_daily_aligned: st.success("✅ 20일선 > 60일선 (단기 상승장)")
            else: st.warning("❌ 역배열 또는 혼조세")

# =====================================================================
# [탭 2] 상위 50개 황금 종목 자동 스캐너 (보조 지표 뱃지 추가!)
# =====================================================================
with tab2:
    st.write("시총 상위 50개 중 **[10이평선 돌파 + 수급]** 기본 조건을 통과한 종목을 찾고, 나머지 3개 보조 지표 합격 여부를 알려줍니다.")
    
    if st.button("🌟 궁극의 스캔 시작 (약 1분 소요)", key="btn_multi"):
        golden_stocks = []
        top_50 = krx_list.head(50) 
        p_bar = st.progress(0)
        p_text = st.empty()
        
        end_date = datetime.today()
        start_date_3yr = end_date - timedelta(days=1095)
        
        for i, (index, row) in enumerate(top_50.iterrows()):
            code = row['Code']
            name = row['Name']
            p_text.text(f"⏳ [{name}] 5대 지표 스캔 중... ({i+1}/50)")
            p_bar.progress((i + 1) / 50)
            
            try:
                df = get_price_data(code, start_date_3yr.strftime('%Y-%m-%d'))
                is_crossed, vol_surge, macd_bull, is_daily_aligned = False, False, False, False
                
                if not df.empty and len(df) >= 200:
                    # 일봉 정배열 체크
                    daily_df = df.copy()
                    daily_df['MA20'] = daily_df['Close'].rolling(window=20).mean()
                    daily_df['MA60'] = daily_df['Close'].rolling(window=60).mean()
                    if daily_df.iloc[-1]['Close'] > daily_df.iloc[-1]['MA20'] > daily_df.iloc[-1]['MA60']:
                        is_daily_aligned = True

                    # 월봉 체크
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(window=10).mean()
                    m_df['EMA12'] = m_df['Close'].ewm(span=12, adjust=False).mean()
                    m_df['EMA26'] = m_df['Close'].ewm(span=26, adjust=False).mean()
                    m_df['MACD'] = m_df['EMA12'] - m_df['EMA26']
                    m_df['Signal'] = m_df['MACD'].ewm(span=9, adjust=False).mean()
                    m_df = m_df.dropna()
                    
                    if len(m_df) >= 2:
                        prev_m, curr_m = m_df.iloc[-2], m_df.iloc[-1]
                        if prev_m['Close'] < prev_m['MA10'] and curr_m['Close'] > curr_m['MA10']:
                            is_crossed = True
                        if prev_m['Volume'] > 0 and curr_m['Volume'] > (prev_m['Volume'] * 1.5):
                            vol_surge = True
                        if curr_m['MACD'] > curr_m['Signal']:
                            macd_bull = True
                
                # 기본 조건(크로스) 통과 시 수급 확인
                if is_crossed:
                    time.sleep(0.3) 
                    inv_df = get_naver_investor_data(code)
                    if not inv_df.empty:
                        f_buy = count_consecutive_buys(inv_df['외국인'])
                        i_buy = count_consecutive_buys(inv_df['기관합계'])
                        
                        if f_buy > 0 or i_buy > 0:
                            golden_stocks.append({
                                '종목명': name,
                                '외인/기관(일)': f"{f_buy} / {i_buy}",
                                '거래량폭발': "✅" if vol_surge else "❌",
                                'MACD상승': "✅" if macd_bull else "❌",
                                '일봉정배열': "✅" if is_daily_aligned else "❌"
                            })
            except Exception: pass 

        p_text.empty()
        p_bar.empty()
        
        if len(golden_stocks) > 0:
            st.success(f"🎉 스캔 완료! 상위 50개 중 **{len(golden_stocks)}개**의 1차 합격 종목을 찾았습니다.")
            st.info("💡 팁: 보조 지표(✅)가 가장 많은 종목이 '진짜 황금 종목'일 확률이 높습니다!")
            st.dataframe(pd.DataFrame(golden_stocks), hide_index=True, use_container_width=True)
        else:
            st.warning("현재 상위 50개 종목 중 기본 조건(돌파+수급)을 만족하는 종목이 없습니다.")
