import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
from pykrx import stock

st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
    return krx

krx_list = load_stock_list()

st.title("🎯 스마트 주식 진단기 (수급 검증 기능 포함)")
st.write("종목명을 검색하고, 10이평선 돌파 여부와 세력의 수급을 한눈에 확인하세요.")

# 기본값을 넥스트바이오메디컬 코드로 설정해두겠습니다! (테스트용)
default_index = krx_list[krx_list['Code'] == '389650'].index[0] if '389650' in krx_list['Code'].values else 0

selected_stock = st.selectbox(
    "🔍 분석할 종목명을 한글로 입력하거나 선택하세요:", 
    krx_list['Name_Code'].tolist(),
    index=int(default_index)
)

user_code = selected_stock.split('(')[1].replace(')', '')
user_name = selected_stock.split(' (')[0]

if st.button("🚀 이 종목 진단하기"):
    st.info(f"[{user_name}] 데이터를 열심히 분석하고 있습니다...")
    
    end_date = datetime.today()
    start_date_2yr = end_date - timedelta(days=730)
    start_date_30d = end_date - timedelta(days=45) # 넉넉하게 45일치 조회
    
    try:
        # --- [1] 차트 분석 ---
        df = fdr.DataReader(user_code, start_date_2yr.strftime('%Y-%m-%d'))
        
        if df.empty or len(df) < 200:
            st.warning("상장된 지 얼마 되지 않아 장기 추세(10개월 월봉) 데이터를 모두 분석하기 어렵습니다. (최근 데이터만 반영)")
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            if len(monthly_df) >= 10:
                monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
                monthly_df = monthly_df.dropna()
            else:
                monthly_df = pd.DataFrame() # 데이터 부족 시 빈 표로 둡니다.
        else:
            monthly_df = df.resample('ME').agg({'Close': 'last'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            monthly_df = monthly_df.dropna()

        # --- [2] 수급 분석 (로직 개선!) ---
        investor_df = stock.get_market_trading_volume_by_date(
            start_date_30d.strftime('%Y%m%d'), 
            end_date.strftime('%Y%m%d'), 
            user_code
        )
        
        # 💡 개선된 연속 매수 계산 로직
        def count_consecutive_buys(series):
            count = 0
            data_list = series.tolist()
            
            # (핵심 로직) 끝에 있는 데이터가 0이면 아직 장중이거나 미집계 상태이므로 삭제합니다!
            while len(data_list) > 0 and data_list[-1] == 0:
                data_list.pop()
                
            # 뒤에서부터 거꾸로 순회하며 연속 매수를 셉니다.
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

        # --- [3] 진단 결과 화면 출력 ---
        st.write("---")
        st.subheader(f"📊 {user_name} ({user_code}) 최종 진단 결과")
        
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
        
        # --- [4] 크로스 체크를 위한 수급 원본 데이터 공개 (새로 추가됨!) ---
        st.write("---")
        st.write("### 🔎 [크로스 체크용] 최근 수급 상세 내역 (단위: 주)")
        st.caption("증권사 앱의 일별 수급 데이터와 아래 표가 일치하는지 확인해 보세요. (가장 아래쪽이 최근 날짜입니다.)")
        
        if not investor_df.empty and '기관합계' in investor_df.columns:
            # 외국인과 기관합계 열만 뽑아서 최근 15일 치를 보여줍니다.
            display_df = investor_df[['외국인', '기관합계']].tail(15)
            st.dataframe(display_df)
        else:
            st.warning("수급 데이터를 표시할 수 없습니다.")
            
    except Exception as e:
        st.error(f"데이터를 가져오거나 분석하는 중 오류가 발생했습니다: {e}")
