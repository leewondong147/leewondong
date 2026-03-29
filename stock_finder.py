import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta

def find_monthly_cross_stocks(stock_list):
    """
    주어진 종목 리스트에서 월봉 10이동평균선을 상향 돌파(상승 교차)한 종목을 찾습니다.
    """
    print("--- 월봉 10이동평균선 상승 교차 종목 검색을 시작합니다 ---")
    
    # 조건에 맞는 종목의 결과를 담을 빈 리스트를 만듭니다.
    crossed_stocks = []

    # 10개월의 평균을 구하려면 넉넉하게 2년(약 730일) 전의 과거 데이터부터 가져와야 합니다.
    start_date = (datetime.today() - timedelta(days=730)).strftime('%Y-%m-%d')

    # 리스트에 있는 종목을 하나씩 꺼내서 반복하여 검사합니다.
    for code, name in stock_list:
        try:
            # 1. 과거 일별 데이터 가져오기
            df = fdr.DataReader(code, start_date)

            if df.empty or len(df) < 200: 
                # 상장된 지 얼마 안 된 종목 등은 데이터가 부족하므로 건너뜁니다.
                continue

            # 2. 일봉 데이터를 월봉 데이터로 변환하기
            # 'ME(Month End)'를 사용하여 매월 말일의 데이터(종가)만 남깁니다.
            monthly_df = df.resample('ME').agg({'Close': 'last'})

            # 3. 10개월 이동평균선(MA10) 계산하기
            # rolling(window=10)을 사용해 10개월씩 묶어 평균(mean)을 구합니다.
            monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()

            # 처음 9개월은 10개월치 데이터가 모이지 않아 계산이 안 되므로(NaN) 해당 행을 지웁니다.
            monthly_df = monthly_df.dropna()

            if len(monthly_df) < 2:
                continue

            # 4. 상승 교차(돌파) 조건 확인하기
            # iloc[-2]는 지난달, iloc[-1]은 이번 달(가장 최근) 데이터를 의미합니다.
            prev_month = monthly_df.iloc[-2]
            curr_month = monthly_df.iloc[-1]

            # 로직: 지난달은 주가가 10이평선 아래였고(AND) 이번 달은 주가가 10이평선 위로 올라왔는가?
            if prev_month['Close'] < prev_month['MA10'] and curr_month['Close'] > curr_month['MA10']:
                
                # 조건을 만족하면 결과 리스트에 추가합니다.
                crossed_stocks.append({
                    '종목코드': code,
                    '종목명': name,
                    '현재 주가(월봉종가)': curr_month['Close'],
                    '현재 10이평선': round(curr_month['MA10'], 2) # 소수점 2자리까지만 표시
                })

        except Exception as e:
            # 데이터 수집 중 일시적 오류가 나면 프로그램이 멈추지 않게 무시하고 다음 종목으로 넘어갑니다.
            pass

    # 리스트에 담긴 결과를 보기 좋은 표(데이터프레임) 형태로 변환하여 반환합니다.
    return pd.DataFrame(crossed_stocks)

# ------------------------------------------------------------------
# 메인 실행 부분
# ------------------------------------------------------------------

# 테스트를 위해 검색해 볼 관심 종목 리스트를 만듭니다. (종목코드, 종목명)
# 원하시는 종목 코드를 여기에 자유롭게 추가하거나 뺄 수 있습니다.
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

# 함수 실행
result = find_monthly_cross_stocks(my_watch_list)

# 결과 출력
if result.empty:
    print("\n[알림] 이번 달에 10이동평균선을 상승 교차한 종목이 없습니다.")
else:
    print("\n🎉 [검색 결과] 월봉 10이동평균선 상승 교차 종목 발견!")
    print("=" * 60)
    print(result.to_string(index=False)) # index 번호는 숨기고 출력합니다.
