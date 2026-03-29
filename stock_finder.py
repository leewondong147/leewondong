import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

# --- 1. 웹페이지 화면 구성하기 ---
st.title("🎯 특정 종목 10이평선 돌파 진단기")
st.write("관심 있는 종목의 코드를 입력하여 장기 상승 추세 전환 여부를 확인해 보세요.")

# 사용자로부터 6자리 종목 코드를 입력받는 빈칸을 만듭니다.
# 기본값으로 삼성전자 코드(005930)를 미리 적어둡니다.
user_code = st.text_input("🔍 종목코드 6자리를 입력하세요 (예: 삼성전자 -> 005930)", value="005930")

# 화면에 검색 버튼 만들기
if st.button("🚀 이 종목 진단하기"):
    
    if not user_code:
        st.warning("종목코드를 입력해주세요!")
    else:
        # 진행 상황 안내
        st.info(f"[{user_code}] 종목의 과거 2년 치 데이터를 분석하고 있습니다...")
        start_date = (datetime.today() - timedelta(days=730)).strftime('%Y-%m-%d')

        try:
            # --- 2. 특정 종목 데이터 수집 ---
            df = fdr.DataReader(user_code, start_date)

            if df.empty or len(df) < 200: 
                st.error("데이터가 부족하거나 잘못된 종목코드입니다. 코드를 다시 확인해 주세요.")
            else:
                # --- 3. 데이터 분석 및 계산 ---
                monthly_df = df.resample('ME').agg({'Close': 'last'})
                monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
                monthly_df = monthly_df.dropna()

                if len(monthly_df) < 2:
                    st.error("상장된 지 얼마 되지 않아 10개월 치 월봉 데이터가 아직 모이지 않았습니다.")
                else:
                    prev_month = monthly_df.iloc[-2]
                    curr_month = monthly_df.iloc[-1]
                    
                    # --- 4. 상세 결과 출력 ---
                    st.write("---")
                    st.write("### 📊 데이터 분석 결과")
                    # {:,.0f}는 숫자에 쉼표(,)를 찍어 보기 좋게 만들어주는 파이썬의 마법입니다.
                    st.write(f"- **지난달 종가:** {prev_month['Close']:,.0f}원 (10개월 이평선: {prev_month['MA10']:,.0f}원)")
                    st.write(f"- **이번달 종가:** {curr_month['Close']:,.0f}원 (10개월 이평선: {curr_month['MA10']:,.0f}원)")
                    st.write("---")

                    # 상승 교차(골든크로스) 조건 확인
                    if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                        st.success("🎉 **축하합니다!** 이 종목은 현재 월봉 10이동평균선을 상향 돌파했습니다! (상승 추세 전환 신호)")
                    else:
                        st.warning("이 종목은 현재 월봉 10이동평균선 상승 돌파 조건에 해당하지 않습니다.")

        except Exception as e:
            st.error(f"데이터를 불러오는 중 오류가 발생했습니다: {e}")
