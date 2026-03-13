import streamlit as st
import pandas as pd
import FinanceDataReader as fdr
import os
import plotly.express as px
import ssl
import urllib.request # 🌟 [추가됨] 웹브라우저 위장을 위한 부품

# ==========================================
# 🌟 [추가됨] 데이터 서버에서 차단당하지 않도록 '일반 사용자'인 척 명찰 달기
# ==========================================
opener = urllib.request.build_opener()
opener.addheaders = [('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36')]
urllib.request.install_opener(opener)

# 맥북 SSL 인증서 에러 해결
ssl._create_default_https_context = ssl._create_unverified_context

FILE_NAME = 'my_portfolio.csv'

# 화면 글씨 크기 키우기 (CSS)
st.markdown("""
    <style>
    html, body, p, div, span, label, input, select, button, td, th {
        font-size: 18px !important;
    }
    h1 { font-size: 38px !important; }
    h2 { font-size: 30px !important; }
    h3 { font-size: 24px !important; }
    .stDataFrame { font-weight: 500 !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 🌟 [추가됨] 에러가 나도 앱이 멈추지 않도록 안전장치(try-except) 추가
# ==========================================
@st.cache_data
def get_stock_dict():
    stock_dict = {}
    try:
        krx_df = fdr.StockListing('KRX')
        stock_dict.update(dict(zip(krx_df['Code'], krx_df['Name'])))
    except Exception as e:
        pass # 에러가 나도 무시하고 넘어갑니다.
        
    try:
        etf_df = fdr.StockListing('ETF/KR')
        stock_dict.update(dict(zip(etf_df['Symbol'], etf_df['Name'])))
    except Exception as e:
        pass
        
    return stock_dict

code_to_name = get_stock_dict()

# 앱 제목 설정
st.title("📈 나의 글로벌 투자 포트폴리오")
st.write("한국 주식과 미국 주식을 원화 기준으로 한 번에 관리하세요!")

# 데이터를 기억하는 보관함 만들기
def load_data():
    if os.path.exists(FILE_NAME):
        df = pd.read_csv(FILE_NAME)
        if '종목명' not in df.columns:
            df.insert(3, '종목명', df['종목코드'].map(lambda x: code_to_name.get(str(x), x)))
            df.to_csv(FILE_NAME, index=False)
        return df
    else:
        return pd.DataFrame(columns=['증권사', '국가', '종목코드', '종목명', '매수단가(원)', '수량', '현재가(원)'])

if 'portfolio' not in st.session_state:
    st.session_state.portfolio = load_data()

# 왼쪽 사이드바에 입력 메뉴 만들기
st.sidebar.header("새로운 주식 추가하기")
with st.sidebar.form("input_form"):
    broker = st.selectbox("증권사", ['KB증권', '토스증권', '카카오페이증권'])
    nation = st.radio("국가 선택", ['한국', '미국'])
    
    st.caption("한국은 6자리 숫자(예: 005930), 미국은 영어 티커(예: NVDA)를 입력하세요.")
    code = st.text_input("종목코드")
    
    buy_price = st.number_input("매수단가 (한국은 원, 미국은 달러)", min_value=0.0, step=1.0)
    quantity = st.number_input("보유 수량 (주)", min_value=0.000000, step=0.01, format="%.6f")
    
    submit = st.form_submit_button("포트폴리오에 추가")

st.sidebar.divider()
st.sidebar.header("⚙️ 설정")
if st.sidebar.button("🗑️ 모든 데이터 초기화 (새로 시작)"):
    st.session_state.portfolio = pd.DataFrame(columns=['증권사', '국가', '종목코드', '종목명', '매수단가(원)', '수량', '현재가(원)'])
    if os.path.exists(FILE_NAME):
        os.remove(FILE_NAME)
    st.sidebar.success("데이터가 깔끔하게 초기화되었습니다!")
    st.rerun() 

# 주식 추가 버튼을 눌렀을 때의 동작
if submit:
    try:
        stock_data = fdr.DataReader(code)
        current_price_local = float(stock_data['Close'].iloc[-1])
        
        if nation == '미국':
            usd_krw = fdr.DataReader('USD/KRW')
            exchange_rate = float(usd_krw['Close'].iloc[-1])
            current_price_krw = int(current_price_local * exchange_rate)
            buy_price_krw = int(buy_price * exchange_rate) 
        else:
            current_price_krw = int(current_price_local)
            buy_price_krw = int(buy_price)

        stock_name = code_to_name.get(code.upper(), code.upper())

        new_data = pd.DataFrame({
            '증권사': [broker],
            '국가': [nation],
            '종목코드': [code.upper()],
            '종목명': [stock_name],
            '매수단가(원)': [buy_price_krw],
            '수량': [quantity],
            '현재가(원)': [current_price_krw]
        })
        st.session_state.portfolio = pd.concat([st.session_state.portfolio, new_data], ignore_index=True)
        st.session_state.portfolio.to_csv(FILE_NAME, index=False)
        st.sidebar.success(f"{stock_name} 추가 및 저장 완료!")
    except Exception as e:
        st.sidebar.error("종목코드를 확인해주세요!")

# 화면에 계산 결과 보여주기
if not st.session_state.portfolio.empty:
    
    st.divider()
    
    if st.button("🔄 모든 주식 최신가로 업데이트하기"):
        with st.spinner("주식 시장에서 최신 가격과 환율을 긁어오는 중입니다... 🚀"):
            try:
                has_us_stock = '미국' in st.session_state.portfolio['국가'].values
                if has_us_stock:
                    usd_krw = fdr.DataReader('USD/KRW')
                    exchange_rate = float(usd_krw['Close'].iloc[-1])
                for index, row in st.session_state.portfolio.iterrows():
                    code_val = str(row['종목코드'])
                    nation_val = row['국가']
                    
                    # 🌟 [수정됨] 사라진 0 다시 채워 넣기! (한국 주식은 무조건 6자리)
                    if nation_val == '한국':
                        code_val = code_val.zfill(6)
            
                    stock_data = fdr.DataReader(code_val)
                    current_price_local = float(stock_data['Close'].iloc[-1])
                    
                    if nation_val == '미국':
                        st.session_state.portfolio.at[index, '현재가(원)'] = int(current_price_local * exchange_rate)
                    else:
                        st.session_state.portfolio.at[index, '현재가(원)'] = int(current_price_local)
                
                st.session_state.portfolio.to_csv(FILE_NAME, index=False)
   # 시간 도장 찍기
                now = pd.Timestamp.now('Asia/Seoul').strftime('%Y년 %m월 %d일 %H시 %M분')
                st.success(f"✅ 업데이트 완료! (기준 시간: {now})")

            except Exception as e:
                st.error(f"정확한 에러 원인: {e}")

    st.subheader("📝 보유 현황 (표를 수정하면 알아서 저장됩니다!)")
    edited_df = st.data_editor(st.session_state.portfolio, num_rows="dynamic")
    st.session_state.portfolio = edited_df
    st.session_state.portfolio.to_csv(FILE_NAME, index=False)

    df = st.session_state.portfolio.copy()
    
    df['매수단가(원)'] = pd.to_numeric(df['매수단가(원)'])
    df['수량'] = pd.to_numeric(df['수량'])
    df['현재가(원)'] = pd.to_numeric(df['현재가(원)'])

    df['매수금액'] = (df['매수단가(원)'] * df['수량']).astype(int)
    df['평가금액'] = (df['현재가(원)'] * df['수량']).astype(int)
    df['수익률(%)'] = ((df['평가금액'] - df['매수금액']) / df['매수금액'] * 100).round(2).fillna(0)

    total_buy = int(df['매수금액'].sum())
    total_eval = int(df['평가금액'].sum())
    total_profit = total_eval - total_buy

    st.divider()

    st.subheader("💰 총 자산 요약")
    col1, col2, col3 = st.columns(3)
    col1.metric("총 매수금액", f"{total_buy:,} 원")
    col2.metric("총 평가금액", f"{total_eval:,} 원")
    
    total_profit_percent = (total_profit / total_buy * 100) if total_buy > 0 else 0
    col3.metric("총 수익/손실", f"{total_profit:,} 원", delta=f"{total_profit_percent:.2f}%")

    st.divider()

    st.subheader("📊 내 자산 분석 한눈에 보기")
    
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**자산 비중 (원형 그래프)**")
        fig_pie = px.pie(df, values='평가금액', names='종목명', hole=0.4)
        st.plotly_chart(fig_pie, use_container_width=True)
        
    with col_chart2:
        st.markdown("**종목별 수익률 (%)**")
        df['색상'] = df['수익률(%)'].apply(lambda x: 'red' if x >= 0 else 'blue')
        fig_bar = px.bar(
            df, 
            x='종목명', 
            y='수익률(%)', 
            text='수익률(%)', 
            color='색상', 
            color_discrete_map={'red':'#ff6b6b', 'blue':'#4dabf7'}
        )
        fig_bar.update_traces(textposition='outside')
        fig_bar.update_layout(showlegend=False)      
        st.plotly_chart(fig_bar, use_container_width=True)

    st.subheader("✅ 최종 계산된 포트폴리오")
    
    def color_profit(val):
        if val > 0:
            return 'color: red'   
        elif val < 0:
            return 'color: blue'  
        else:
            return 'color: black' 

    styled_df = df.style.map(color_profit, subset=['수익률(%)'])
    st.dataframe(styled_df)
    
    st.write("") 
    csv_data = df.to_csv(index=False).encode('utf-8-sig') 
    st.download_button(
        label="📥 현재 포트폴리오 파일로 다운로드 (클릭)",
        data=csv_data,
        file_name="내_멋진_포트폴리오.csv",
        mime="text/csv",
    )
    
    st.divider()

    st.subheader("📰 내 보유 종목 맞춤형 뉴스")
    st.write("관심 있는 종목을 클릭하시면 네이버 금융 뉴스로 바로 연결됩니다!")
    
    unique_stocks = df['종목명'].unique()
    
    for stock in unique_stocks:
        news_link = f"https://search.naver.com/search.naver?where=news&query={stock}+주가"
        st.markdown(f"👉 **[{stock} 최신 뉴스 보러가기]({news_link})**")

else:
    st.info("👈 왼쪽 메뉴에서 주식을 추가해 보세요. 추가한 데이터는 자동으로 저장됩니다!")
