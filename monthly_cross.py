import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

def find_monthly_cross_stocks(stock_list):
    print("--- 🚀 월봉 10이동평균선 상승 교차 종목 검색을 시작합니다 ---")
    print("인터넷에서 2년 치 데이터를 가져오는 중입니다. 잠시만 기다려주세요...\n")
    
    crossed_stocks = []
    start_date = (datetime.today() - timedelta(days=730)).strftime('%Y-%m-%d')

    for code, name in stock_list:
        # 이 부분이 추가되었습니다! 현재 어떤 종목을 검사 중인지 화면에 출력합니다.
        print(f"[{name}] 데이터 분석 중... 🔎") 
        
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
                    '현재 주가(월봉종가)': curr_month['Close'],
                    '현재 10이평선': round(curr_month['MA10'], 2)
                })

        except Exception as e:
            print(f"[{name}] 데이터를 가져오는 데 실패했습니다: {e}")
            pass

    return pd.DataFrame(crossed_stocks)

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

# 함수 실행 및 결과 출력
result = find_monthly_cross_stocks(my_watch_list)

if result.empty:
    print("\n[알림] 이번 달에 10이동평균선을 상승 교차한 종목이 없습니다.")
else:
    print("\n🎉 [검색 결과] 월봉 10이동평균선 상승 교차 종목 발견!")
    print("=" * 60)
    print(result.to_string(index=False))
