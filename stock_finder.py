import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time

# =====================================================================
# [설정] 웹페이지의 기본 화면 넓이와 제목을 설정합니다.
# =====================================================================
st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

# =====================================================================
# [엔진 1] 한국 주식 시장(KRX)의 전체 종목 리스트를 가져오는 함수
# @st.cache_data를 붙여서 한 번 가져온 리스트는 메모리에 기억해둡니다.
# =====================================================================
@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')' # 검색하기 편하게 이름과 코드를 합칩니다.
    return krx

# =====================================================================
# [엔진 2] 특정 종목의 과거 주가(차트) 데이터를 가져오는 함수
# ttl=3600은 3600초(1시간) 동안 데이터를 기억하라는 뜻입니다.
# =====================================================================
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

# =====================================================================
# [엔진 3] 네이버 금융에서 세력(외국인/기관) 수급을 긁어오는 핵심 크롤링 함수
# =====================================================================
@st.cache_data(ttl=3600, show_spinner=False)
def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'} # 기계가 아닌 사람인 척 속이는 마법의 주문입니다.
    res = requests.get(url, headers=headers)
    res.encoding = 'euc-kr' # 한글이 깨지지 않게 설정합니다.
    
    try:
        dfs = pd.read_html(res.text) # 네이버 화면에 있는 모든 표를 가져옵니다.
        for df in dfs:
            cols = df.columns
            if isinstance(cols, pd.MultiIndex):
                cols = [''.join(c) for c in cols]
            else:
                cols = cols.astype(str)
                
            # '날짜', '기관', '외국인' 이라는 글자가 있는 진짜 수급표를 찾습니다.
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
                
                # 표 안의 숫자들에 붙어있는 콤마(,)와 더하기(+) 기호를 떼어내고 순수 숫자로 바꿉니다.
                for col in [inst_col, forgn_col]:
                    df[col] = df[col].astype(str).str.replace(',', '').str.replace('+', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                df = df.rename(columns={date_col: '날짜', inst_col: '기관합계', forgn_col: '외국인'})
                return df[['날짜', '외국인', '기관합계']]
    except Exception as e:
        pass
    
    return pd.DataFrame()

# =====================================================================
# [엔진 4] 연속 매수 일수를 똑똑하게 세어주는 함수
# =====================================================================
def count_consecutive_buys_naver(series):
    count = 0
    data_list = series.tolist()
    # 장중이라 최상단(오늘) 데이터가 0으로 비어있다면 연속 계산에서 잠시 제외합니다.
    if len(data_list) > 0 and data_list[0] == 0:
        data_list = data_list[1:]
    for val in data_list:
        if val > 0:
            count += 1
        else:
            break
    return count

# 프로그램 시작! 종목 리스트를 불러옵니다.
krx_list = load_stock_list()

st.title("🎯 스마트 주식 진단기 & 자동 발굴기")
st.write("관심 종목을 깊게 분석하거나, 시장을 스캔하여 황금 종목을 찾아보세요.")

# 💡 화면을 2개의 탭으로 깔끔하게 나눕니다!
tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "🌟 상위 50개 황금 종목 자동 발굴"])

# =====================================================================
# [탭 1] 개별 종목 정밀 진단 (기존 기능)
# =====================================================================
with tab1:
    default_index = krx_list[krx_list['Code'] == '389650'].index[0] if '389650' in krx_list['Code'].values else 0

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
        
        # 1. 주가 데이터 수집 및 분석
        df = get_price_data(user_code, start_date_2yr.strftime('%Y-%m-%d'))
        monthly_df = pd.DataFrame()
        if not df.empty and len(df) >= 200:
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            monthly_df = monthly_df.dropna()

        # 2. 수급 데이터 수집 및 분석
        investor_df = get_naver_investor_data(user_code)
        foreigner_buy_days = 0
        institution_buy_days = 0
        
        if not investor_df.empty:
            if '외국인' in investor_df.columns:
                foreigner_buy_days = count_consecutive_buys_naver(investor_df['외국인'])
            if '기관합계' in investor_df.columns:
                institution_buy_days = count_consecutive_buys_naver(investor_df['기관합계'])

        # 3. 화면 출력
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
                if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                    st.success("🔥 **월봉 10이평선 상승 돌파! (강력 신호)**")
                else:
                    st.warning("상승 돌파 조건에 해당하지 않음")
            else:
                st.info("데이터 부족")
        
        with col2:
            st.write("**[💰 외국인/기관 수급 진단]**")
            if not investor_df.empty:
                if foreigner_buy_days > 0: st.success(f"👱‍♂️ 외국인: **{foreigner_buy_days}일 연속 매수!**")
                else: st.write("👱‍♂️ 외국인: 매수 없음")
                if institution_buy_days > 0: st.success(f"🏢 기 관: **{institution_buy_days}일 연속 매수!**")
                else: st.write("🏢 기 관: 매수 없음")
        
        st.write("---")
        st.write("### 🔎 최근 20일 수급 상세 내역 (단위: 주)")
        if not investor_df.empty:
            display_df = investor_df.copy()
            display_df['외국인'] = display_df['외국인'].apply(lambda x: f"{int(x):,}")
            display_df['기관합계'] = display_df['기관합계'].apply(lambda x: f"{int(x):,}")
            st.dataframe(display_df, hide_index=True)

# =====================================================================
# [탭 2] 시가총액 상위 50개 황금 종목 자동 발굴 (신규 기능!)
# =====================================================================
with tab2:
    st.write("시가총액 상위 50개 종목 중에서 **[10이평선 돌파 + 세력 연속 매수]** 조건이 모두 일치하는 종목을 찾습니다.")
    
    if st.button("🌟 황금 종목 스캔 시작하기 (약 30초 소요)", key="btn_multi"):
        golden_stocks = []
        top_50 = krx_list.head(50) # 상위 50개 종목만 추출합니다.
        
        # 화면에 진행률(게이지 바)을 표시하기 위한 준비
        progress_bar = st.progress(0)
        progress_text = st.empty()
        
        end_date = datetime.today()
        start_date_2yr = end_date - timedelta(days=730)
        
        # 50개 종목을 하나씩 꺼내서 검사합니다.
        for i, (index, row) in enumerate(top_50.iterrows()):
            code = row['Code']
            name = row['Name']
            
            progress_text.text(f"⏳ [{name}] 분석 중... ({i+1}/50)")
            progress_bar.progress((i + 1) / 50)
            
            try:
                # 1. 차트 분석 (돌파 여부)
                df = get_price_data(code, start_date_2yr.strftime('%Y-%m-%d'))
                is_crossed = False
                
                if not df.empty and len(df) >= 200:
                    monthly_df = df.resample('ME').agg({'Close': 'last'})
                    monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
                    monthly_df = monthly_df.dropna()
                    
                    if len(monthly_df) >= 2:
                        prev_month = monthly_df.iloc[-2]
                        curr_month = monthly_df.iloc[-1]
                        # 돌파 조건을 만족하면 스위치를 켭니다(True)
                        if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                            is_crossed = True
                
                # 2. 수급 분석 (차트 돌파 종목에 대해서만 수급을 확인합니다!)
                # 돌파하지도 않았는데 네이버에 접속하면 시간만 낭비되니까요.
                if is_crossed:
                    time.sleep(0.5) # 네이버가 기계로 오해하지 않도록 0.5초 살짝 쉬어줍니다.
                    investor_df = get_naver_investor_data(code)
                    
                    if not investor_df.empty:
                        foreigner_buys = count_consecutive_buys_naver(investor_df['외국인'])
                        inst_buys = count_consecutive_buys_naver(investor_df['기관합계'])
                        
                        # 기관이나 외국인 중 하나라도 연속 매수 중이라면 황금 리스트에 추가!
                        if foreigner_buys > 0 or inst_buys > 0:
                            golden_stocks.append({
                                '종목명': name,
                                '종목코드': code,
                                '외국인 연속매수': f"{foreigner_buys}일",
                                '기관 연속매수': f"{inst_buys}일"
                            })
                            
            except Exception as e:
                pass # 에러가 나면 무시하고 다음 종목으로 넘어갑니다.

        # 스캔이 100% 끝나면 진행 상황 안내 문구를 지웁니다.
        progress_text.empty()
        progress_bar.empty()
        
        # 3. 최종 결과 화면 출력
        if len(golden_stocks) > 0:
            st.success(f"🎉 축하합니다! 상위 50개 중 **{len(golden_stocks)}개**의 황금 종목을 발굴했습니다!")
            result_df = pd.DataFrame(golden_stocks)
            st.dataframe(result_df, hide_index=True, use_container_width=True)
        else:
            st.warning("아쉽게도 현재 상위 50개 종목 중에는 완벽한 조건에 부합하는 종목이 없습니다.")
