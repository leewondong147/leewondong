import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정
st.set_page_config(page_title="EagleEye V4.1", layout="wide")

# 2. 종목 리스트 로더 (KOSPI 200 + KOSDAQ 50)
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

# 3. 데이터 분석 보조 함수들
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        time.sleep(0.1) # 차단 방지 미세 대기
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

# --- 메인 로직 시작 ---
krx_list = load_stock_list()

st.title("🦅 EagleEye V4.1 (NameError 해결 버전)")

if krx_list.empty:
    st.error("데이터 로드 실패. 'Manage app' -> 'Clear cache' 후 새로고침하세요.")
else:
    # ⚠️ 여기서 tab1, tab2를 정확하게 정의합니다.
    tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 우량주 250개 전수조사"])

    # --- [탭 1] ---
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
                    # 지표 계산 및 출력 (기존 V3.8 로직 포함)
                    ma20_d = df['Close'].rolling(20).mean().iloc[-1]
                    ma60_d = df['Close'].rolling(60).mean().iloc[-1]
                    is_daily_aligned = df['Close'].iloc[-1] > ma20_d > ma60_d
                    
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    m_df = m_df.dropna()
                    
                    st.subheader(f"📊 {user_name} 분석 결과")
                    st.line_chart(m_df[['Close', 'MA10']])
                    
                    inv_df = get_naver_investor_data(user_code)
                    f_buy = count_consecutive(inv_df['외국인'], True) if not inv_df.empty else 0
                    i_buy = count_consecutive(inv_df['기관합계'], True) if not inv_df.empty else 0

                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write("**📈 장기 추세**")
                        st.success("✅ 10MA 위") if m_df.iloc[-1]['Close'] > m_df.iloc[-1]['MA10'] else st.error("❌ 10MA 아래")
                    with c2:
                        st.write("**💰 세력 수급**")
                        st.info(f"외인:{f_buy}일 / 기관:{i_buy}일")
                    with c3:
                        st.write("**🌳 일봉 상태**")
                        st.success("✅ 정배열") if is_daily_aligned else st.warning("❌ 혼조세")
                else:
                    st.error("데이터를 가져올 수 없습니다.")

    # --- [탭 2] ---
    with tab2:
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
                        if not inv_df.empty and (inv_df.head(3)['외국인'].sum() > 0 or inv_df.head(3)['기관합계'].sum() > 0):
                            results.append({'종목명': row['Name'], '코드': row['Code'], '현재가': int(m_df.iloc[-1]['Close'])})
                except: continue
            
            status_text.success(f"✅ {len(results)}개 발견!")
            if results:
                st.dataframe(pd.DataFrame(results), use_container_width=True)
