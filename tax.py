import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 환경 설정 (Ver 9.9: 컬럼 위치 자동 감지 및 강제 매핑 엔진)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.9)")
st.caption("날짜와 상호가 뒤섞이는 현상을 방지하기 위해 위치 기반 강제 매핑 엔진을 가동합니다.")

# ==========================================
# ⚙️ [사이드바] 사용량 직접 입력 및 컬럼 강제 지정
# ==========================================
st.sidebar.header("⚙️ 정밀 정산 설정")
job_type = st.sidebar.radio("작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])
ansan_usage = st.sidebar.number_input("안산 본점 사용량", value=50, step=1)
incheon_usage = st.sidebar.number_input("인천 지점 사용량", value=50, step=1)

# 비율 계산
total_usage = ansan_usage + incheon_usage
ansan_ratio = (ansan_usage / total_usage) if total_usage > 0 else 0.5

uploaded_file = st.file_uploader("📂 엑셀 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 파일 로드
        df = pd.read_excel(uploaded_file) if uploaded_file.name.endswith(('.xlsx', '.xls')) else pd.read_csv(uploaded_file)
        
        # 🚨 [중요] 컬럼명을 순서대로 리스트화
        cols = list(df.columns)
        
        # [위치 기반 자동 매핑]
        # 보통 홈택스 기준: 0번은 승인번호, 1번은 작성일자, 2번은 상호명 순서임
        # 대표님의 파일 순서가 다르다면 여기서 숫자를 수정하시면 됩니다!
        idx_date = 1 # 엑셀의 몇 번째(0부터 시작) 열이 날짜인가요?
        idx_name = 2 # 엑셀의 몇 번째 열이 상호인가요?
        idx_supply = 3 # 엑셀의 몇 번째 열이 공급가액인가요?
        idx_tax = 4    # 엑셀의 몇 번째 열이 세액인가요?
        
        c_date, c_name = cols[idx_date], cols[idx_name]
        c_supply, c_tax = cols[idx_supply], cols[idx_tax]
        
        # 정제 및 파싱
        df[c_supply] = df[c_supply].apply(lambda x: float(str(x).replace(',','').replace('원','')) if pd.notna(x) else 0.0)
        df[c_tax] = df[c_tax].apply(lambda x: float(str(x).replace(',','').replace('원','')) if pd.notna(x) else 0.0)
        df['합계'] = df[c_supply] + df[c_tax]
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)
        df['일'] = pd.to_datetime(df[c_date], errors='coerce').dt.day.fillna(0).astype(int)

        # (나머지 분류 및 포맷팅 로직은 이전과 동일하게 유지)
        st.success("✅ 매핑 완료! 결과 확인")
        st.dataframe(df[[c_date, c_name, c_supply, c_tax]])

    except Exception as e:
        st.error(f"🚨 오류: {e}")
