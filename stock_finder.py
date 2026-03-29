import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정 (넓게 보기)
st.set_page_config(page_title="궁극의 스마트 주식 진단기 V3.5", layout="wide")

# 2. 종목 리스트 로더 (안정성 강화)
@st.cache_data
def load_stock_list():
    try:
        ks = fdr.StockListing('KOSPI')
        kd = fdr.StockListing('KOSDAQ').head(200)
        df = pd.concat([ks, kd])
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        try:
            url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt'
            res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
            res.encoding = 'euc-kr'
            df = pd.read_html(res.text, header=0)[0]
            df = df[['회사명', '종목코드']].rename(columns={'회사명': 'Name', '종목코드': 'Code'})
            df['Code'] = df['Code'].astype(str).str.zfill(6)
            df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
            return df
        except: return pd.DataFrame()

# 데이터 분석 보조 함수들
@st.cache_data(ttl=3600)
def get_price_data(code, start_date):
    return fdr.DataReader(code, start_date)

@st.cache_data(ttl=3600, show_spinner=False)
def get_naver_investor_data(code):
    url = f"https://finance.naver.com/item/frgn.naver?code={code}"
    try:
        res = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
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

def count_consecutive(series, is_buy=True):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if (is_buy and val > 0) or (not is_buy and val < 0): count += 1
        else: break
    return count

# 프로그램 본문
krx_list = load_stock_list()

st.title("🦅 궁극의 스마트 주식 진단기 V3.5")

if krx_list.empty:
    st.error("❌ 종목 리스트 로드 실패. 새로고침 하세요.")
else:
    tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 시장 전수조사 & 엑셀"])

    # --- [탭 1] 개별 종목 정밀 진단 (복구 및 강화) ---
    with tab1:
        selected_stock = st.selectbox("진단할 종목 선택:", krx_list['Name_Code'].tolist())
        user_code = selected_stock.split('(')[1].replace(')', '')
        user_name = selected_stock.split(' (')[0]

        if st.button("🚀 정밀 진단 시작"):
            with st.spinner(f"[{user_name}] 5대 지표 분석 중..."):
                start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
                df = get_price_data(user_code, start_date)
                
                if not df.empty:
                    # 일봉 정배열
                    ma20 = df['Close'].rolling(20).mean().iloc[-1]
                    ma60 = df['Close'].rolling(60).mean().iloc[-1]
                    is_daily_aligned = df['Close'].iloc[-1] > ma20 > ma60
                    
                    # 월봉 분석
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    m_df['EMA12'] = m_df['Close'].ewm(span=12).mean()
                    m_df['EMA26'] = m_df['Close'].ewm(span=26).mean()
                    m_df['MACD'] = m_df['EMA12'] - m_df['EMA26']
                    m_df['Signal'] = m_df['MACD'].ewm(span=9).mean()
                    m_df = m_df.dropna()
                    
                    # 수급
                    inv_df = get_naver_investor_data(user_code)
                    f_buy, f_sell, i_buy, i_sell = 0, 0, 0, 0
                    if not inv_df.empty:
                        f_buy = count_consecutive(inv_df['외국인'], True)
                        f_sell = count_consecutive(inv_df['외국인'], False)
                        i_buy = count_consecutive(inv_df['기관합계'], True)
                        i_sell = count_consecutive(inv_df['기관합계'], False)

                    st.subheader(f"📊 {user_name} 진단 결과")
                    st.line_chart(m_df[['Close', 'MA10']].rename(columns={'Close':'종가','MA10':'10월선'}))
                    
                    c1, c2, c3 = st.columns(3)
                    curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                    with c1:
                        st.write("**📈 장기 추세**")
                        if curr_m['Close'] > curr_m['MA10']: st.success("✅ 10MA 위 (안전)")
                        else: st.error("❌ 10MA 아래 (위험)")
                        st.write("**💰 세력 수급**")
                        if f_buy > 0 or i_buy > 0: st.success(f"🔥 매수(외:{f_buy}/기:{i_buy})")
                        elif f_sell > 0 or i_sell > 0: st.error(f"❄️ 매도(외:{f_sell}/기:{i_sell})")
                    with c2:
                        st.write("**📊 거래량**")
                        if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 거래량 폭발")
                        else: st.write("❌ 평이함")
                        st.write("**🚀 MACD**")
                        if curr_m['MACD'] > curr_m['Signal']: st.success("✅ 상승 에너지")
                        else: st.warning("❌ 에너지 약화")
                    with c3:
                        st.write("**🌳 일봉 상태**")
                        if is_daily_aligned: st.success("✅ 일봉 정배열")
                        else: st.warning("❌ 혼조세")
                else: st.error("데이터 로드 실패")

    # --- [탭 2] 전수조사 및 엑셀 (V3.3 로직 반영) ---
    with tab2:
        st.subheader("🖥️ 전 종목 실시간 스캔 (필터 완화 버전)")
        if st.button("🌟 전수조사 시작"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            
            # 스캔 리스트 섞기
            search_list = krx_list.sample(frac=1).reset_index(drop=True)
            start_date = (datetime.today() - timedelta(days=1095)).strftime('%Y-%m-%d')
            
            for i, (idx, row) in enumerate(search_list.iterrows()):
                p_bar.progress((i + 1) / len(search_list))
                status_text.text(f"⏳ [{row['Name']}] 분석 중... ({i+1}/{len(search_list)})")
                try:
                    df = get_price_data(row['Code'], start_date)
                    if df.empty or len(df) < 100: continue
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    curr_m = m_df.iloc[-1]
                    
                    if curr_m['Close'] >= (curr_m['MA10'] * 0.98): # 이평선 근처
                        inv_df = get_naver_investor_data(row['Code'])
                        if not inv_df.empty:
                            recent_3d = inv_df.head(3)
                            if recent_3d['외국인'].sum() > 0 or recent_3d['기관합계'].sum() > 0:
                                results.append({
                                    '종목명': row['Name'], '종목코드': row['Code'],
                                    '현재가': int(curr_m['Close']),
                                    '이평대비': f"{round((curr_m['Close']/curr_m['MA10']-1)*100, 1)}%"
                                })
                except: continue
                
            status_text.success(f"✅ 완료! {len(results)}개 발견")
            if results:
                final_df = pd.DataFrame(results)
                st.dataframe(final_df, use_container_width=True)
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False)
                st.download_button("📥 엑셀 다운로드", output.getvalue(), "Stock_Report.xlsx")
