import streamlit as st
import pandas as pd
import random
from collections import Counter

# 1. 페이지 설정 및 세션 상태 초기화 (이력 저장용)
st.set_page_config(page_title="프리미엄 로또 분석기", page_icon="🎰", layout="wide")

if 'lotto_history' not in st.session_state:
    st.session_state['lotto_history'] = []

# 2. 데이터 로드 함수
@st.cache_data
def load_lotto_data():
    try:
        df = pd.read_csv('lotto_data.csv')
        return df
    except FileNotFoundError:
        st.error("lotto_data.csv 파일을 찾을 수 없습니다.")
        return None

df = load_lotto_data()

# 3. 사이드바: 사용자 설정 (포함/제외)
st.sidebar.header("⚙️ 번호 조건 설정")
include_nums = st.sidebar.multiselect("⭐ 반드시 포함 (최대 3개)", options=list(range(1, 46)), max_selections=3)
exclude_nums = st.sidebar.multiselect("❌ 제외할 번호", options=list(range(1, 46)))

st.sidebar.divider()
st.sidebar.write("🛡️ **활성화된 당첨 최적화 필터:**")
st.sidebar.caption("1. 홀짝 비율 (2:4, 3:3, 4:2)")
st.sidebar.caption("2. 총합 범위 (100 ~ 175)")
st.sidebar.caption("3. 연속 번호 제한 (3개 이상 연속 금지)")

# --- 메인 화면 ---
st.title("🎰 통계 기반 로또 추천 & 이력 관리")

if df is not None:
    tab1, tab2 = st.tabs(["번호 생성", "전체 통계 보기"])

    with tab1:
        col_main, col_history = st.columns([2, 1])

        with col_main:
            if st.button("🚀 분석 기반 번호 생성", use_container_width=True):
                cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']
                all_nums = df[cols].values.flatten().tolist()
                counts = Counter(all_nums)
                
                # 후보군 설정
                hot_candidates = [n for n, c in counts.most_common(20) if n not in exclude_nums]
                cold_candidates = [n for n in range(1, 46) if n not in exclude_nums]

                success = False
                for _ in range(200): # 필터링 통과를 위해 최대 200번 시도
                    res = set(include_nums)
                    needed = 6 - len(res)
                    
                    # 믹스 전략: 핫 넘버와 일반 넘버 섞기
                    mix_pool = list(set(hot_candidates + random.sample(cold_candidates, 10)))
                    res.update(random.sample([n for n in mix_pool if n not in res], needed))
                    
                    final_list = sorted(list(res))
                    
                    # [필터 1] 총합 체크 (100~175)
                    if not (100 <= sum(final_list) <= 175): continue
                    
                    # [필터 2] 홀짝 비율 (홀수가 2, 3, 4개인 경우만)
                    odds = len([n for n in final_list if n % 2 != 0])
                    if odds not in [2, 3, 4]: continue
                    
                    # [필터 3] 연속 번호 제한 (3개 연속 금지: 예 1,2,3)
                    consecutive = 0
                    max_consecutive = 1
                    for i in range(len(final_list)-1):
                        if final_list[i+1] == final_list[i] + 1:
                            consecutive += 1
                            max_consecutive = max(max_consecutive, consecutive + 1)
                        else:
                            consecutive = 0
                    if max_consecutive >= 3: continue
                    
                    success = True
                    break

                if success:
                    st.success(f"🎊 추천 번호: {final_list}")
                    # 세션 상태에 이력 저장
                    st.session_state['lotto_history'].insert(0, final_list) 
                else:
                    st.error("조건에 맞는 조합을 찾지 못했습니다. 제외 번호를 줄여주세요.")

        with col_history:
            st.subheader("📜 생성 이력")
            if st.session_state['lotto_history']:
                for i, hist in enumerate(st.session_state['lotto_history'][:10]): # 최근 10개만 표시
                    st.write(f"{i+1}회: `{hist}`")
                if st.button("이력 초기화"):
                    st.session_state['lotto_history'] = []
                    st.rerun()
            else:
                st.write("생성된 번호가 없습니다.")

    with tab2:
        st.subheader("📊 전체 회차 번호 빈도")
        all_nums_tab2 = df[['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']].values.flatten().tolist()
        counts_tab2 = Counter(all_nums_tab2)
        freq_df = pd.DataFrame(counts_tab2.most_common(45), columns=['번호', '빈도']).set_index('번호')
        st.bar_chart(freq_df)
