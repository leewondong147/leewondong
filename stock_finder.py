import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

st.set_page_config(page_title="EagleEye V5.3 (거래량 철벽 필터)", layout="wide")

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
        return fdr.DataReader(code, start_date)
    except:
        return pd.DataFrame()

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

krx_list = load_stock_list()

st.title("🦅 EagleEye V5.3 (거래량 10만주 이상 엄선)")

tab1, tab2 = st.tabs(["🔍 1:1 정밀 진단 (수급 확인용)", "📊 거래량 탑재 초고속 스캔"])

with tab1:
    st.subheader("🔎 종목 진단 (최종 수급 확인)")
    
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        selected_stock = st.selectbox("리스트에서 선택:", ["직접 입력"] + krx_list['Name_Code'].tolist())
    with col_input2:
        direct_code = st.text_input("또는 코드 직접 입력:", placeholder="예: 389650")

    final_code = direct_code if direct_code else (selected_stock.split('(')[1].replace(')', '') if selected_stock != "직접 입력" else "")

    if st.button("🚀 정밀 분석 시작") and final_code:
        with st.spinner(f"[{final_code}] 데이터 분석 중..."):
            start_date = (datetime.today() - timedelta(days=2000)).strftime('%Y-%m-%d')
            df = get_price_data(final_code, start_date)
            
            if not df.empty and len(df) > 200:
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                ma60 = df['Close'].rolling(60).mean().iloc[-1]
                df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
                df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = df['EMA12'] - df['EMA26']
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                
                m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df = m_df.dropna()
                
                inv_df = get_naver_investor_data(final_code)
                f_buy = count_consecutive(inv_df['외국인'], True) if not inv_df.empty else 0
                i_buy = count_consecutive(inv_df['기관합계'], True) if not inv_df.empty else 0

                st.subheader(f"📊 종목코드 [{final_code}] 분석 리포트")
                st.line_chart(m_df[['Close', 'MA10']].rename(columns={'Close':'종가','MA10':'10월선'}))
                
                if len(m_df) >= 2:
                    curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                    curr_price = df['Close'].iloc[-1]
                    
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.write("**📈 장기 추세**")
                        if curr_price >= curr_m['MA10']: st.success(f"✅ 10MA 위")
                        else: st.error(f"❌ 10MA 아래")
                    with c2:
                        st.write("**💰 세력 수급**")
                        if f_buy > 0 or i_buy > 0: st.info(f"🔥 매수(외:{f_buy}/기:{i_buy})")
                        else: st.write("뚜렷한 수급 없음")
                    with c3:
                        st.write("**🌳 일봉 상태**")
                        if curr_price >= ma20: st.success("✅ 20일선 위 지지")
                        else: st.warning("❌ 20일선 이탈")

                    st.write("---")
                    c4, c5 = st.columns(2)
                    with c4:
                        st.write("**📊 거래량 폭발**")
                        if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 1.5배 이상 폭발")
                        else: st.write("❌ 변화 미비")
                    with c5:
                        st.write("**🚀 일봉 MACD**")
                        if df['MACD'].iloc[-1] > df['Signal'].iloc[-1]: st.success("✅ MACD 상승")
                        else: st.warning("❌ MACD 하락")
            else:
                st.error("데이터가 부족합니다.")

with tab2:
    st.subheader("🖥️ 초고속 정밀 차트 스캔 (거래량 필터 탑재)")
    st.write("💡 장기추세 + 단기추세 + MACD + **[평균 거래량 10만주 이상]** 종목만 발굴합니다.")
    
    if st.button("🌟 유동성 탑재 스캔 시작"):
        results = []
        p_bar = st.progress(0)
        status_text = st.empty()
        
        start_date = (datetime.today() - timedelta(days=2000)).strftime('%Y-%m-%d')
        
        for i, (idx, row) in enumerate(krx_list.iterrows()):
            p_bar.progress((i+1)/len(krx_list))
            status_text.text(f"⏳ [{row['Name']}] 차트 및 거래량 분석 중...")
            try:
                df = get_price_data(row['Code'], start_date)
                if df.empty or len(df) < 250: continue 
                
                curr_price = df['Close'].iloc[-1]
                ma20 = df['Close'].rolling(20).mean().iloc[-1]
                
                # 💡 핵심 추가: 20일 평균 거래량 계산
                avg_vol_20d = df['Volume'].rolling(20).mean().iloc[-1]
                
                df['EMA12'] = df['Close'].ewm(span=12, adjust=False).mean()
                df['EMA26'] = df['Close'].ewm(span=26, adjust=False).mean()
                df['MACD'] = df['EMA12'] - df['EMA26']
                df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
                curr_macd = df['MACD'].iloc[-1]
                curr_signal = df['Signal'].iloc[-1]
                
                m_df = df.resample('ME').agg({'Close': 'last'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df = m_df.dropna()
                
                if not m_df.empty:
                    curr_m_ma10 = m_df['MA10'].iloc[-1]
                    
                    # 💡 4중 초강력 필터 (거래량 포함)
                    cond1 = curr_price >= curr_m_ma10        # 장기추세 합격
                    cond2 = curr_price >= ma20               # 단기추세 합격
                    cond3 = curr_macd > curr_signal          # MACD 에너지 합격
                    cond4 = avg_vol_20d >= 100000            # 거래량 10만주 이상 합격!
                    
                    if cond1 and cond2 and cond3 and cond4:
                        results.append({
                            '시장':row['Market'], 
                            '종목명':row['Name'], 
                            '코드':row['Code'], 
                            '현재가':int(curr_price),
                            '평균거래량': f"{int(avg_vol_20d):,}주", # 결과에 거래량 표시
                            '수급확인': '🔍 탭 1에서 확인'
                        })
            except: continue
            
        status_text.success(f"✅ 스캔 완료! 거래량이 풍부한 진짜배기 {len(results)}개 종목 발견")
        if results:
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                res_df.to_excel(writer, index=False)
            st.download_button("📥 활어 종목 리스트 다운로드", output.getvalue(), "EagleEye_Volume_Scan.xlsx")
