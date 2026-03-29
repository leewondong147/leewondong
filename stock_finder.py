import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock  # 💰 수급(외국인/기관) 데이터를 가져오기 위해 새로 추가된 도구입니다!

# --- 웹페이지 화면 넓게 쓰기 ---
st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

# --- 1. 종목 리스트 한 번만 불러오기 (속도 향상 마법) ---
# @st.cache_data를 붙여두면 2,000개 종목을 매번 새로 다운받지 않고 컴퓨터가 기억해둡니다!
@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    # 화면에 보여줄 때 "삼성전자 (005930)" 처럼 이름과 코드를 합쳐서 예쁘게 만듭니다.
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
    return krx

krx_list = load_stock_list()

# --- 2. 화면 구성 및 종목 검색창 ---
st.title("🎯 스마트 주식 진단기")
st.write("종목명을 검색하고, 10이평선 돌파 여부와 외국인/기관의 수급을 한눈에 확인하세요.")

# 사용자가 한글로 검색하면 자동으로 필터링되는 마법의 검색창입니다!
selected_stock = st.selectbox(
    "🔍 분석할 종목명을 한글로 입력하거나 선택하세요:", 
    krx_list['Name_Code'].tolist()
)

# 선택된 항목 "삼성전자 (005930)"에서 괄호 안의 6자리 코드만 쏙 뽑아냅니다.
user_code = selected_stock.split('(')[1].replace(')', '')
user_name = selected_stock.split(' (')[0]

if st.button("🚀 이 종목 진단하기"):
    st.info(f"[{user_name}] 데이터를 열심히 분석하고 있습니다...")
    
    # 데이터 수집 기간 설정 (추세용 2년, 수급용 30일)
    end_date = datetime.today()
    start_date_2yr = end_date - timedelta(days=730)
    start_date_30d = end_date - timedelta(days=30)
    
    try:
        # --- 3. 가격 데이터 분석 (월봉 돌파) ---
        df = fdr.DataReader(user_code, start_date_2yr.strftime('%Y-%m-%d'))
        
        if df.empty or len(df) < 200:
            st.error("데이터가 부족합니다. (신규 상장 종목일 수 있습니다.)")
        else:
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            monthly_df = monthly_df.dropna()
            
            # --- 4. 수급 데이터 분석 (연속 매수) ---
            # 최근 30일 동안의 투자자별 매매 동향을 가져옵니다.
            investor_df = stock.get_market_trading_volume_by_date(
                start_date_30d.strftime('%Y%m%d'), 
                end_date.strftime('%Y%m%d'), 
                user_code
            )
            
            # 연속 매수 일수를 세어주는 똑똑한 함수를 만듭니다.
            def count_consecutive_buys(series):
                count = 0
                # 가장 최근 날짜부터 과거로 거슬러 올라가며 양수(매수)인지 확인합니다.
                for val in series[::-1]: 
                    if val > 0:
                        count += 1
                    else:
                        break # 음수(매도)가 나오면 연속 기록이 깨지므로 멈춥니다!
                return count

            foreigner_buy_days = 0
            institution_buy_days = 0
            
            # 가져온 데이터에 외국인/기관 항목이 안전하게 있는지 확인하고 계산합니다.
            if not investor_df.empty:
                if '외국인' in investor_df.columns:
                    foreigner_buy_days = count_consecutive_buys(investor_df['외국인'])
                if '기관합계' in investor_df.columns:
                    institution_buy_days = count_consecutive_buys(investor_df['기관합계'])

            # --- 5. 상세 결과 화면에 출력하기 ---
            st.write("---")
            st.subheader(f"📊 {user_name} ({user_code}) 최종 진단 결과")
            
            # 화면을 좌우 2칸으로 예쁘게 나눕니다.
            col1, col2 = st.columns(2)
            
            # 왼쪽 칸: 차트 추세 분석
            with col1:
                st.write("**[📈 장기 차트 추세 진단]**")
                prev_month = monthly_df.iloc[-2]
                curr_month = monthly_df.iloc[-1]
                
                st.write(f"- 지난달 종가: {prev_month['Close']:,.0f}원")
                st.write(f"- 10개월 이평선: {prev_month['MA10']:,.0f}원")
                st.write(f"- 현재 주가: {curr_month['Close']:,.0f}원")
                
                if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                    st.success("🔥 **월봉 10이평선 상승 돌파! (강력 신호)**")
                else:
                    st.warning("상승 돌파 조건에 해당하지 않음")
            
            # 오른쪽 칸: 외국인/기관 수급 분석
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
            st.caption("※ 수급 데이터는 최근 30일(영업일 기준) 순매수 거래량을 바탕으로 계산됩니다.")
            
    except Exception as e:
        st.error(f"데이터를 가져오거나 분석하는 중 오류가 발생했습니다: {e}")
