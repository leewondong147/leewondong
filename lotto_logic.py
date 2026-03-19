import streamlit as st
import pandas as pd
import random
from collections import Counter

# 페이지 설정
st.set_page_config(page_title="로또 번호 추천기", page_icon="🎰")

st.title("🎰 통계 기반 로또 번호 추천")
st.write("과거 당첨 데이터를 분석하여 번호를 생성합니다.")

# 데이터 불러오기 함수
@st.cache_data
def load_lotto_data():
    try:
        # 파일명이 정확히 lotto_data.csv여야 합니다.
        df = pd.read_csv('lotto_data.csv')
        return df
    except FileNotFoundError:
        st.error("파일을 찾을 수 없습니다. GitHub에 'lotto_data.csv'가 있는지 확인하세요.")
        return None

df = load_lotto_data()

if df is not None:
    # 1. 간단한 통계 보여주기
    st.subheader("📊 최근 당첨 번호")
    st.dataframe(df.head(5)) # 최근 5회차 출력

    # 2. 번호 생성 버튼
    if st.button("이번 주 번호 추천받기"):
        # 분석할 컬럼명 (본인 CSV 파일의 헤더에 맞게 수정하세요)
        cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']
        all_nums = df[cols].values.flatten().tolist()
        
        # 빈도 분석
        counts = Counter(all_nums)
        
        # 전략: 가장 많이 나온 번호(Hot) 3개 + 안 나온 번호(Cold) 3개 조합
        hot_candidates = [n for n, c in counts.most_common(15)]
        recent_nums = df[cols].head(10).values.flatten().tolist()
        cold_candidates = [n for n in range(1, 46) if n not in recent_nums]
        
        # 중복 없이 6개 추출
        rec = set(random.sample(hot_candidates, 3))
        rec.update(random.sample(cold_candidates, 6 - len(rec)))
        final_numbers = sorted(list(rec))
        
        # 결과 대문짝만하게 출력
        st.success(f"🎊 추천 번호: {final_numbers}")
        
        # 빈도 차트
        st.bar_chart(pd.DataFrame(counts.most_common(10), columns=['번호', '빈도']).set_index('번호'))

st.info("💡 Tip: GitHub에서 lotto_data.csv 파일만 업데이트하면 분석 결과가 자동으로 갱신됩니다.")
