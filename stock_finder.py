import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

# --- 1. 웹페이지 화면 구성하기 ---
st.title("📈 월봉 10이동평균선 돌파 검색기")
st.write("관심 종목 중에서 장기 상승 추세로 전환되는 종목을 찾아냅니다.")

# 테스트용 관심 종목 리스트
my_watch_list = [
    ('005930', '삼성전자'),
    ('000660', 'SK하이닉스'),
    ('035420', 'NAVER'),
    ('035720', '카카오'),
    ('005380', '현대차'),
    ('068270', '셀트리온'),
    ('000270', '기아'),
    ('051910', 'LG화학')
]

# 화면에 버튼을 만듭니다. 사용자가 이 버튼을 누르면 아래 코드가 실행됩니다.
if st.button("🚀 종목 검색 시작하기"):
    
    # 웹 화면에 빈 공간을 만들고, 진행 상황을 보여줄 준비를 합니다.
    progress_text = st.empty() 
    
    crossed_stocks = []
    start_date = (datetime.today() - timedelta(days=730)).strftime('%Y-%m-%d')

    # --- 2. 데이터 수집 및 분석 ---
    for code, name in my_watch_list:
        # 웹 화면에 현재 어떤 종목을 분석 중인지 실시간으로 띄워줍니다! (먹통 방지)
        progress_text.text(f"⏳ [{name}] 데이터 분석 중...")
        
        try:
            df = fdr.DataReader(code, start_date)

            if df.empty or len(df) < 200: 
                continue

            monthly_df = df.resample('ME').agg({'Close': 'last'})
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
            monthly_df = monthly_df.dropna()

            if len(monthly_df) < 2:
                continue

            prev_month = monthly_df.iloc[-2]
            curr_month = monthly_df.iloc[-1]

            if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                crossed_stocks.append({
                    '종목코드': code,
                    '종목명': name,
                    '현재 주가': curr_month['Close'],
                    '현재 10이평선': round(curr_month['MA10'], 2)
                })

        except Exception as e:
            pass
            
    # 검색이 끝나면 진행 상황 안내 문구를 지웁니다.
    progress_text.empty()

    # --- 3. 검색 결과 웹 화면에 출력 ---
    result_df = pd.DataFrame(crossed_stocks)

    if result_df.empty:
        st.warning("이번 달에 10이동평균선을 상승 교차한 종목이 없습니다.")
    else:
        st.success("🎉 검색 완료! 월봉 10이동평균선 상승 교차 종목을 발견했습니다.")
        # 결과를 깔끔한 웹 표(dataframe) 형식으로 보여줍니다.
        st.dataframe(result_df, hide_index=True)
