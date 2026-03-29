import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests # 💡 pykrx를 버리고 네이버에서 긁어오기 위한 도구입니다.

st.set_page_config(page_title="스마트 주식 진단기", layout="centered")

@st.cache_data
def load_stock_list():
    krx = fdr.StockListing('KRX')
    krx['Name_Code'] = krx['Name'] + ' (' + krx['Code'] + ')'
    return krx

@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

# 💡 [핵심 엔진 교체] 네이버 금융에서 20일 치 수급표를 1초 만에 긁어옵니다!
@st.cache_data(ttl=3600, show_spinner=False)
def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    res = requests.get(url, headers=headers)
    res.encoding = 'euc-kr'
    
    try:
        dfs = pd.read_html(res.text)
        for df in dfs:
            cols = df.columns
            if isinstance(cols, pd.MultiIndex):
                cols = [''.join(c) for c in cols]
            else:
                cols = cols.astype(str)
                
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
                
                # 콤마, 플러스 기호 떼고 숫자로 변환
                for col in [inst_col, forgn_col]:
                    df[col] = df[col].astype(str).str.replace(',', '').str.replace('+', '')
                    df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
                df = df.rename(columns={date_col: '날짜', inst_col: '기관합계', forgn_col: '외국인'})
                return df[['날짜', '외국인', '기관합계']]
    except Exception as e:
        pass
    
    return pd.DataFrame()

krx_list = load_stock_list()

st.title("🎯 스마트 주식 진단기 (네이버 수급 엔진 장착!)")
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
    
    status_msg.info(f"▶️ [{user_name}] 데이터를 분석 중입니다...")
    
    # --- [1단계] 주가 데이터 수집 ---
    df = get_price_data(user_code, start_date_2yr.strftime('%Y-%m-%d'))
    
    monthly_df = pd.DataFrame()
    if not df.empty and len(df) >= 200:
        monthly_df = df.resample('ME').agg({'Close': 'last'})
        monthly_df['MA10'] = monthly_df['Close'].rolling(window=10).mean()
        monthly_df = monthly_df.dropna()

    # --- [2단계] 수급 데이터 수집 (네이버 엔진) ---
    investor_df = get_naver_investor_data(user_code)
        
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

    foreigner_buy_days = 0
    institution_buy_days = 0
    
    if not investor_df.empty:
        if '외국인' in investor_df.columns:
            foreigner_buy_days = count_consecutive_buys_naver(investor_df['외국인'])
        if '기관합계' in investor_df.columns:
            institution_buy_days = count_consecutive_buys_naver(investor_df['기관합계'])

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
        if investor_df.empty:
            st.warning("수급 데이터를 가져올 수 없습니다.")
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
    st.write("### 🔎 [크로스 체크용] 최근 20일 수급 상세 내역 (단위: 주)")
    if not investor_df.empty:
        # 천 단위 콤마(,)를 예쁘게 찍어서 표를 보여줍니다.
        display_df = investor_df.copy()
        display_df['외국인'] = display_df['외국인'].apply(lambda x: f"{int(x):,}")
        display_df['기관합계'] = display_df['기관합계'].apply(lambda x: f"{int(x):,}")
        st.dataframe(display_df, hide_index=True)
    else:
        st.error("데이터를 불러오지 못했습니다.")
