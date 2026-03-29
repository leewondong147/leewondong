import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 1. 화면 설정
st.set_page_config(page_title="EagleEye V4.7 (완전체)", layout="wide")

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
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    try:
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

st.title("🦅 EagleEye V4.7 (전 종목 대응 & 5대 지표 복구)")

tab1, tab2 = st.tabs(["🔍 개별 정밀 진단", "📊 우량주 전수조사"])

with tab1:
    st.subheader("🔎 종목 진단 (코드 6자리 직접 입력)")
    
    col_input1, col_input2 = st.columns([3, 1])
    with col_input1:
        selected_stock = st.selectbox("리스트에서 선택:", ["직접 입력"] + krx_list['Name_Code'].tolist())
    with col_input2:
        direct_code = st.text_input("또는 코드 직접 입력:", placeholder="예: 389650")

    # 분석 대상 코드 결정
    final_code = direct_code if direct_code else (selected_stock.split('(')[1].replace(')', '') if selected_stock != "직접 입력" else "")

    if st.button("🚀 분석 시작") and final_code:
        with st.spinner(f"[{final_code}] 정밀 분석 중..."):
            start_date = (datetime.today() - timedelta(days=1000)).strftime('%Y-%m-%d')
            df = get_price_data(final_code, start_date)
            
            if not df.empty:
                # 1. 지표 계산
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

                # 2. 화면 출력
                st.subheader(f"📊 종목코드 [{final_code}] 분석 리포트")
                st.line_chart(m_df[['Close', 'MA10']].rename(columns={'Close':'종가','MA10':'10월선'}))
                
                curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                
                # 상단 3개 카드
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.write("**📈 장기 추세 (월봉 10MA)**")
                    if curr_m['Close'] > curr_m['MA10']: st.success("✅ 10MA 위 (안정)")
                    else: st.error("❌ 10MA 아래 (주의)")
                with c2:
                    st.write("**💰 세력 수급**")
                    if f_buy > 0 or i_buy > 0: st.info(f"🔥 매수중(외:{f_buy}/기:{i_buy})")
                    else: st.write("뚜렷한 수급 없음")
                with c3:
                    st.write("**🌳 일봉 상태**")
                    if df['Close'].iloc[-1] > ma20 > ma60: st.success("✅ 일봉 정배열")
                    else: st.warning("❌ 역배열/혼조세")

                # 하단 2개 카드
                st.write("---")
                c4, c5 = st.columns(2)
                with c4:
                    st.write("**📊 거래량 폭발 (전월비)**")
                    if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 거래량 대폭발")
                    else: st.write("❌ 변화 미비")
                with c5:
                    st.write("**🚀 MACD 에너지**")
                    if curr_m['MACD'] > curr_m['Signal']: st.success("✅ 상승세 유지")
                    else: st.warning("❌ 에너지 약화")
            else:
                st.error("데이터를 가져올 수 없습니다. 코드를 확인해 주세요.")

with tab2:
    st.subheader("🖥️ 우량주 실시간 스캔 리포트")
    if st.button("🌟 스캔 시작 (KOSPI 300 + KOSDAQ 200)"):
        results = []
        p_bar = st.progress(0)
        status_text = st.empty()
        for i, (idx, row) in enumerate(krx_list.iterrows()):
            p_bar.progress((i+1)/len(krx_list))
            status_text.text(f"⏳ [{row['Name']}] 분석 중...")
            try:
                # 스캔 로직 (V4.5의 안정 필터 적용)
                df = get_price_data(row['Code'], (datetime.today()-timedelta(days=365)).strftime('%Y-%m-%d'))
                if df.empty: continue
                if df['Close'].iloc[-1] > df['Close'].rolling(20).mean().iloc[-1]:
                    results.append({'시장':row['Market'], '종목명':row['Name'], '코드':row['Code'], '현재가':int(df['Close'].iloc[-1])})
            except: continue
        status_text.success(f"✅ {len(results)}개 발견")
        if results:
            res_df = pd.DataFrame(results)
            st.dataframe(res_df, use_container_width=True)
            # 엑셀 다운로드 버튼
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                res_df.to_excel(writer, index=False)
            st.download_button("📥 엑셀 다운로드", output.getvalue(), "EagleEye_Scan.xlsx")
