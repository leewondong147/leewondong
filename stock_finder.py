import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time

st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
    return krx

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
            if isinstance(cols, pd.MultiIndex):
                cols = [''.join(c) for c in cols]
            else:
                cols = cols.astype(str)
                
            if any('날짜' in c for c in cols) and any('기관' in c for c in cols) and any('외국인' in c for c in cols):
                df.columns = cols
                df = df.dropna(subset=[cols[0]]) 
                
                date_col = [c for c in cols if '날짜' in c][0]
                inst_col = [c for c in cols if '기관' in c][0]
                forgn_col = [c for c in cols if '외국인' in c and '순매매' in c]
                if not forgn_col:
                    forgn_col = [c for c in cols if '외국인' in c][0]
                else:
                    forgn_col = forgn_col[0]
                
                df = df[df[date_col] != '날짜'] 
                df = df.reset_index(drop=True)
                
                for col in [inst_col, forgn_col]:
                    df[col] = df[col].astype(str).str.replace(',', '').str.replace('+', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                df = df.rename(columns={date_col: '날짜', inst_col: '기관합계', forgn_col: '외국인'})
                return df[['날짜', '외국인', '기관합계']]
    except Exception as e:
        pass
    
    return pd.DataFrame()

# 💡 [기존] 연속 매수(+) 일수를 세는 함수
def count_consecutive_buys_naver(series):
    count = 0
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0:
        data_list = data_list[1:]
    for val in data_list:
        if val > 0: # 0보다 크면(매수) 카운트!
            count += 1
        else:
            break
    return count

# 💡 [신규 추가!] 연속 매도(-) 일수를 세는 함수를 새롭게 만들었습니다!
def count_consecutive_sells_naver(series):
    count = 0
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0:
        data_list = data_list[1:]
    for val in data_list:
        if val < 0: # 0보다 작으면(매도) 카운트!
            count += 1
        else:
            break
    return count

krx_list = load_stock_list()

st.title("🎯 스마트 주식 진단기 & 자동 발굴기")
st.write("관심 종목의 매수/매도 타이밍을 분석하거나 황금 종목을 찾아보세요.")

tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "🌟 상위 50개 황금 종목 자동 발굴"])

# =====================================================================
# [탭 1] 개별 종목 정밀 진단 (매도 신호 추가!)
# =====================================================================
with tab1:
    default_index = krx_list[krx_list['Code'] == '005930'].index[0] if '005930' in krx_list['Code'].values else 0
    
    selected_stock = st.selectbox(
        "분석할 종목명을 한글로 입력하거나 선택하세요:", 
        krx_list['Name_Code'].tolist(),
        index=int(default_index)
    )

    user_code = selected_stock.split('(')[1].replace(')', '')
    user_name = selected_stock.split(' (')[0]

    if st.button("🚀 이 종목 진단하기", key="btn_single"):
        status_msg = st.empty()
        end_date = datetime.today()
        start_date_2yr = end_date - timedelta(days=730)
        
        status_msg.info(f"▶️ [{user_name}] 데이터를 분석 중입니다...")
        
        df = get_price_data(user_code, start_date_2yr.strftime('%Y-%m-%d'))
        monthly_df = pd.DataFrame()
        if not df.empty and len(df) >= 200:
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            monthly_df = monthly_df.dropna()

        investor_df = get_naver_investor_data(user_code)
        foreigner_buy_days, foreigner_sell_days = 0, 0
        institution_buy_days, institution_sell_days = 0, 0
        
        if not investor_df.empty:
            if '외국인' in investor_df.columns:
                foreigner_buy_days = count_consecutive_buys_naver(investor_df['외국인'])
                foreigner_sell_days = count_consecutive_sells_naver(investor_df['외국인']) # 매도 일수 추가
            if '기관합계' in investor_df.columns:
                institution_buy_days = count_consecutive_buys_naver(investor_df['기관합계'])
                institution_sell_days = count_consecutive_sells_naver(investor_df['기관합계']) # 매도 일수 추가

        status_msg.empty()
        st.subheader(f"📊 {user_name} ({user_code}) 최종 진단 결과")
        
        if not monthly_df.empty and len(monthly_df) >= 2:
            chart_df = monthly_df[['Close', 'MA10']].rename(columns={'Close': '월봉 종가', 'MA10': '10개월 이평선'})
            st.line_chart(chart_df)
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**[📈 장기 차트 추세 진단]**")
            if not monthly_df.empty and len(monthly_df) >= 2:
                prev_month = monthly_df.iloc[-2]
                curr_month = monthly_df.iloc[-1]
                
                # 💡 돌파(매수)와 이탈(매도) 조건을 모두 검사합니다!
                is_golden_cross = prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']
                is_dead_cross = prev_month['Close'] > prev_month['MA10'] and curr_month['Close'] < curr_month['MA10']
                
                if is_golden_cross:
                    st.success("🔥 **월봉 10이평선 상향 돌파! (매수 신호)**")
                elif is_dead_cross:
                    st.error("❄️ **월봉 10이평선 하향 이탈! (매도/위험 신호)**")
                else:
                    st.info("현재 특별한 교차(돌파/이탈) 신호는 없습니다.")
                    
                st.caption(f"현재가: {curr_month['Close']:,.0f}원 / 10이평선: {curr_month['MA10']:,.0f}원")
            else:
                st.info("데이터 부족")
        
        with col2:
            st.write("**[💰 외국인/기관 수급 진단]**")
            if not investor_df.empty:
                # 외국인 수급 결과 출력 (매수/매도 분리)
                if foreigner_buy_days > 0: 
                    st.success(f"👱‍♂️ 외국인: **{foreigner_buy_days}일 연속 매수!** 🔥")
                elif foreigner_sell_days > 0: 
                    st.error(f"👱‍♂️ 외국인: **{foreigner_sell_days}일 연속 매도!** ❄️")
                else: 
                    st.write("👱‍♂️ 외국인: 뚜렷한 연속 수급 없음")
                    
                # 기관 수급 결과 출력 (매수/매도 분리)
                if institution_buy_days > 0: 
                    st.success(f"🏢 기 관: **{institution_buy_days}일 연속 매수!** 🔥")
                elif institution_sell_days > 0: 
                    st.error(f"🏢 기 관: **{institution_sell_days}일 연속 매도!** ❄️")
                else: 
                    st.write("🏢 기 관: 뚜렷한 연속 수급 없음")
        
        st.write("---")
        st.write("### 🔎 최근 20일 수급 상세 내역 (단위: 주)")
        if not investor_df.empty:
            display_df = investor_df.copy()
            display_df['외국인'] = display_df['외국인'].apply(lambda x: f"{int(x):,}")
            display_df['기관합계'] = display_df['기관합계'].apply(lambda x: f"{int(x):,}")
            st.dataframe(display_df, hide_index=True)

# =====================================================================
# [탭 2] 시가총액 상위 50개 황금 종목 자동 발굴 (그대로 유지)
# =====================================================================
with tab2:
    st.write("시가총액 상위 50개 종목 중에서 **[10이평선 돌파 + 세력 연속 매수]** 조건이 모두 일치하는 종목을 찾습니다.")
    
    if st.button("🌟 황금 종목 스캔 시작하기 (약 30초 소요)", key="btn_multi"):
        golden_stocks = []
        top_50 = krx_list.head(50) 
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        end_date = datetime.today()
        start_date_2yr = end_date - timedelta(days=730)
        
        for i, (index, row) in enumerate(top_50.iterrows()):
            code = row['Code']
            name = row['Name']
            progress_text.text(f"⏳ [{name}] 분석 중... ({i+1}/50)")
            progress_bar.progress((i + 1) / 50)
            
            try:
                df = get_price_data(code, start_date_2yr.strftime('%Y-%m-%d'))
                is_crossed = False
                
                if not df.empty and len(df) >= 200:
                    monthly_df = df.resample('ME').agg({'Close': 'last'})
                    monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
                    monthly_df = monthly_df.dropna()
                    
                    if len(monthly_df) >= 2:
                        prev_month = monthly_df.iloc[-2]
                        curr_month = monthly_df.iloc[-1]
                        if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                            is_crossed = True
                
                if is_crossed:
                    time.sleep(0.5) 
                    investor_df = get_naver_investor_data(code)
                    if not investor_df.empty:
                        foreigner_buys = count_consecutive_buys_naver(investor_df['외국인'])
                        inst_buys = count_consecutive_buys_naver(investor_df['기관합계'])
                        if foreigner_buys > 0 or inst_buys > 0:
                            golden_stocks.append({
                                '종목명': name,
                                '종목코드': code,
                                '외국인 연속매수': f"{foreigner_buys}일",
                                '기관 연속매수': f"{inst_buys}일"
                            })
            except Exception as e:
                pass 

        progress_text.empty()
        progress_bar.empty()
        
        if len(golden_stocks) > 0:
            st.success(f"🎉 축하합니다! 상위 50개 중 **{len(golden_stocks)}개**의 황금 종목을 발굴했습니다!")
            result_df = pd.DataFrame(golden_stocks)
            st.dataframe(result_df, hide_index=True, use_container_width=True)
        else:
            st.warning("아쉽게도 현재 상위 50개 종목 중에는 완벽한 조건에 부합하는 종목이 없습니다.")
