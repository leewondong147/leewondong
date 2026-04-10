import streamlit as st
import pandas as pd
import random
from collections import Counter

# 1. 페이지 설정
st.set_page_config(
    page_title="프리미엄 로또 분석기 v2.0",
    page_icon="🎰",
    layout="wide"
)

# 2. 세션 상태 초기화
if 'lotto_history' not in st.session_state:
    st.session_state['lotto_history'] = []

# 3. 데이터 로드 함수
@st.cache_data
def load_lotto_data():
    try:
        df = pd.read_csv('lotto_data.csv')
        if '회차' in df.columns:
            df = df.sort_values(by='회차', ascending=False)
        return df
    except FileNotFoundError:
        return None

# --- 데이터 준비 ---
df = load_lotto_data()

if df is not None:
    # 데이터 정의
    latest_round = df['회차'].iloc[0]
    cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']
    
    st.title("🎰 프리미엄 로또 추천 & 전략 분석")
    st.info(f"✅ 현재 **{latest_round}회**차 데이터를 기준으로 최적의 필터링을 수행합니다.")

    # 사이드바: 전략 설정
    st.sidebar.header("🎯 당첨 전략 설정")
    include_nums = st.sidebar.multiselect("⭐ 포함할 번호 (추천: 최근 5주 핫넘버 중 1-2개)", options=list(range(1, 46)), max_selections=3)
    exclude_nums = st.sidebar.multiselect("❌ 제외할 번호 (추천: 직전 회차 번호 일부)", options=list(range(1, 46)))

    tab1, tab2 = st.tabs(["🎯 번호 생성 및 공유", "📊 트렌드 분석 통계"])

    with tab1:
        col_gen, col_hist = st.columns([2, 1])
        with col_gen:
            st.subheader("최적 조합 추출")
            if st.button("🚀 필터링 적용 번호 생성", use_container_width=True):
                # 전체 데이터 기반 빈도
                all_nums = df[cols].values.flatten().tolist()
                counts = Counter(all_nums)
                
                # 생성 로직
                success = False
                for _ in range(500): # 시도 횟수 상향
                    res = set(include_nums)
                    needed = 6 - len(res)
                    # 핫넘버(상위 20개)에서 일부, 전체에서 일부 섞기
                    pool = [n for n, c in counts.most_common(20) if n not in exclude_nums]
                    random_pool = [n for n in range(1, 46) if n not in exclude_nums and n not in res]
                    
                    if len(random_pool) < needed: break
                    res.update(random.sample(random_pool, needed))
                    
                    final_list = sorted(list(res))
                    
                    # [필터 적용]
                    if not (100 <= sum(final_list) <= 175): continue # 총합
                    odds = len([n for n in final_list if n % 2 != 0])
                    if odds not in [2, 3, 4]: continue # 홀짝비율
                    
                    # 연속 번호 체크
                    is_consecutive = False
                    for i in range(len(final_list)-2):
                        if final_list[i]+1 == final_list[i+1] and final_list[i+1]+1 == final_list[i+2]:
                            is_consecutive = True; break
                    if is_consecutive: continue
                    
                    success = True
                    break

                if success:
                    st.balloons()
                    st.success(f"### 🎊 추천 번호: {final_list}")
                    share_text = f"🎰 [로또 추천]\n기준: {latest_round}회차\n번호: {final_list}\n함께 행운을! ✨"
                    st.code(share_text, language=None)
                    st.session_state['lotto_history'].insert(0, final_list)
                else:
                    st.error("조건에 맞는 조합을 찾지 못했습니다. 제외 번호를 줄여주세요.")

        with col_hist:
            st.subheader("📜 생성 이력")
            if st.session_state['lotto_history']:
                for i, h in enumerate(st.session_state['lotto_history'][:8]):
                    st.write(f"**{i+1}회:** `{h}`")
                if st.button("이력 삭제"):
                    st.session_state['lotto_history'] = []
                    st.rerun()

    with tab2:
        st.subheader("🔥 최근 트렌드 분석")
        
        # 🌟 최근 5주 데이터 추출 및 분석
        recent_5_df = df.head(5)
        recent_5_nums = recent_5_df[cols].values.flatten().tolist()
        recent_5_counts = Counter(recent_5_nums)
        
        col_t1, col_t2 = st.columns(2)
        
        with col_t1:
            st.write("#### 1️⃣ 최근 5주간 많이 나온 번호 (Hot)")
            hot_5_df = pd.DataFrame(recent_5_counts.most_common(10), columns=['번호', '빈도'])
            st.dataframe(hot_5_df, hide_index=True, use_container_width=True)
            
        with col_t2:
            st.write("#### 2️⃣ 최근 5주간 한 번도 안 나온 번호 (Cold)")
            all_45 = set(range(1, 46))
            cold_5_nums = sorted(list(all_45 - set(recent_5_nums)))
            st.write(f"총 {len(cold_5_nums)}개의 번호가 미출현 중입니다.")
            st.caption(f"{cold_5_nums}")

        st.divider()
        st.subheader("📈 전체 회차 누적 빈도 Top 15")
        all_counts = Counter(df[cols].values.flatten().tolist())
        all_freq_df = pd.DataFrame(all_counts.most_common(15), columns=['번호', '빈도']).set_index('번호')
        st.bar_chart(all_freq_df)

else:
    st.error("데이터 파일을 찾을 수 없습니다.")
