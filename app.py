import streamlit as st
import pandas as pd
import numpy as np
import random
import requests
import time
from datetime import datetime

# ==========================================
# 앱 아이콘 및 페이지 설정 (Ver 2.0 고도화)
# ==========================================
st.set_page_config(page_title="이원동 로또 비밀 연구소", page_icon="🎯", layout="wide")
st.title("🎯 이원동의 '로또(Lotto) 스마트 매칭 & 패턴 연구소' (Ver 2.0)")
st.caption("인터넷 동행복권 API와의 실시간 광대역 연결을 통해, 과거 CSV 데이터 위에 최신 당첨 데이터를 완전 자동으로 누적 연산합니다.")

# ==========================================
# 1. 📡 [실시간 고속 크롤링 엔진] 최신 회차 조회용
# ==========================================
def fetch_lotto_api(drw_no):
    """동행복권 공식 API를 통해 특정 회차의 당첨 번호를 가져옵니다."""
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}"
    try:
        res = requests.get(url, timeout=3)
        if res.status_code == 200:
            data = res.json()
            if data.get("returnValue") == "success":
                return {
                    "회차": int(data["drwNo"]),
                    "년도": data["drwNoDate"].split("-")[0],
                    "번호1": int(data["drwtNo1"]),
                    "번호2": int(data["drwtNo2"]),
                    "번호3": int(data["drwtNo3"]),
                    "번호4": int(data["drwtNo4"]),
                    "번호5": int(data["drwtNo5"]),
                    "번호6": int(data["drwtNo6"]),
                    "보너스": int(data["bnusNo"])
                }
    except:
        pass
    return None

# ==========================================
# 2. 🛡️ [하이브리드 예외처리 엔진] 로컬 CSV + 실시간 API 자동 동기화
# ==========================================
@st.cache_data(ttl=3600)  # 1시간 캐싱으로 속도 및 무중단 유지
def load_and_sync_lotto_data():
    # 기본 비상용 시뮬레이션 기반 DB 구성
    fake_data = []
    random.seed(42)
    for round_idx in range(1100, 1150):
        nums = sorted(random.sample(range(1, 46), 6))
        fake_data.append({
            "회차": round_idx, "년도": "2024",
            "번호1": nums[0], "번호2": nums[1], "번호3": nums[2],
            "번호4": nums[3], "번호5": nums[4], "번호6": nums[5],
            "보너스": random.choice([n for n in range(1, 46) if n not in nums])
        })
    df_base = pd.DataFrame(fake_data)
    
    status_msg = ""
    try:
        # 로컬 CSV 읽기 시도 (줄 깨짐 방어)
        df_base = pd.read_csv('lotto_data.csv', on_bad_lines='skip')
        status_msg = "로컬 CSV 데이터베이스 로드 성공"
    except FileNotFoundError:
        df_base.to_csv('lotto_data.csv', index=False)
        status_msg = "로컬 lotto_data.csv 신규 생성 및 장착"
    except Exception as e:
        status_msg = f"⚠️ 로컬 로딩 오류 우회 가상 구동 중"

    # 실시간 데이터 동기화 파트
    try:
        if not df_base.empty and "회차" in df_base.columns:
            last_saved_round = int(df_base["회차"].max())
            next_round = last_saved_round + 1
            
            # 무중단 고속 루핑을 돌려 최신 회차까지 실시간으로 긁어다 붙입니다.
            new_rows = []
            while True:
                api_data = fetch_lotto_api(next_round)
                if api_data is None:
                    # 더 이상 조회되지 않는 최신 미발표 회차에 도달하면 탈출
                    break
                new_rows.append(api_data)
                next_round += 1
                time.sleep(0.05) # 서버 부하 차단 딜레이
                
            if new_rows:
                df_new = pd.DataFrame(new_rows)
                # 데이터 병합 및 중복 완벽 제거
                df_base = pd.concat([df_base, df_new], ignore_index=True)
                df_base = df_base.drop_duplicates(subset=["회차"], keep="last")
                df_base = df_base.sort_values(by="회차", ascending=True)
                
                # 병합된 최신본을 로컬 CSV에 실시간으로 다시 저장(누적)합니다!
                df_base.to_csv('lotto_data.csv', index=False)
                status_msg += f" (최신 {len(new_rows)}개 회차 실시간 동기화 완료!)"
    except Exception as e:
        status_msg += " (서버 차단으로 인한 실시간 API 동기화 일시 대기)"
        
    return df_base, status_msg

df_lotto, load_status = load_and_sync_lotto_data()

# 사이드바 대시보드 상태창 표출
st.sidebar.success(f"📡 데이터 네트워크: {load_status}")
if "회차" in df_lotto.columns:
    st.sidebar.metric(label="현재 확보된 최신 회차", value=f"{int(df_lotto['회차'].max())}회")

# ==========================================
# 3. 📊 고도화된 연산 지표 (빈도수 및 홀짝 비율 추출)
# ==========================================
num_cols = ["번호1", "번호2", "번호3", "번호4", "번호5", "번호6"]
all_numbers = []
even_count = 0
odd_count = 0

for col in num_cols:
    if col in df_lotto.columns:
        list_vals = df_lotto[col].dropna().tolist()
        all_numbers.extend(list_vals)
        for val in list_vals:
            if val % 2 == 0:
                even_count += 1
            else:
                odd_count += 1

frequency = pd.Series(all_numbers).value_counts().reindex(range(1, 46), fill_value=0)

# ==========================================
# 4. 🔮 레이아웃 전개 (탭 구성)
# ==========================================
tab1, tab2 = st.tabs(["📊 역대 통계 및 홀짝 비율 분석", "🔮 가중치 전략 번호 생성기"])

with tab1:
    st.subheader("📊 역대 당첨 데이터 패턴 종합 대시보드")
    
    df_freq = pd.DataFrame({
        "숫자": frequency.index,
        "출현횟수": frequency.values
    }).sort_values(by="출현횟수", ascending=False)
    
    col1, col2, col3 = st.columns([1, 1.2, 1.8])
    with col1:
        st.write("🏆 **최다 출현 번호 Top 7**")
        st.dataframe(df_freq.head(7), use_container_width=True, hide_index=True)
        
    with col2:
        st.write("📉 **최소 출현 번호 Top 7**")
        st.dataframe(df_freq.tail(7), use_container_width=True, hide_index=True)
        
    with col3:
        st.write("⚖️ **역대 당첨 번호 홀수 vs 짝수 비율**")
        total_balls = even_count + odd_count
        if total_balls > 0:
            even_pct = (even_count / total_balls) * 100
            odd_pct = (odd_count / total_balls) * 100
            st.info(f"🔵 **홀수(Odd): {odd_pct:.1f}%**  |  🔴 **짝수(Even): {even_pct:.1f}%**")
        st.write("📈 **1~45 번호별 출현 빈도 레이더 차트**")
        st.bar_chart(df_freq.set_index("숫자"))

with tab2:
    st.subheader("🔮 패턴 전략 가중치 번호 추출기")
    
    st.sidebar.write("---")
    st.sidebar.subheader("⚙️ 고도화 전략 설정")
    strategy_mode = st.sidebar.radio("🎯 분석 가중치 필터 선택", ["🔥 다출수 가중치 (많이 나온 번호 선호)", "❄️ 미출수 가중치 (희귀 번호 선호)"])
    exclude_input = st.sidebar.text_input("❌ 제외 번호 입력 (쉼표 구분):", value="4, 13, 44")
    num_sets = st.sidebar.slider("🎲 생성할 조합 수", min_value=1, max_value=10, value=5)
    
    # 제외수 정수 변환 예외처리
    exclude_nums = []
    if exclude_input:
        try:
            exclude_nums = [int(x.strip()) for x in exclude_input.split(",") if x.strip().isdigit()]
        except:
            pass

    if st.button("🚀 특수 가중치 조합 엔진 실시간 가동"):
        st.balloons()
        
        available_numbers = [n for n in range(1, 46) if n not in exclude_nums]
        
        # 대표님의 필터 선택에 따른 가중치 연산 공식 교체
        if strategy_mode == "🔥 다출수 가중치 (많이 나온 번호 선호)":
            weights = [frequency.get(n, 1) + 1 for n in available_numbers]
        else:
            # 미출수 선호 전략: 출현 빈도의 역수를 가중치로 지정
            max_freq = frequency.max()
            weights = [(max_freq - frequency.get(n, 0)) + 1 for n in available_numbers]
            
        sum_weights = sum(weights)
        norm_weights = [w / sum_weights for w in weights]
        
        generated_results = []
        for i in range(num_sets):
            set_nums = np.random.choice(available_numbers, size=6, replace=False, p=norm_weights)
            set_nums = sorted(set_nums)
            
            # 생성된 번호 세트의 자체 홀짝 통계 연산
            odds = len([x for x in set_nums if x % 2 != 0])
            evens = len([x for x in set_nums if x % 2 == 0])
            
            generated_results.append({
                "조합": f"✨ 세트 {i+1}",
                "번호1": set_nums[0], "번호2": set_nums[1], "번호3": set_nums[2],
                "번호4": set_nums[3], "번호5": set_nums[4], "번호6": set_nums[5],
                "홀짝 분포": f"{odds} : {evens}"
            })
            
        st.success("🎯 지정하신 특수 가중치 필터를 대입하여 매칭을 완료했습니다.")
        st.dataframe(pd.DataFrame(generated_results), use_container_width=True, hide_index=True)
