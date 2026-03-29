import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock
import time # 💡 기계가 아닌 사람처럼 1초씩 쉬어주기 위한 시간 도구를 추가합니다.

st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

# --- [속도 향상 1] 종목 리스트 ---
@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
    return krx

# --- [속도 향상 2] 주가 차트 데이터 ---
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

# --- [속도 향상 3 & 차단 방지] 수급 데이터 ---
@st.cache_data(ttl=3600, show_spinner=False)
def get_investor_data(start_date, end_date, code):
    time.sleep(1) # 💡 너무 빠른 연속 요청으로 거래소가 차단하지 않도록 1초 대기합니다.
    df = stock.get_market_trading_volume_by_date(start_date, end_date, code)
    
    # 💡 만약 거래소가 데이터를 안 주고 빈칸을 주면, 에러를 내뿜어서 캐시에 저장되지 않게 막습니다!
    if df.empty:
        raise ValueError("KRX_BLOCK") 
    return df

krx_list = load_stock_list()

st.title("🎯 스마트 주식 진단기 (차단 방지 패치 완료!)")
st.write("종목명을 검색하고, 10이평선 돌파 차트와 세력의 수급을 한눈에 확인하세요.")

default_index = krx_list[krx_list['Code'] == '389650'].index[0] if '389650' in krx_list['Code'].values else 0

selected_stock = st.selectbox(
    "🔍 분석할 종목명을 한글로 입력하거나 선택하세요:", 
    krx_list['Name_Code'].tolist(),
    index=int(default_index)
)

user_code = selected_stock.split('(')[1].replace(')', '')
user_name = selected_stock.split(' (')[0]

if st.button("🚀 이 종목 진단하기"):
    status_msg = st.empty()
    
    end_date = datetime.today()
    start_date_2yr = end_date - timedelta(days=730)
    start_date_short = end_date - timedelta(days=15) 
    
    status_msg.info(f"▶️ [{user_name}] 데이터를 분석 중입니다...")
    
    # --- [1단계] 주가 데이터 수집 (차트용) ---
    df = get_price_data(user_code, start_date_2yr.strftime('%Y-%m-%d'))
    
    monthly_df = pd.DataFrame()
    if not df.empty and len(df) >= 200:
        monthly_df = df.resample('ME').agg({'Close': 'last'})
        monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
        monthly_df = monthly_df.dropna()

    # --- [2단계] 수급 데이터 수집 (안전 장치 추가!) ---
    investor_df = pd.DataFrame()
    krx_blocked = False # 차단 여부를 기억하는 스위치
    
    try:
        investor_df = get_investor_data(
            start_date_short.strftime('%Y%m%d'), 
            end_date.strftime('%Y%m%d'), 
            user_code
        )
    except Exception as e:
        # 에러가 났다면 거래소 차단 스위치를 켭니다!
        krx_blocked = True 
        
    def count_consecutive_buys(series):
        count = 0
        data_list = series.tolist()
        while len(data_list) > 0 and data_list[-1] == 0:
            data_list.pop()
        for val in reversed(data_list):
            if val > 0:
                count += 1
            else:
                break
        return count

    foreigner_buy_days = 0
    institution_buy_days = 0
    
    if not investor_df.empty:
        if '외국인' in investor_df.columns:
            foreigner_buy_days = count_consecutive_buys(investor_df['외국인'])
        if '기관합계' in investor_df.columns:
            institution_buy_days = count_consecutive_buys(investor_df['기관합계'])

    # --- [3단계] 화면 출력 ---
    status_msg.empty()
    st.write("---")
    st.subheader(f"📊 {user_name} ({user_code}) 최종 진단 결과")
    
    if not monthly_df.empty and len(monthly_df) >= 2:
        st.write("#### 📈 월봉 및 10개월 이평선 차트")
        chart_df = monthly_df[['Close', 'MA10']].rename(columns={'Close': '월봉 종가', 'MA10': '10개월 이평선'})
        st.line_chart(chart_df)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**[📈 장기 차트 추세 진단]**")
        if not monthly_df.empty and len(monthly_df) >= 2:
            prev_month = monthly_df.iloc[-2]
            curr_month = monthly_df.iloc[-1]
            st.write(f"- 지난달 종가: {prev_month['Close']:,.0f}원")
            st.write(f"- 10개월 이평선: {prev_month['MA10']:,.0f}원")
            st.write(f"- 현재 주가: {curr_month['Close']:,.0f}원")
            
            if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                st.success("🔥 **월봉 10이평선 상승 돌파! (강력 신호)**")
            else:
                st.warning("상승 돌파 조건에 해당하지 않음")
        else:
            st.info("신규 상장 종목이라 10개월 이평선을 계산할 수 없습니다.")
    
    with col2:
        st.write("**[💰 외국인/기관 수급 진단]**")
        # 💡 차단되었을 때 안내 메시지
        if krx_blocked:
            st.warning("⚠️ 너무 잦은 검색으로 거래소 서버가 수급 데이터를 일시 차단했습니다.")
        else:
            if foreigner_buy_days > 0:
                st.success(f"👱‍♂️ 외국인: **{foreigner_buy_days}일 연속 매수 중!** 🔥")
            else:
                st.write("👱‍♂️ 외국인: 연속 매수 없음")
                
            if institution_buy_days > 0:
                st.success(f"🏢 기 관: **{institution_buy_days}일 연속 매수 중!** 🔥")
            else:
                st.write("🏢 기 관: 연속 매수 없음")
    
    st.write("---")
    st.write("### 🔎 [크로스 체크용] 최근 수급 상세 내역 (단위: 주)")
    
    # 💡 아래 표 부분에도 차단 안내문을 예쁘게 띄워줍니다.
    if krx_blocked:
        st.error("🚨 **한국거래소(KRX) 단기 접속 차단 안내**\n\n단시간에 여러 종목을 연속 검색하여 거래소에서 데이터를 차단했습니다. \n\n☕ **커피 한 잔 드시고 약 10~30분 뒤에 다시 검색하시면 정상적으로 표가 나타납니다!**")
    elif not investor_df.empty and '기관합계' in investor_df.columns:
        display_df = investor_df[['외국인', '기관합계']].tail(15)
        st.dataframe(display_df)
    else:
        st.warning("수급 데이터를 표시할 수 없습니다. (신규 상장 또는 거래 정지 종목일 수 있습니다.)")
