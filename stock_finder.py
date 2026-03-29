import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정
st.set_page_config(page_title="EagleEye V4.9 (VVIP 초강력 필터)", layout="wide")

# 2. 종목 리스트 로더
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

# 3. 데이터 분석 보조 함수들
def get_price_data(code, start_date):
    try:
        return fdr.DataReader(code, start_date)
    except:
        return pd.DataFrame()

def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        time.sleep(0.1) # 1~3번 관문 통과한 종목만 물어보므로 대기시간 단축 가능
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

def count_consecutive(series, is_buy=True):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if (is_buy and val > 0) or (not is_buy and val < 0): count += 1
        else: break
    return count

# 메인 로직 시작
krx_list = load_stock_list()

st.title("🦅 EagleEye V4.9 (Top 1% 황금종목 추출기)")

tab1, tab2 = st.tabs(["🔍 개별 정밀 진단", "📊 VVIP 5성급 전수조사"])

with tab1:
    st.subheader("🔎 종목 진단 (코드 직접 입력 가능)")
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        selected_stock = st.selectbox("리스트에서 선택:", ["직접 입력"] + krx_list['Name_Code'].tolist())
    with col_input2:
        direct_code = st.text_input("또는 코드 직접 입력:", placeholder="예: 389650")

    final_code = direct_code if direct_code else (selected_stock.split('(')[1].replace(')', '') if selected_stock != "직접 입력" else "")

    if st.button("🚀 분석 시작") and final_code:
        with st.spinner(f"[{final_code}] 정밀 분석 중..."):
            start_date = (datetime.today() - timedelta(days=1000)).strftime('%Y-%m-%d')
            df = get_price_data(final_code, start_date)
            
            if not df.empty:
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                ma60 = df['Close'].rolling(60).mean().iloc[-1]
                m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df['EMA12'] = m_df['Close'].ewm(span=12).mean()
                m_df['EMA26'] = m_df['Close'].ewm(span=26).mean()
                m_df['MACD'] = m_df['EMA12'] - m_df['EMA26']
                m_df['Signal'] = m_df['MACD'].ewm(span=9).mean()
                m_df = m_df.dropna()
                
                inv_df = get_naver_investor_data(final_code)
                f_buy = count_consecutive(inv_df['외국인'], True) if not inv_df.empty else 0
                i_buy = count_consecutive(inv_df['기관합계'], True) if not inv_df.empty else 0

                st.subheader(f"📊 종목코드 [{final_code}] 분석 리포트")
                st.line_chart(m_df[['Close', 'MA10']].rename(columns={'Close':'종가','MA10':'10월선'}))
                
                if len(m_df) >= 2:
                    curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write("**📈 장기 추세 (월봉 10MA)**")
                        if curr_m['Close'] > curr_m['MA10']: st.success("✅ 10MA 위 (장기 상승세)")
                        else: st.error("❌ 10MA 아래 (장기 하락세)")
                    with c2:
                        st.write("**💰 세력 수급**")
                        if f_buy > 0 or i_buy > 0: st.info(f"🔥 매수중(외:{f_buy}/기:{i_buy})")
                        else: st.write("뚜렷한 수급 없음")
                    with c3:
                        st.write("**🌳 일봉 상태**")
                        if df['Close'].iloc[-1] > ma20 > ma60: st.success("✅ 일봉 완벽 정배열")
                        else: st.warning("❌ 역배열/혼조세")

                    st.write("---")
                    c4, c5 = st.columns(2)
                    with c4:
                        st.write("**📊 거래량 폭발 (전월비)**")
                        if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 거래량 1.5배 대폭발")
                        else: st.write("❌ 변화 미비")
                    with c5:
                        st.write("**🚀 MACD 에너지**")
                        if curr_m['MACD'] > curr_m['Signal']: st.success("✅ 상승 에너지 우세")
                        else: st.warning("❌ 에너지 약화")
            else:
                st.error("데이터를 가져올 수 없습니다.")

with tab2:
    st.subheader("🖥️ VVIP 초강력 스캔 (차트 정배열 + MACD + 수급 동시 만족)")
    if st.button("🌟 초강력 필터 스캔 시작"):
        results = []
        p_bar = st.progress(0)
        status_text = st.empty()
        
        start_date = (datetime.today() - timedelta(days=1000)).strftime('%Y-%m-%d')
        
        for i, (idx, row) in enumerate(krx_list.iterrows()):
            p_bar.progress((i+1)/len(krx_list))
            status_text.text(f"⏳ [{row['Name']}] 정밀 필터링 중...")
            try:
                df = get_price_data(row['Code'], start_date)
                if df.empty or len(df) < 200: continue
                
                # [일봉 계산]
                curr_price = df['Close'].iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                ma60 = df['Close'].rolling(60).mean().iloc[-1]
                
                # [월봉/MACD 계산]
                m_df = df.resample('ME').agg({'Close': 'last'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df['EMA12'] = m_df['Close'].ewm(span=12).mean()
                m_df['EMA26'] = m_df['Close'].ewm(span=26).mean()
                m_df['MACD'] = m_df['EMA12'] - m_df['EMA26']
                m_df['Signal'] = m_df['MACD'].ewm(span=9).mean()
                m_df = m_df.dropna()
                
                if not m_df.empty:
                    curr_m_ma10 = m_df['MA10'].iloc[-1]
                    curr_macd = m_df['MACD'].iloc[-1]
                    curr_signal = m_df['Signal'].iloc[-1]
                    
                    # 💡 4중 초강력 필터 적용
                    cond1 = curr_price >= curr_m_ma10        # 장기추세 합격
                    cond2 = curr_price > ma20 > ma60         # 일봉 정배열 합격
                    cond3 = curr_macd > curr_signal          # MACD 상승에너지 합격
                    
                    if cond1 and cond2 and cond3:
                        # 위 3개를 다 통과한 '찐' 우량주만 수급 확인 (속도 대폭 향상)
                        inv_df = get_naver_investor_data(row['Code'])
                        if not inv_df.empty:
                            f_sum = inv_df.head(3)['외국인'].sum()
                            i_sum = inv_df.head(3)['기관합계'].sum()
                            
                            cond4 = (f_sum > 0 or i_sum > 0) # 세력 수급 합격
                            
                            if cond4:
                                results.append({
                                    '시장':row['Market'], 
                                    '종목명':row['Name'], 
                                    '코드':row['Code'], 
                                    '현재가':int(curr_price)
                                })
            except: continue
            
        status_text.success(f"✅ 스캔 완료! 모든 관문을 통과한 최정예 {len(results)}개 종목 발견")
        if results:
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                res_df.to_excel(writer, index=False)
            st.download_button("📥 최정예 리스트 다운로드", output.getvalue(), "EagleEye_VVIP_Scan.xlsx")
