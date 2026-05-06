import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import re

st.set_page_config(page_title="EagleEye V6.0 (수급 완전 정복)", layout="wide")

# --- (기존과 동일한 데이터 수집 함수들) ---
@st.cache_data
def load_stock_list():
    try:
        ks = fdr.StockListing('KOSPI').head(300)
        kd = fdr.StockListing('KOSDAQ').head(200)
        df = pd.concat([ks, kd], ignore_index=True)
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        return pd.DataFrame()

def get_price_data(code, start_date):
    try:
        df = fdr.DataReader(code, start_date)
        if not df.empty:
            df = df[df['Volume'] > 0]
        return df
    except:
        return pd.DataFrame()

def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows; U; MSIE 9.0; Windows NT 9.0; en-US)'
    }
    try:
        time.sleep(0.1) 
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr'
        
        if res.status_code != 200:
            return pd.DataFrame()
            
        html = res.text
        rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.IGNORECASE | re.DOTALL)
        
        results = []
        for row in rows:
            tds = re.findall(r'<td[^>]*>(.*?)</td>', row, re.IGNORECASE | re.DOTALL)
            if len(tds) >= 7:
                clean_tds = [re.sub(r'<[^>]+>', '', td).replace('&nbsp;', '').strip() for td in tds]
                date_str = clean_tds[0]
                
                if re.match(r'^\d{4}\.\d{2}\.\d{2}$', date_str):
                    inst_str = clean_tds[5].replace(',', '').replace('+', '')
                    forgn_str = clean_tds[6].replace(',', '').replace('+', '')
                    
                    try:
                        results.append({
                            '날짜': date_str,
                            '외국인': int(forgn_str),
                            '기관합계': int(inst_str)
                        })
                    except:
                        pass
        return pd.DataFrame(results)
    except:
        return pd.DataFrame()

# 데이터 로드
krx_list = load_stock_list()

st.title("🦅 EagleEye V6.0 (수급 & 양매도 회피 시스템)")

tab1, tab2 = st.tabs(["🔍 1:1 정밀 진단", "📊 내 맘대로 커스텀 스캔"])

# ==========================================
# 탭 1: 정밀 진단 (양매도 '경고' 기능 추가)
# ==========================================
with tab1:
    st.subheader("🔎 종목 정밀 진단")
    selected_stock = st.selectbox("리스트에서 선택:", ["직접 입력"] + krx_list['Name_Code'].tolist())
    direct_code = st.text_input("또는 코드 직접 입력:", placeholder="예: 389650")

    final_code = direct_code if direct_code else (selected_stock.split('(')[1].replace(')', '') if selected_stock != "직접 입력" else "")

    if st.button("🚀 분석 시작") and final_code:
        with st.spinner("데이터를 분석 중입니다..."):
            inv_df = get_naver_investor_data(final_code)
            
            # 💡 [코드 추가 부분] 당일 양매도 위험 경고 로직
            if not inv_df.empty:
                f_today = inv_df.iloc[0]['외국인']
                i_today = inv_df.iloc[0]['기관합계']
                
                if f_today < 0 and i_today < 0:
                    st.error(f"🚨 **[위험 경보]** 최근 거래일 기준 외국인({f_today:,}주)과 기관({i_today:,}주)의 강력한 양매도가 포착되었습니다! 단기 변동성에 주의하세요.")
            
            st.write("---")
            st.subheader("📋 최근 10일 수급 상세 현황")
            if not inv_df.empty:
                display_df = inv_df.head(10).copy()
                # 숫자에 천 단위 콤마 찍기
                display_df['외국인'] = display_df['외국인'].apply(lambda x: f"{int(x):,}")
                display_df['기관합계'] = display_df['기관합계'].apply(lambda x: f"{int(x):,}")
                st.dataframe(display_df, use_container_width=True)
            else:
                st.warning("수급 데이터를 불러오지 못했습니다.")

# ==========================================
# 탭 2: 커스텀 스캔 (양매도 '제외' 필터링 추가)
# ==========================================
with tab2:
    st.subheader("🖥️ 커스텀 스캐너 설정")
    
    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        require_sugeub = st.checkbox("🔥 반드시 외인/기관 매수가 있어야 함 (수급 포착)", value=False)
    with col_opt2:
        # 💡 [코드 추가 부분] 양매도 회피 옵션 UI
        exclude_double_sell = st.checkbox("🚫 당일 강력 양매도(외국인+기관 동시 매도) 종목 제외", value=True)

    if st.button("🌟 스캔 시작"):
        results = []
        p_bar = st.progress(0)
        status_text = st.empty()
        
        for i, (idx, row) in enumerate(krx_list.head(30).iterrows()): # 테스트를 위해 30개만 조회 (필요시 제거)
            p_bar.progress((i+1)/len(krx_list.head(30)))
            status_text.text(f"⏳ [{row['Name']}] 분석 중...")
            
            try:
                inv_df = get_naver_investor_data(row['Code'])
                if inv_df.empty: continue
                
                f_today = inv_df.iloc[0]['외국인']
                i_today = inv_df.iloc[0]['기관합계']
                
                # 💡 [코드 추가 부분] 양매도 회피 필터링 로직
                if exclude_double_sell and (f_today < 0 and i_today < 0):
                    continue # 양매도 종목은 결과에 넣지 않고 다음 종목으로 넘어갑니다.
                
                # 기존 수급 조건 로직
                f_sum = inv_df.head(3)['외국인'].sum()
                i_sum = inv_df.head(3)['기관합계'].sum()
                
                if require_sugeub and (f_sum <= 0 and i_sum <= 0):
                    continue
                    
                results.append({
                    '종목명': row['Name'], 
                    '코드': row['Code'],
                    '최근 외국인': f_today,
                    '최근 기관': i_today,
                    '상태': '양호' if (f_today > 0 or i_today > 0) else '보통'
                })
            except: continue
            
        status_text.success(f"✅ 스캔 완료! 총 {len(results)}개 종목 발견")
        
        if results:
            st.dataframe(pd.DataFrame(results), use_container_width=True)
