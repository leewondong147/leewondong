import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.1)")

# [사이드바] 위치 수동 지정 도구
st.sidebar.header("⚙️ 엑셀 구조 수동 설정")
start_row = st.sidebar.number_input("데이터 시작 행 번호 (첫 줄=0)", value=0)
c_date_idx = st.sidebar.number_input("작성일자 열 번호 (A=0, B=1...)", value=1)
c_name_idx = st.sidebar.number_input("상호 열 번호", value=2)
c_supply_idx = st.sidebar.number_input("공급가액 열 번호", value=3)
c_tax_idx = st.sidebar.number_input("세액 열 번호", value=4)

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["xlsx", "xls", "csv"])

if uploaded_file:
    try:
        # 1. 파일 로드
        df = pd.read_excel(uploaded_file, header=None) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None)
        
        # 2. 지정한 시작 행부터 읽기
        df = df.iloc[start_row:].reset_index(drop=True)
        df.columns = df.iloc[0]
        df = df.iloc[1:].reset_index(drop=True)
        
        # 3. 지정한 열 번호로 데이터 매핑
        cols = list(df.columns)
        df['작성일자'] = df.iloc[:, c_date_idx]
        df['상호'] = df.iloc[:, c_name_idx]
        df['공급가액'] = pd.to_numeric(df.iloc[:, c_supply_idx], errors='coerce').fillna(0)
        df['세액'] = pd.to_numeric(df.iloc[:, c_tax_idx], errors='coerce').fillna(0)
        df['합계'] = df['공급가액'] + df['세액']
        
        st.success("✅ 매핑 완료. 아래 표가 맞는지 확인하세요.")
        st.dataframe(df[['작성일자', '상호', '공급가액', '세액', '합계']])

    except Exception as e:
        st.error(f"🚨 설정 오류: {e} - 행/열 번호를 다시 확인해 주세요.")
