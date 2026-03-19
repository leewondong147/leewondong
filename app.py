import streamlit as st
import pandas as pd
import random
from collections import Counter

# 1. 페이지 설정 (가장 상단에 위치)
st.set_page_config(
    page_title="프리미엄 로또 번호 분석기",
    page_icon="🎰",
    layout="wide"
)

# 2. 세션 상태 초기화 (번호 생성 이력 저장용)
if 'lotto_history' not in st.session_state:
    st.session_state['lotto_history'] = []

# 3. 데이터 로드 함수
@st.cache_data
def load_lotto_data():
    try:
        # GitHub에 업로드된 csv 파일을 읽어옵니다.
        df = pd.read_csv('lotto_data.csv')
        # 회차 기준 내림차순 정렬 (최신 회차가 위로)
        if '회차' in df.columns:
            df = df.sort_values(by='회차', ascending=False)
        return df
    except FileNotFoundError:
        return None

# --- 메인 화면 구성 ---
df = load_lotto_data()

st.title("🎰 통계 기반 로또 추천 & 공유 시스템")
st.markdown("---")

if df is not None:
    # 사이드바 설정 영역
    st.sidebar.header("⚙️ 조건 필터 설정")
    include_nums = st.sidebar.multiselect("⭐ 반드시 포함 (최대 3개)", options=list(range(1, 46)), max_selections=3)
    exclude_nums = st.sidebar.multiselect("❌ 제외할 번호", options=list(range(1, 46)))
    
    st.sidebar.divider()
    st.sidebar.info("""
    **🛡️ 적용된 당첨 최적화 필터**
    1. **홀짝 비율**: 2:4, 3:3, 4:2만 허용
    2. **총합 범위**: 100 ~ 175 사이만 허용
    3. **연속 제한**: 3개 이상 연속 번호 금지
    """)

    # 상단 요약 정보
    latest_round = df['회차'].iloc[0]
    total_rounds = len(df)
    st.info(f"✅ 현재 **{latest_round}회**까지의 데이터를 분석 중입니다. (총 {total_rounds}개 회차 반영)")

    # 탭 메뉴 구성
    tab1, tab2 = st.tabs(["🎯 번호 생성 및 공유", "📊 전체 통계 분석"])

    with tab1:
        col_gen, col_hist = st.columns([2, 1])

        with col_gen:
            st.subheader("번호 추출하기")
            if st.button("🚀 분석 기반 번호 생성", use_container_width=True):
                # 데이터 분석 시작
                cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']
                all_nums = df[cols].values.flatten().tolist()
                counts = Counter(all_nums)
                
                # 후보군: 자주 나온 번호 20개 + 나머지 섞기
                hot_candidates = [n for n, c in counts.most_common(20) if n not in exclude_nums]
                cold_candidates = [n for n in range(1, 46) if n not in exclude_nums]

                success = False
                # 필터링 통과를 위해 최대 300번 시도
                for _ in range(300):
                    res = set(include_nums)
                    needed = 6 - len(res)
                    
                    mix_pool = list(set(hot_candidates + random.sample(cold_candidates, 10)))
                    res.update(random.sample([n for n in mix_pool if n not in res], needed))
                    
                    final_list = sorted(list(res))
                    
                    # [필터 1] 총합 체크
                    if not (100 <= sum(final_list) <= 175): continue
                    # [필터 2] 홀짝 비율
                    odds = len([n for n in final_list if n % 2 != 0])
                    if odds not in [2, 3, 4]: continue
                    # [필터 3] 연속 번호 제한
                    is_consecutive = False
                    for i in range(len(final_list)-2):
                        if final_list[i]+1 == final_list[i+1] and final_list[i+1]+1 == final_list[i+2]:
                            is_consecutive = True; break
                    if is_consecutive: continue
                    
                    success = True
                    break

                if success:
                    st.balloons()
                    st.success(f"### 🎊 이번 주 추천 번호: {final_list}")
                    
                    # 공유용 텍스트 생성 및 복사 기능
                    st.write("📋 **친구에게 공유하기 (아래 박스 오른쪽 복사 클릭)**")
                    share_text = f"🎰 [로또 분석기 추천]\n분석회차: {total_rounds}회분\n추천번호: {final_list}\n함께 1등 가자! 🚀"
                    st.code(share_text, language=None)
                    
                    # 세션에 저장
                    st.session_state['lotto_history'].insert(0, final_list)
                else:
                    st.error("조건에 맞는 조합을 찾지 못했습니다. 제외 번호를 줄여보세요.")

        with col_hist:
            st.subheader("📜 최근 생성 이력")
            if st.session_state['lotto_history']:
                for i, h in enumerate(st.session_state['lotto_history'][:10]):
                    st.write(f"**{i+1}회:** `{h}`")
                if st.button("이력 삭제"):
                    st.session_state['lotto_history'] = []
                    st.rerun()
            else:
                st.write("아직 생성된 번호가 없습니다.")

    with tab2:
        st.subheader("📈 번호별 출현 빈도 순위")
        # 전체 데이터 빈도 계산
        all_nums_all = df[['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']].values.flatten().tolist()
        cnt = Counter(all_nums_all)
        freq_df = pd.DataFrame(cnt.most_common(45), columns=['번호', '빈도']).set_index('번호')
        st.bar_chart(freq_df)
        
        st.subheader("📅 데이터 확인 (최근 10회차)")
        st.dataframe(df.head(10), use_container_width=True)

else:
    st.error("lotto_data.csv 파일을 불러올 수 없습니다. GitHub에 파일이 있는지 확인해 주세요.")
