import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

# --- [속도 향상 1] 종목 리스트 기억하기 ---
@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
    return krx

# --- [속도 향상 2] 주가 차트 데이터 기억하기 (1시간 유지) ---
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

# --- [속도 향상 3] 수급 데이터 기억하기 (1시간 유지) ---
@st.cache_data(ttl=3600)
def get_investor_data(start_date, end_date, code):
    return stock.get_market_trading_volume_by_date(start_date, end_date, code)


krx_list = load_stock_list()

st.title("🎯 스마트 주식 진단기 (최종 완성본)")
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
    
    try:
        status_msg.info(f"▶️ [{user_name}] 데이터를 분석 중입니다. 처음 검색 시 거래소 지연으로 10~20초 정도 소요될 수 있습니다...")
        
        # --- [1단계] 주가 데이터 수집 (캐시 사용) ---
        df = get_price_data(user_code, start_date_2yr.strftime('%Y-%m-%d'))
        
        if df.empty or len(df) < 200:
            st.warning("상장된 지 얼마 되지 않아 10개월 월봉 데이터를 모두 분석하기 어렵습니다.")
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            if len(monthly_df) >= 10:
                monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
                monthly_df = monthly_df.dropna()
            else:
                monthly_df = pd.DataFrame()
        else:
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            monthly_df = monthly_df.dropna()

        # --- [2단계] 수급 데이터 수집 (캐시 사용) ---
        investor_df = get_investor_data(
            start_date_short.strftime('%Y%m%d'), 
            end_date.strftime('%Y%m%d'), 
            user_code
        )
        
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
        status_msg.empty() # 분석이 끝나면 안내 문구를 깔끔하게 지웁니다.
        
        st.write("---")
        st.subheader(f"📊 {user_name} ({user_code}) 최종 진단 결과")
        
        # 💡 [새로운 기능] 주가 흐름을 보여주는 예쁜 꺾은선 차트 그리기
        if not monthly_df.empty and len(monthly_df) >= 2:
            st.write("#### 📈 월봉 및 10개월 이평선 차트")
            # 그래프에 표시될 이름(범례)을 예쁘게 바꿔줍니다.
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
        if not investor_df.empty and '기관합계' in investor_df.columns:
            display_df = investor_df[['외국인', '기관합계']].tail(15)
            st.dataframe(display_df)
        else:
            st.warning("수급 데이터를 표시할 수 없습니다.")
            
    except Exception as e:
        status_msg.error(f"오류가 발생했습니다: {e}")
