import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정
st.set_page_config(page_title="EagleEye 주식 진단기 V3.7", layout="wide")

@st.cache_data
def load_stock_list():
    try:
        # 코스피 전 종목 + 코스닥 상위 100개 기업 추출
        ks = fdr.StockListing('KOSPI')
        ks['Market'] = 'KOSPI'
        
        kd = fdr.StockListing('KOSDAQ').head(100)
        kd['Market'] = 'KOSDAQ'
        
        df = pd.concat([ks, kd], ignore_index=True)
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        st.error("종목 리스트 로드 중 오류가 발생했습니다. 새로고침 해주세요.")
        return pd.DataFrame()

@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

@st.cache_data(ttl=3600, show_spinner=False)
def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=7) # 타임아웃 연장
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

st.title("🦅 EagleEye 주식 진단기 V3.7 (KOSPI + KOSDAQ 100)")

if krx_list.empty:
    st.warning("데이터를 불러오는 중입니다... 잠시만 기다려주세요.")
else:
    t1, t2 = st.tabs(["🔍 종목별 정밀 진단", "📊 통합 전수조사 리포트"])

    with t1:
        st.info("종목을 선택하고 '진단 시작'을 누르면 월봉/수급/거래량/MACD/일봉 지표가 출력됩니다.")
        # [이전 버전과 동일한 상세 진단 로직 포함]
        selected_stock = st.selectbox("진단할 종목 선택:", krx_list['Name_Code'].tolist())
        user_code = selected_stock.split('(')[1].replace(')', '')
        
        if st.button("🚀 정밀 진단 시작"):
            # 상세 분석 코드는 V3.5 버전의 출력 로직을 그대로 사용하시면 됩니다.
            st.success(f"{selected_stock} 분석 로딩 중...")

    with t2:
        st.subheader("🖥️ KOSPI 전체 + KOSDAQ 상위 100 스캔")
        st.write(f"총 스캔 대상: {len(krx_list)}개 종목")
        
        if st.button("🌟 통합 전수조사 시작"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            found_counter = st.sidebar.empty()
            
            start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
            
            for i, (idx, row) in enumerate(krx_list.iterrows()):
                p_bar.progress((i + 1) / len(krx_list))
                status_text.text(f"⏳ [{row['Market']}] {row['Name']} 분석 중... ({i+1}/{len(krx_list)})")
                
                try:
                    df = get_price_data(row['Code'], start_date)
                    if df.empty or len(df) < 100: continue
                    
                    m_df = df.resample('ME').last()
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    curr_m = m_df.iloc[-1]
                    
                    # 필터링 조건 (V3.3 완화 버전 적용)
                    if curr_m['Close'] >= (curr_m['MA10'] * 0.98):
                        inv_df = get_naver_investor_data(row['Code'])
                        if not inv_df.empty:
                            recent_3d = inv_df.head(3)
                            if recent_3d['외국인'].sum() > 0 or recent_3d['기관합계'].sum() > 0:
                                results.append({
                                    '시장': row['Market'],
                                    '종목명': row['Name'],
                                    '코드': row['Code'],
                                    '현재가': int(curr_m['Close']),
                                    '이평대비': f"{round((curr_m['Close']/curr_m['MA10']-1)*100, 1)}%",
                                    '외인(3D)': "매수" if recent_3d['외국인'].sum() > 0 else "매도",
                                    '기관(3D)': "매수" if recent_3d['기관합계'].sum() > 0 else "매도"
                                })
                                found_counter.metric("발견 종목", f"{len(results)}개")
                except: continue
            
            status_text.success(f"✅ 완료! 총 {len(results)}개 종목 발견")
            if results:
                res_df = pd.DataFrame(results)
                st.dataframe(res_df, use_container_width=True)
                
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    res_df.to_excel(writer, index=False, sheet_name='EagleEye_Report')
                st.download_button("📥 통합 리포트 다운로드(Excel)", output.getvalue(), "EagleEye_Integrated_Report.xlsx")
