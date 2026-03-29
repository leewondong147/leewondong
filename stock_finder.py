import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정 (노트북의 넓은 해상도에 최적화)
st.set_page_config(page_title="EagleEye 주식 진단기 V3.6", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        # 코스피 전 종목 로드
        df = fdr.StockListing('KOSPI')
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        return pd.DataFrame()

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
            if any('날짜' in str(c) for c in cols) and any('기관' in str(c) for c in cols):
                df.columns = [str(c) for c in cols]
                df = df.dropna(subset=[df.columns[0]])
                df = df[df[df.columns[0]] != '날짜'].reset_index(drop=True)
                # 기관/외인 컬럼 찾기
                inst_col = [c for c in df.columns if '기관' in c][0]
                forgn_col = [c for c in df.columns if '외국인' in c and '순매매' in c]
                forgn_col = forgn_col[0] if forgn_col else [c for c in df.columns if '외국인' in c][0]
                
                for col in [inst_col, forgn_col]:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('+', ''), errors='coerce').fillna(0)
                return df[['날짜', forgn_col, inst_col]].rename(columns={forgn_col: '외국인', inst_col: '기관합계'})
    except: pass
    return pd.DataFrame()

krx_list = load_stock_list()

st.title("🦅 EagleEye 주식 진단기 V3.6 (PC 최적화)")

if krx_list.empty:
    st.error("데이터 로딩 중... 잠시 후 새로고침(F5)을 눌러주세요.")
else:
    t1, t2 = st.tabs(["🔍 종목별 정밀 진단", "📊 코스피 전수조사 리포트"])

    with t1:
        # (개별 진단 로직은 V3.5와 동일하게 유지)
        st.info("종목을 선택하고 '진단 시작'을 누르면 5대 지표가 출력됩니다.")
        # ... [중략: 상세 지표 출력 코드] ...

    with t2:
        st.subheader("🖥️ KOSPI 전 종목 스캔 (엑셀 다운로드 지원)")
        if st.button("🌟 전수조사 시작 (노트북 전용 스피드 모드)"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
            
            # 검색 리스트
            search_list = krx_list.copy()
            
            for i, (idx, row) in enumerate(search_list.iterrows()):
                p_bar.progress((i + 1) / len(search_list))
                status_text.text(f"⏳ [{row['Name']}] 분석 중... ({i+1}/{len(search_list)})")
                
                try:
                    df = get_price_data(row['Code'], start_date)
                    if df.empty or len(df) < 100: continue
                    m_df = df.resample('ME').last()
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    curr_m = m_df.iloc[-1]
                    
                    if curr_m['Close'] >= (curr_m['MA10'] * 0.98):
                        inv_df = get_naver_investor_data(row['Code'])
                        if not inv_df.empty:
                            recent_sum = inv_df.head(3)['외국인'].sum() + inv_df.head(3)['기관합계'].sum()
                            if recent_sum > 0:
                                results.append({
                                    '종목명': row['Name'], '코드': row['Code'],
                                    '현재가': int(curr_m['Close']),
                                    '이평대비': f"{round((curr_m['Close']/curr_m['MA10']-1)*100, 1)}%",
                                    '외인수급(3D)': "매수" if inv_df.head(3)['외국인'].sum()>0 else "매도",
                                    '기관수급(3D)': "매수" if inv_df.head(3)['기관합계'].sum()>0 else "매도"
                                })
                except: continue
            
            status_text.success(f"✅ 완료! {len(results)}개 종목 발견")
            if results:
                res_df = pd.DataFrame(results)
                st.dataframe(res_df, use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    res_df.to_excel(writer, index=False)
                st.download_button("📥 엑셀 리포트 다운로드", output.getvalue(), "EagleEye_Report.xlsx")
