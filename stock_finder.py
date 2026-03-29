# 필요한 라이브러리를 불러옵니다.
import FinanceDataReader as fdr
import pandas as pd

def find_rising_stocks(target_ratio):
    """
    목표 등락률(target_ratio) 이상 상승한 종목을 찾아주는 함수입니다.
    """
    print(f"--- 오늘 {target_ratio}% 이상 상승한 종목 검색을 시작합니다 ---")

    # 1. 한국 거래소(KRX) 전체 상장 종목 데이터 가져오기
    # KOSPI, KOSDAQ 등의 종목코드, 이름, 현재가, 등락률 데이터를 표 형태로 가져옵니다.
    krx_list = fdr.StockListing('KRX')

    # 2. 데이터 정제하기
    # 가끔 등락률(ChagesRatio) 데이터가 비어있는 경우가 있으므로 이를 제거합니다.
    krx_list = krx_list.dropna(subset=['ChagesRatio'])

    # 3. 조건 필터링
    # ChagesRatio(등락률)이 우리가 설정한 target_ratio 이상인 종목만 골라냅니다.
    rising_stocks = krx_list[krx_list['ChagesRatio'] >= target_ratio]

    # 4. 보기 좋게 정렬하기 (등락률이 높은 순서대로 내림차순 정렬)
    rising_stocks = rising_stocks.sort_values(by='ChagesRatio', ascending=False)

    # 5. 필요한 정보만 추려서 결과 저장 (종목명, 현재가, 등락률)
    result = rising_stocks[['Name', 'Close', 'ChagesRatio']]

    return result

# 함수 실행: 오늘 10% 이상 상승한 종목 찾기
# 10.0 이라는 숫자를 변경하여 원하시는 상승률을 설정할 수 있습니다.
my_stocks = find_rising_stocks(10.0)

print(f"\n검색된 종목 수: {len(my_stocks)}개")
print("========================================")
print(my_stocks.head(15)) # 상위 15개 종목만 화면에 출력합니다.
