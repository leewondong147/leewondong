import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

st.set_page_config(page_title="EagleEye V4.4", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        ks = fdr.StockListing('KOSPI').head(200)
        kd = fdr.StockListing('KOSDAQ').head(50)
        df = pd.concat([ks, kd], ignore_index=True)
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        time.sleep(0.1)
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr'
        dfs = pd.read_html(res.text)
        for df in dfs:
            cols = df.columns
            if isinstance(cols, pd.MultiIndex): cols = [''.join(c) for c in cols]
            if any('날짜' in str(c) for c in cols) and any('기관' in str(c) for c in cols):
                df.columns = [str(c) for c in cols]
                df = df.dropna(subset=[df.columns[0]])
                df = df[df[df.columns[0]] != '날짜'].reset_index(drop=True)
                inst_col = [c for c in df.columns if '기관' in c][0]
                forgn_col = [c for c in df.columns if '외국인' in c and '순매매' in c]
                forgn_col = forgn_col[0] if forgn_col else [c for c in df.columns if '외국인' in c][0]
                for col in [inst_col, forgn_col]:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('+', ''), errors='coerce').fillna(0)
                return df[['날짜', forgn_col, inst_col]].rename(columns={forgn_col: '외국인', inst_col: '기관합계'})
    except: pass
    return pd.DataFrame()

def count_consecutive(series, is_buy=True):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if (is_buy and val > 0) or (not is_buy and val < 0): count += 1
        else: break
    return count

krx_list = load_stock_list()

st.title("🦅 EagleEye V4.4 (5대 지표 완전체)")

if krx_list.empty:
    st.error("데이터 로드 실패. 새로고침 하세요.")
else:
    tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 우량주 250개 전수조사"])

    with tab1:
        st.subheader("🔎 종목별 5대 지표 분석")
        selected_stock = st.selectbox("진단할 종목 선택:", krx_list['Name_Code'].tolist(), key="s1")
        user_code = selected_stock.split('(')[1].replace(')', '')
        user_name = selected_stock.split(' (')[0]

        if st.button("🚀 정밀 진단 시작", key="b1"):
            with st.spinner(f"[{user_name}] 분석 중..."):
                start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
                df = get_price_data(user_code, start_date)
                
                if not df.empty:
                    # 1. 지표 계산
                    ma20_d = df['Close'].rolling(20).mean().iloc[-1]
                    ma60_d = df['Close'].rolling(60).mean().iloc[-1]
                    is_daily_aligned = df['Close'].iloc[-1] > ma20_d > ma60_d
                    
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    m_df['EMA12'] = m_df['Close'].ewm(span=12).mean()
                    m_df['EMA26'] = m_df['Close'].ewm(span=26).mean()
                    m_df['MACD'] = m_df['EMA12'] - m_df['EMA26']
                    m_df['Signal'] = m_df['MACD'].ewm(span=9).mean()
                    m_df = m_df.dropna()
                    
                    inv_df = get_naver_investor_data(user_code)
                    f_buy = count_consecutive(inv_df['외국인'], True) if not inv_df.empty else 0
                    i_buy = count_consecutive(inv_df['기관합계'], True) if not inv_df.empty else 0

                    st.subheader(f"📊 {user_name} 분석 결과")
                    st.line_chart(m_df[['Close', 'MA10']])
                    
                    curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]

                    # 💡 출력부: 5대 지표 카드 구성
                    row1_col1, row1_col2, row1_col3 = st.columns(3)
                    with row1_col1:
                        st.write("**📈 장기 추세 (월봉 10MA)**")
                        if curr_m['Close'] > curr_m['MA10']: st.success("✅ 10MA 위 (장기 우상향)")
                        else: st.error("❌ 10MA 아래 (장기 하락세)")
                            
                    with row1_col2:
                        st.write("**💰 세력 수급 (최근 연속)**")
                        if f_buy > 0 or i_buy > 0: st.info(f"🔥 매수: 외인 {f_buy}일 / 기관 {i_buy}일")
                        else: st.write("뚜렷한 수급 없음")
                            
                    with row1_col3:
                        st.write("**🌳 일봉 상태 (20/60선)**")
                        if is_daily_aligned: st.success("✅ 일봉 정배열 (단기 상승)")
                        else: st.warning("❌ 일봉 혼조세/역배열")

                    st.write("---") # 구분선
                    row2_col1, row2_col2 = st.columns(2)
                    with row2_col1:
                        st.write("**📊 거래량 폭발 (전월비)**")
                        if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 거래량 1.5배 이상 대폭발!")
                        else: st.write("❌ 거래량 변화 크지 않음")

                    with row2_col2:
                        st.write("**🚀 MACD 추세 에너지**")
                        if curr_m['MACD'] > curr_m['Signal']: st.success("✅ MACD 골든크로스/상승중")
                        else: st.warning("❌ MACD 데드크로스/하락중")
                else:
                    st.error("데이터를 가져올 수 없습니다.")

    with tab2:
        # 전수조사 로직은 V4.3과 동일하게 유지
        st.subheader("🖥️ 우량주 250개 실시간 스캔")
        if st.button("🌟 스캔 시작", key="b2"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
            for i, (idx, row) in enumerate(krx_list.iterrows()):
                p_bar.progress((i + 1) / len(krx_list))
                status_text.text(f"⏳ [{row['Name']}] 분석 중...")
                try:
                    df = get_price_data(row['Code'], start_date)
                    if df.empty: continue
                    m_df = df.resample('ME').last()
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    if m_df.iloc[-1]['Close'] >= (m_df.iloc[-1]['MA10'] * 0.97):
                        inv_df = get_naver_investor_data(row['Code'])
                        if not inv_df.empty:
                            f_s, i_s = inv_df.head(3)['외국인'].sum(), inv_df.head(3)['기관합계'].sum()
                            if f_s > 0 or i_s > 0:
                                results.append({'종목명': row['Name'], '코드': row['Code'], '현재가': int(m_df.iloc[-1]['Close'])})
                except: continue
            status_text.success(f"✅ {len(results)}개 발견!")
            if results:
                st.dataframe(pd.DataFrame(results), use_container_width=True)
