import streamlit as st
import pandas as pd
import numpy as np
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.0)")

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 (모든 데이터를 문자로 먼저 읽음)
        df_raw = pd.read_excel(uploaded_file, header=None, dtype=str) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None, dtype=str)
        
        # 2. 🚨 데이터 시작 행을 찾는 정밀 알고리즘
        # '공급가액'이나 '세액'이라는 단어가 처음 등장하는 행을 찾아 그 다음부터를 데이터로 인식
        start_row = 0
        for i in range(len(df_raw)):
            row_str = "".join(df_raw.iloc[i].fillna('').astype(str))
            if '공급가액' in row_str or '세액' in row_str:
                start_row = i
                break
        
        # 데이터프레임 재구성
        df = df_raw.iloc[start_row+1:].reset_index(drop=True)
        df.columns = df_raw.iloc[start_row].values
        
        # 컬럼명 정리 및 0값 방어
        df.columns = [str(c).strip() for c in df.columns]
        
        # 3. 데이터형 변환 (필수 컬럼만 추적)
        def clean_num(x):
            try:
                return float(str(x).replace(',', '').replace('원', '').replace('"', '').strip())
            except:
                return 0.0

        # 컬럼 찾기 (유연하게)
        c_date = next((c for c in df.columns if '일자' in str(c)), df.columns[0])
        c_name = next((c for c in df.columns if '상호' in str(c) or '거래처' in str(c)), df.columns[1])
        c_supply = next((c for c in df.columns if '공급가액' in str(c)), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in str(c)), df.columns[-1])

        df[c_supply] = df[c_supply].apply(clean_num)
        df[c_tax] = df[c_tax].apply(clean_num)
        df['합계'] = df[c_supply] + df[c_tax]
        
        st.write("✅ 데이터 로드 성공!")
        st.dataframe(df[[c_date, c_name, c_supply, c_tax, '합계']])

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
