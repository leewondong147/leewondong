import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정
st.set_page_config(page_title="EagleEye V4.5 (최종 안정화)", layout="wide")

# 2. 종목 리스트 로더 (KOSPI 200 + KOSDAQ 150 우량주 위주)
@st.cache_data
def load_stock_list():
    try:
        # 코스피 상위 200개
        ks = fdr.StockListing('KOSPI')
        ks = ks.head(200).copy()
        ks['Market'] = 'KOSPI'
        
        # 코스닥 상위 150개 (코스닥 150 지수 종목 위주)
        kd = fdr.StockListing('KOSDAQ')
        kd = kd.head(150).copy()
        kd['Market'] = 'KOSDAQ'
        
        df = pd.concat([ks, kd], ignore_index=True)
        # 종목명과 코드를 합친 리스트 생성
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except Exception as e:
        st.error(f"종목 리스트 로드 오류: {e}")
        return pd.DataFrame()

# 3. 데이터 분석 보조 함수들
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    try:
        return fdr.DataReader(code, start_date)
    except:
        return pd.DataFrame()

def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    # 💡 차단을 피하기 위해 더 실제 브라우저 같은 정보를 보냅니다.
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    }
    try:
        time.sleep(0.3) # 차단 방지를 위해 쉬는 시간을 조금 더 늘림
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'euc-kr'
        dfs = pd.read_html(res.text)
        for df in dfs:
            cols = df.columns
            if isinstance(cols, pd.MultiIndex): cols = [''.join(c) for c in cols]
            if any('날짜' in str(c) for c in cols) and any('기관' in str(c) for c in cols):
                df.columns = [str(c) for c in cols]
                df = df.dropna(subset=[df.columns[0]])
                df = df[df[df.columns[0]].str.contains(r'\d{4}\.\d{2}\.\d{2}', na=False)].reset_index(drop=True)
                
                inst_col = [c for c in df.columns if '기관' in c][0]
                forgn_col = [c for c in df.columns if '외국인' in c and '순매매' in c]
                forgn_col = forgn_col[0] if forgn_col else [c for c in df.columns if '외국인' in c][0]
                
                for col in [inst_col, forgn_col]:
                    df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', '').str.replace('+', ''), errors='coerce').fillna(0)
                return df[['날짜', forgn_col, inst_col]].rename(columns={forgn_col: '외국인', inst_col: '기관합계'})
    except: pass
    return pd.DataFrame()

# --- 메인 로직 ---
krx_list = load_stock_list()

st.title("🦅 EagleEye V4.5 (KOSPI/KOSDAQ 통합본)")

if krx_list.empty:
    st.error("데이터를 불러오지 못했습니다. 'Manage app'에서 캐시를 비우거나 새로고침 하세요.")
else:
    tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 우량주 350개 전수조사"])

    with tab1:
        st.subheader("🔎 KOSPI/KOSDAQ 통합 진단")
        # 검색 기능 추가 (코스닥 종목도 검색 가능)
        selected_stock = st.selectbox("종목 선택 (이름 또는 코드를 입력):", krx_list['Name_Code'].tolist(), key="s1")
        user_code = selected_stock.split('(')[1].replace(')', '')
        user_name = selected_stock.split(' (')[0]

        if st.button("🚀 정밀 진단 시작", key="b1"):
            with st.spinner(f"[{user_name}] 분석 중..."):
                start_date = (datetime.today() - timedelta(days=1000)).strftime('%Y-%m-%d')
                df = get_price_data(user_code, start_date)
                
                if not df.empty:
                    # [월봉 데이터]
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    
                    # [지표 계산]
                    curr_price = df['Close'].iloc[-1]
                    ma20_d = df['Close'].rolling(20).mean().iloc[-1]
                    ma60_d = df['Close'].rolling(60).mean().iloc[-1]
                    
                    st.subheader(f"📊 {user_name} 분석 리포트")
                    st.line_chart(m_df[['Close', 'MA10']])
                    
                    inv_df = get_naver_investor_data(user_code)
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write("**📈 장기 추세 (월봉)**")
                        if not m_df.empty and curr_price > m_df['MA10'].iloc[-1]:
                            st.success("✅ 10MA 위 (정배열)")
                        else: st.error("❌ 10MA 아래")
                    with c2:
                        st.write("**💰 수급 상태**")
                        if not inv_df.empty:
                            f_buy = (inv_df['외국인'].head(3).sum() > 0)
                            i_buy = (inv_df['기관합계'].head(3).sum() > 0)
                            st.info(f"외인매수: {f_buy} / 기관매수: {i_buy}")
                        else: st.warning("수급 데이터 일시 차단됨")
                    with c3:
                        st.write("**🌳 일봉 상태**")
                        if curr_price > ma20_d > ma60_d: st.success("✅ 일봉 정배열")
                        else: st.warning("❌ 역배열/혼조세")
                else: st.error("데이터 로드 실패")

    with tab2:
        st.subheader("🖥️ KOSPI 200 + KOSDAQ 150 실시간 스캔")
        if st.button("🌟 전수조사 시작 (안정 모드)", key="b2"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            start_date = (datetime.today() - timedelta(days=500)).strftime('%Y-%m-%d')
            
            for i, (idx, row) in enumerate(krx_list.iterrows()):
                p_bar.progress((i + 1) / len(krx_list))
                status_text.text(f"⏳ [{row['Market']}] {row['Name']} 분석 중...")
                
                try:
                    df = get_price_data(row['Code'], start_date)
                    if df.empty or len(df) < 50: continue
                    
                    curr_p = df['Close'].iloc[-1]
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    
                    # 💡 1차 필터: 일봉 20선 근처 (수급 확인 전 가격으로 먼저 거름)
                    if curr_p >= ma20 * 0.98:
                        inv_df = get_naver_investor_data(row['Code'])
                        # 수급 차단 시 가격 필터만 통과한 것들 위주로 보여줌
                        f_sum = inv_df['외국인'].head(2).sum() if not inv_df.empty else 0
                        i_sum = inv_df['기관합계'].head(2).sum() if not inv_df.empty else 0
                        
                        if f_sum > 0 or i_sum > 0:
                            results.append({
                                '시장': row['Market'], '종목명': row['Name'], '코드': row['Code'],
                                '현재가': int(curr_p), '등락': f"{round(((curr_p/df['Close'].iloc[-2])-1)*100, 2)}%"
                            })
                except: continue
                
            status_text.success(f"✅ 완료! {len(results)}개 종목 발견")
            if results:
                st.dataframe(pd.DataFrame(results), use_container_width=True)
