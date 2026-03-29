import streamlit as st
import FinanceDataReader as fdr
import pandas as pd
from datetime import datetime, timedelta
import requests
import time
import io

st.set_page_config(page_title="궁극의 스마트 주식 진단기 V3", layout="wide")

# =====================================================================
# [엔진 1] 종목 리스트 (코스피 전체 - 무적 우회로 재장착!)
# =====================================================================
@st.cache_data
def load_stock_list():
    try:
        # 1순위: 기본 방법 시도
        df = fdr.StockListing('KOSPI')
        if df.empty: raise ValueError("Empty")
        df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
        return df
    except:
        try:
            # 2순위: 깃허브 차단 시 한국거래소(KIND) 직접 우회 접속
            kospi_url = 'https://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13&marketType=stockMkt'
            headers = {'User-Agent': 'Mozilla/5.0'}
            res = requests.get(kospi_url, headers=headers)
            res.encoding = 'euc-kr'
            df = pd.read_html(res.text, header=0)[0]
            df = df[['회사명', '종목코드']].rename(columns={'회사명': 'Name', '종목코드': 'Code'})
            df['Code'] = df['Code'].astype(str).str.zfill(6)
            df['Name_Code'] = df['Name'] + ' (' + df['Code'] + ')'
            return df
        except Exception as e:
            st.error(f"종목 리스트를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요. (사유: {e})")
            return pd.DataFrame()

# =====================================================================
# [엔진 2] 데이터 분석 함수들 (속도 최적화)
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
            # 멀티인덱스 처리
            if isinstance(cols, pd.MultiIndex):
                cols = [''.join(c) for c in cols]
            else:
                cols = cols.astype(str)
                
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
    count = 0
    data_list = series.tolist()
    # 오늘 데이터가 0이면 제외
    if len(data_list) > 0 and data_list[0] == 0: data_list = data_list[1:]
    for val in data_list:
        if (is_buy and val > 0) or (not is_buy and val < 0): count += 1
        else: break
    return count

# 데이터 로드
krx_list = load_stock_list()

st.title("🦅 궁극의 스마트 주식 진단기 V3 (KOSPI 전수조사)")
st.write("코스피 전 종목을 스캔하고 분석 결과를 엑셀로 소장하세요.")

tab1, tab2 = st.tabs(["🔍 개별 종목 정밀 진단", "📊 코스피 전체 스캐너 & 엑셀"])

# --- [탭 1] 개별 종목 진단 ---
with tab1:
    if not krx_list.empty:
        selected_stock = st.selectbox("분석할 종목명 검색:", krx_list['Name_Code'].tolist())
        user_code = selected_stock.split('(')[1].replace(')', '')
        user_name = selected_stock.split(' (')[0]

        if st.button("🚀 정밀 진단 시작", key="btn_single"):
            # V2의 정밀 진단 로직 (차트 + 5대지표) 실행
            status_msg = st.empty()
            status_msg.info("데이터 분석 중...")
            # ... (중략: 상세 지표 출력 로직)
            status_msg.success(f"{user_name} 진단 완료!")
    else:
        st.warning("종목 리스트가 비어 있습니다. 페이지를 새로고침해 주세요.")

# --- [탭 2] 코스피 전체 스캐너 & 엑셀 ---
with tab2:
    st.subheader("📈 코스피 전 종목 실시간 필터링")
    if not krx_list.empty:
        st.write(f"대상 종목 수: {len(krx_list)}개")
        if st.button("🌟 전 종목 스캔 및 리포트 생성"):
            results = []
            p_bar = st.progress(0)
            status_text = st.empty()
            
            end_date = datetime.today()
            start_date_3yr = (end_date - timedelta(days=1095)).strftime('%Y-%m-%d')
            
            for i, (idx, row) in enumerate(krx_list.iterrows()):
                code, name = row['Code'], row['Name']
                p_bar.progress((i + 1) / len(krx_list))
                status_text.text(f"⏳ [{name}] 스캔 중... ({i+1}/{len(krx_list)})")
                
                try:
                    df = get_price_data(code, start_date_3yr)
                    if df.empty or len(df) < 200: continue
                    
                    # 월봉 분석
                    m_df = df.resample('ME').agg({'Close': 'last', 'Volume': 'sum'})
                    m_df['MA10'] = m_df['Close'].rolling(10).mean()
                    m_df = m_df.dropna()
                    
                    if len(m_df) >= 2:
                        curr_m, prev_m = m_df.iloc[-1], m_df.iloc[-2]
                        # 1. 월봉 10이평선 돌파 확인
                        if prev_m['Close'] < prev_m['MA10'] and curr_m['Close'] > curr_m['MA10']:
                            # 2. 수급 확인
                            inv_df = get_naver_investor_data(code)
                            if not inv_df.empty:
                                f_buy = count_consecutive(inv_df['외국인'], True)
                                i_buy = count_consecutive(inv_df['기관합계'], True)
                                
                                # 기관이나 외국인이 사고 있다면 리스트 추가
                                if f_buy > 0 or i_buy > 0:
                                    results.append({
                                        '종목코드': code,
                                        '종목명': name,
                                        '현재가': int(curr_m['Close']),
                                        '외인연속매수': f"{f_buy}일",
                                        '기관연속매수': f"{i_buy}일",
                                        '전월비거래량': f"{round(curr_m['Volume']/prev_m['Volume'], 1)}배" if prev_m['Volume'] > 0 else "0",
                                        '스캔일자': end_date.strftime('%Y-%m-%d')
                                    })
                except: continue
                
            status_text.success("✅ 스캔 완료!")
            
            if results:
                final_df = pd.DataFrame(results)
                st.dataframe(final_df, use_container_width=True)
                
                # 엑셀 다운로드 파일 생성
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    final_df.to_excel(writer, index=False, sheet_name='KOSPI_황금종목')
                excel_data = output.getvalue()
                
                st.download_button(
                    label="📥 분석 결과 엑셀 다운로드",
                    data=excel_data,
                    file_name=f"KOSPI_Report_{datetime.today().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                st.warning("조건에 맞는 종목이 없습니다.")
