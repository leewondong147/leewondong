import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

st.set_page_config(page_title="궁극의 스마트 주식 진단기 V3.3", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        # 코스피 + 코스닥 상위 일부를 합쳐서 더 넓게 봅니다.
        ks = fdr.StockListing('KOSPI')
        kd = fdr.StockListing('KOSDAQ').head(300) # 코스닥은 상위 300개만 추가
        df = pd.concat([ks, kd])
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        kospi_url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt'
        headers = {'User-Agent': 'Mozilla/5.0'}
        res = requests.get(kospi_url, headers=headers)
        res.encoding = 'euc-kr'
        df = pd.read_html(res.text, header=0)[0]
        df = df[['회사명', '종목코드']].rename(columns={'회사명': 'Name', '종목코드': 'Code'})
        df['Code'] = df['Code'].astype(str).str.zfill(6)
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df

@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

@st.cache_data(ttl=3600, show_spinner=False)
def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr'
        dfs = pd.read_html(res.text)
        for df in dfs:
            cols = df.columns
            if isinstance(cols, pd.MultiIndex): cols = [''.join(c) for c in cols]
            else: cols = cols.astype(str)
            if any('날짜' in c for c in cols) and any('기관' in c for c in cols):
                df.columns = cols
                df = df.dropna(subset=[cols[0]])
                df = df[df[cols[0]] != '날짜'].reset_index(drop=True)
                inst_col = [c for c in cols if '기관' in c][0]
                forgn_col = [c for c in cols if '외국인' in c and '순매매' in c]
                forgn_col = forgn_col[0] if forgn_col else [c for c in cols if '외국인' in c][0]
                for col in [inst_col, forgn_col]:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('+', ''), errors='coerce').fillna(0)
                return df[['날짜', forgn_col, inst_col]].rename(columns={forgn_col: '외국인', inst_col: '기관합계'})
    except: pass
    return pd.DataFrame()

krx_list = load_stock_list()

st.title("🦅 궁극의 스마트 주식 진단기 V3.3 (필터 최적화)")
tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 시장 전수조사 & 엑셀"])

with tab2:
    st.subheader("📈 시장 전 종목 실시간 스캔 (필터 완화 버전)")
    st.info("💡 팁: 현재 '최근 3일 내 세력 매수 유입' 종목까지 폭넓게 검색합니다.")
    
    if st.button("🌟 전수조사 및 엑셀 파일 생성"):
        results = []
        p_bar = st.progress(0)
        status_text = st.empty()
        found_counter = st.sidebar.empty()
        
        start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
        
        # 셔플을 통해 매번 다른 종목부터 스캔하여 지루함을 방지합니다.
        search_list = krx_list.sample(frac=1).reset_index(drop=True)
        
        for i, (idx, row) in enumerate(search_list.iterrows()):
            p_bar.progress((i + 1) / len(search_list))
            status_text.text(f"⏳ [{row['Name']}] 분석 중... ({i+1}/{len(search_list)})")
            
            try:
                df = get_price_data(row['Code'], start_date)
                if df.empty or len(df) < 100: continue
                
                m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                curr_m = m_df.iloc[-1]
                
                # 필터 1: 현재가가 10이평선 대비 -2% 이상 (돌파 임박 포함)
                if curr_m['Close'] >= (curr_m['MA10'] * 0.98):
                    inv_df = get_naver_investor_data(row['Code'])
                    if not inv_df.empty:
                        # 최근 3일치 수급 확인
                        recent_3d = inv_df.head(3)
                        f_sum = recent_3d['외국인'].sum()
                        i_sum = recent_3d['기관합계'].sum()
                        
                        # 필터 2: 최근 3일 합산이 양수(매수 우위)라면 합격!
                        if f_sum > 0 or i_sum > 0:
                            results.append({
                                '종목명': row['Name'],
                                '종목코드': row['Code'],
                                '현재가': int(curr_m['Close']),
                                '이평선대비': f"{round((curr_m['Close']/curr_m['MA10'] - 1) * 100, 1)}%",
                                '최근외인수급': "매수" if f_sum > 0 else "매도",
                                '최근기관수급': "매수" if i_sum > 0 else "매도"
                            })
                            found_counter.metric("발견된 종목", f"{len(results)}개")
            except: continue
            
        status_text.success(f"✅ 완료! {len(results)}개의 종목을 찾았습니다.")
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 엑셀 결과 다운로드", output.getvalue(), f"Stock_Scan_{datetime.today().strftime('%Y%m%d')}.xlsx")
        else:
            st.warning("조건을 더 완화했음에도 종목이 없습니다. 시장이 매우 침체기일 수 있습니다.")
