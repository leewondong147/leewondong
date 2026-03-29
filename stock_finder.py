import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

# 화면 설정을 넓게 잡습니다.
st.set_page_config(page_title="궁극의 스마트 주식 진단기 V3.2", layout="wide")

# =====================================================================
# [엔진 1] 종목 리스트 (우회로 포함)
# =====================================================================
@st.cache_data
def load_stock_list():
    try:
        df = fdr.StockListing('KOSPI')
        if df.empty: raise ValueError
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

# =====================================================================
# [엔진 2] 데이터 분석 함수들
# =====================================================================
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

def count_consecutive(series, is_buy=True):
    data_list = series.tolist()
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    count = 0
    for val in data_list:
        if (is_buy and val > 0) or (not is_buy and val < 0): count += 1
        else: break
    return count

# 데이터 로드
krx_list = load_stock_list()

st.title("🦅 궁극의 스마트 주식 진단기 V3.2")

tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 코스피 전수조사 & 엑셀"])

# =====================================================================
# [탭 1] 개별 종목 정밀 진단 (복구 완료!)
# =====================================================================
with tab1:
    if not krx_list.empty:
        selected_stock = st.selectbox("진단할 종목을 선택하세요:", krx_list['Name_Code'].tolist())
        user_code = selected_stock.split('(')[1].replace(')', '')
        user_name = selected_stock.split(' (')[0]

        if st.button("🚀 정밀 진단 시작", key="btn_single"):
            status_msg = st.empty()
            status_msg.info(f"▶️ [{user_name}] 지표 분석 중...")
            
            end_date = datetime.today()
            start_date_3yr = (end_date - timedelta(days=1095)).strftime('%Y-%m-%d')
            df = get_price_data(user_code, start_date_3yr)
            
            if not df.empty:
                # 1. 일봉 정배열
                ma20_d = df['Close'].rolling(20).mean().iloc[-1]
                ma60_d = df['Close'].rolling(60).mean().iloc[-1]
                is_daily_aligned = df['Close'].iloc[-1] > ma20_d > ma60_d
                
                # 2. 월봉 및 보조지표
                m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                m_df['EMA12'] = m_df['Close'].ewm(span=12).mean()
                m_df['EMA26'] = m_df['Close'].ewm(span=26).mean()
                m_df['MACD'] = m_df['EMA12'] - m_df['EMA26']
                m_df['Signal'] = m_df['MACD'].ewm(span=9).mean()
                m_df = m_df.dropna()
                
                # 3. 수급
                inv_df = get_naver_investor_data(user_code)
                f_buy, f_sell, i_buy, i_sell = 0, 0, 0, 0
                if not inv_df.empty:
                    f_buy = count_consecutive(inv_df['외국인'], True)
                    f_sell = count_consecutive(inv_df['외국인'], False)
                    i_buy = count_consecutive(inv_df['기관합계'], True)
                    i_sell = count_consecutive(inv_df['기관합계'], False)

                status_msg.empty()
                st.subheader(f"📊 {user_name} 진단 리포트")
                
                chart_df = m_df[['Close', 'MA10']].rename(columns={'Close': '월봉 종가', 'MA10': '10개월 선'})
                st.line_chart(chart_df)
                
                c1, c2, c3 = st.columns(3)
                curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                
                with c1:
                    st.write("**📈 장기 추세**")
                    if prev_m['Close'] < prev_m['MA10'] and curr_m['Close'] > curr_m['MA10']: st.success("🔥 10MA 상향 돌파!")
                    elif curr_m['Close'] > curr_m['MA10']: st.info("✅ 10MA 위 유지 중")
                    else: st.error("❄️ 10MA 아래 하락세")
                    
                    st.write("**💰 세력 수급**")
                    if f_buy > 0 or i_buy > 0: st.success(f"🔥 매수(외:{f_buy}/기:{i_buy})")
                    elif f_sell > 0 or i_sell > 0: st.error(f"❄️ 매도(외:{f_sell}/기:{i_sell})")
                    else: st.write("뚜렷한 수급 없음")

                with c2:
                    st.write("**📊 거래량 폭발**")
                    if curr_m['Volume'] > prev_m['Volume'] * 1.5: st.success("✅ 거래량 대폭발!")
                    else: st.write("❌ 거래량 평이함")
                    
                    st.write("**🚀 MACD 에너지**")
                    if curr_m['MACD'] > curr_m['Signal']: st.success("✅ 상승 에너지 우위")
                    else: st.warning("❌ 에너지 약화 중")

                with c3:
                    st.write("**🌳 일봉 정배열**")
                    if is_daily_aligned: st.success("✅ 일봉 정배열 (상승장)")
                    else: st.warning("❌ 일봉 혼조세")
            else:
                st.error("데이터를 불러올 수 없습니다.")

# =====================================================================
# [탭 2] 코스피 전수조사 (사이드바 통계 추가)
# =====================================================================
with tab2:
    st.subheader("📈 코스피 전체 종목 리포트 생성")
    if st.button("🌟 전수조사 및 엑셀 파일 생성"):
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
                
                m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                m_df['MA10'] = m_df['Close'].rolling(10).mean()
                curr_m = m_df.iloc[-1]
                
                # 1차 필터: 현재가가 월봉 10이평선 위
                if curr_m['Close'] > curr_m['MA10']:
                    inv_df = get_naver_investor_data(row['Code'])
                    if not inv_df.empty:
                        f_buy = count_consecutive(inv_df['외국인'], True)
                        i_buy = count_consecutive(inv_df['기관합계'], True)
                        
                        # 2차 필터: 외인이나 기관이 사고 있음
                        if f_buy > 0 or i_buy > 0:
                            results.append({
                                '종목명': row['Name'],
                                '종목코드': row['Code'],
                                '현재가': int(curr_m['Close']),
                                '외인매수': f"{f_buy}일",
                                '기관매수': f"{i_buy}일",
                                '거래량배수': round(curr_m['Volume']/m_df.iloc[-2]['Volume'], 1) if len(m_df)>1 else 0
                            })
                            found_counter.metric("발견된 황금 종목", f"{len(results)}개")
            except: continue
            
        status_text.success(f"✅ 완료! {len(results)}개의 종목을 찾았습니다.")
        if results:
            final_df = pd.DataFrame(results)
            st.dataframe(final_df, use_container_width=True)
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                final_df.to_excel(writer, index=False)
            st.download_button("📥 엑셀 결과 다운로드", output.getvalue(), f"KOSPI_{datetime.today().strftime('%Y%m%d')}.xlsx")
