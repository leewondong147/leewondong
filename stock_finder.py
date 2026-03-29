import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

st.set_page_config(page_title="EagleEye V3.9 (안정화 버전)", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        # 너무 많은 종목 대신, 우량주 위주로 250개를 선별합니다 (차단 방지)
        ks = fdr.StockListing('KOSPI').head(200) # 시총 상위 200개
        kd = fdr.StockListing('KOSDAQ').head(50)  # 코스닥 상위 50개
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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
        # 💡 네이버 차단을 피하기 위해 접속 전후로 아주 짧은 대기 시간을 둡니다.
        time.sleep(0.2) 
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

krx_list = load_stock_list()

st.title("🦅 EagleEye V3.9 (차단 방지 & 우량주 집중)")

if krx_list.empty:
    st.error("종목 리스트 로드 실패. F5를 눌러주세요.")
else:
    t1, t2 = st.tabs(["🔍 개별 정밀 진단", "📊 우량주 250개 전수조사"])

    with t1:
        # 개별 진단 로직은 V3.8과 동일하게 유지 (한 종목씩 보는 건 차단 안 당함)
        selected_stock = st.selectbox("종목 선택:", krx_list['Name_Code'].tolist())
        # ... [이하 생략 - 이전 V3.8 코드의 출력 로직 그대로 사용] ...

    with t2:
        st.subheader("🖥️ 시총 상위 250개 집중 스캔")
        st.write("차단 방지를 위해 안정적인 속도로 조사를 진행합니다.")
        
        if st.button("🌟 안정 모드 스캔 시작"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            found_counter = st.sidebar.empty()
            
            start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
            
            for i, (idx, row) in enumerate(krx_list.iterrows()):
                p_bar.progress((i + 1) / len(krx_list))
                status_text.text(f"⏳ [{row['Name']}] 분석 중... ({i+1}/{len(krx_list)})")
                
                try:
                    df = get_price_data(row['Code'], start_date)
                    if df.empty or len(df) < 100: continue
                    
                    m_df = df.resample('ME').last()
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    curr_m = m_df.iloc[-1]
                    
                    # 필터링 (주가가 10이평선 근처 이상)
                    if curr_m['Close'] >= (curr_m['MA10'] * 0.97):
                        inv_df = get_naver_investor_data(row['Code'])
                        if not inv_df.empty:
                            recent_3d = inv_df.head(3)
                            f_buy = recent_3d['외국인'].sum()
                            i_buy = recent_3d['기관합계'].sum()
                            
                            if f_buy > 0 or i_buy > 0:
                                results.append({
                                    '종목명': row['Name'], '코드': row['Code'],
                                    '현재가': int(curr_m['Close']),
                                    '외인(3D)': "매수" if f_buy > 0 else "매도",
                                    '기관(3D)': "매수" if i_buy > 0 else "매도"
                                })
                                found_counter.metric("발견 종목", f"{len(results)}개")
                except: continue
            
            status_text.success(f"✅ 완료! {len(results)}개 종목을 발굴했습니다.")
            if results:
                st.dataframe(pd.DataFrame(results), use_container_width=True)
                # 엑셀 다운로드 버튼...
