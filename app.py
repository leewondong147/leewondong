import streamlit as st
import pandas as pd
import numpy as np
import random
import requests
import time
from datetime import datetime

# ==========================================
# 0. 🕒 [신규] 최신 회차 자동 계산 엔진
# ==========================================
def get_latest_draw_number():
    """오늘 날짜를 기준으로 가장 최근에 추첨된 로또 회차를 계산합니다."""
    # 1회차 추첨일 (2002년 12월 7일 21시 기준)
    first_draw_date = datetime(2002, 12, 7, 21, 0, 0)
    now = datetime.now()
    delta = now - first_draw_date
    return (delta.days // 7) + 1

# ==========================================
# 앱 아이콘 및 페이지 설정 (Ver 2.8)
# ==========================================
st.set_page_config(page_title="이원동 로또 비밀 연구소", page_icon="🎯", layout="wide")
st.title("🎯 이원동의 '로또(Lotto) 스마트 매칭 & 패턴 연구소' (Ver 2.8)")
st.caption("절대 날짜 기반 추적 엔진 탑재! 서버 지연을 극복하고 최신 회차를 영구적으로 자동 동기화합니다.")

# ==========================================
# 1. 📡 [실시간 고속 크롤링 엔진]
# ==========================================
def fetch_lotto_api(drw_no):
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
# 2. 🛡️ [하이브리드 예외처리 및 데이터 정제 엔진]
# ==========================================
@st.cache_data(ttl=3600)
def load_and_sync_lotto_data():
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
        df_base = pd.read_csv('lotto_data.csv', on_bad_lines='skip')
        status_msg = "로컬 CSV 데이터베이스 로드 완료"
        
        df_base["회차"] = df_base["회차"].astype(str).str.replace('"', '').str.replace(',', '').str.strip()
        df_base["회차"] = pd.to_numeric(df_base["회차"], errors="coerce")
        df_base = df_base.dropna(subset=["회차"])
        df_base["회차"] = df_base["회차"].astype(int)
        
    except FileNotFoundError:
        df_base.to_csv('lotto_data.csv', index=False)
        status_msg = "로컬 lotto_data.csv 신규 생성"
    except Exception as e:
        status_msg = f"⚠️ 가상 백업 구동 모드 전환"

    try:
        if not df_base.empty and "회차" in df_base.columns:
            last_saved_round = int(df_base["회차"].max())
            target_latest_round = get_latest_draw_number() # 💡 실제 최신 회차 계산!
            
            # 💡 while 루프를 버리고, 정확한 목표치를 향해 달리는 for 루프로 변경!
            if last_saved_round < target_latest_round:
                new_rows = []
                for next_round in range(last_saved_round + 1, target_latest_round + 1):
                    api_data = fetch_lotto_api(next_round)
                    if api_data is None:
                        # 통신 장애가 발생해도 무한히 멈추지 않고, 수집된 곳까지만 안전하게 저장
                        break 
                    new_rows.append(api_data)
                    time.sleep(0.1) # 서버 보호
                
                if new_rows:
                    df_new = pd.DataFrame(new_rows)
                    df_base = pd.concat([df_base, df_new], ignore_index=True)
                    df_base = df_base.drop_duplicates(subset=["회차"], keep="last")
                    df_base["회차"] = df_base["회차"].astype(int)
                    df_base = df_base.sort_values(by="회차", ascending=True)
                    
                    df_base.to_csv('lotto_data.csv', index=False)
                    status_msg += f" (🚀 누락되었던 {len(new_rows)}개 최신 회차 동기화 완료!)"
            elif last_saved_round == target_latest_round:
                status_msg += " (✅ 현재 최신 회차 유지 중)"
                
    except Exception as e:
        status_msg += " (⚠️ 서버 연결 일시 지연)"
        
    return df_base, status_msg

df_lotto, load_status = load_and_sync_lotto_data()

# ==========================================
# 3. 수치화 표출부
# ==========================================
st.sidebar.success(f"📡 데이터 네트워크: {load_status}")
if "회차" in df_lotto.columns and not df_lotto.empty:
    max_round = int(df_lotto['회차'].max())
    st.sidebar.metric(label="현재 확보된 최신 회차", value=f"{max_round}회")

# ==========================================
# 4. 📊 융합형 연산 (대표님 실전 CSV 최적화 파싱 알고리즘)
# ==========================================
all_numbers = []
even_count = 0
odd_count = 0

try:
    if "회차" in df_lotto.columns:
        col_list = list(df_lotto.columns)
        idx_round = col_list.index("회차")
        
        target_cols = col_list[idx_round + 1 : idx_round + 7]
        
        for col in target_cols:
            df_lotto[col] = pd.to_numeric(df_lotto[col], errors="coerce")
            list_vals = df_lotto[col].dropna().astype(int).tolist()
            all_numbers.extend(list_vals)
            for val in list_vals:
                if val % 2 == 0:
                    even_count += 1
                else:
                    odd_count += 1
except:
    pass

if not all_numbers:
    all_numbers = [random.randint(1, 45) for _ in range(300)]

frequency = pd.Series(all_numbers).value_counts().reindex(range(1, 46), fill_value=0)

# ==========================================
# 5. 🔮 UI 탭 구성
# ==========================================
tab1, tab2 = st.tabs(["📊 역대 통계 및 홀짝 비율 분석", "🔮 가중치 전략 번호 생성기"])

with tab1:
    st.subheader("📊 역대 당첨 데이터 패턴 종합 대시보드")
    
    df_freq_display = pd.DataFrame({
        "숫자": [f"{i}번" for i in frequency.index],
        "출현횟수": frequency.values
    }).sort_values(by="출현횟수", ascending=False)
    
    col1, col2, col3 = st.columns([1, 1.2, 1.8])
    with col1:
        st.write("🏆 **최다 출현 번호 Top 7**")
        st.dataframe(df_freq_display.head(7), use_container_width=True, hide_index=True)
        
    with col2:
        st.write("📉 **최소 출현 번호 Top 7**")
        st.dataframe(df_freq_display.tail(7), use_container_width=True, hide_index=True)
        
    with col3:
        st.write("⚖️ **역대 당첨 번호 홀수 vs 짝수 비율**")
        total_balls = even_count + odd_count
        if total_balls > 0:
            even_pct = (even_count / total_balls) * 100
            odd_pct = (odd_count / total_balls) * 100
            st.info(f"🔵 **홀수(Odd): {odd_pct:.1f}%**  |  🔴 **짝수(Even): {even_pct:.1f}%**")
        
        st.write("📈 **1~45 번호별 출현 빈도 바 차트 (가로축: 번호순 정렬)**")
        df_chart_data = pd.DataFrame({
            "출현빈도": [float(val) for val in frequency.values]
        }, index=list(range(1, 46)))
        st.bar_chart(df_chart_data)

with tab2:
    st.subheader("🔮 패턴 전략 가중치 번호 추출기")
    
    st.sidebar.write("---")
    st.sidebar.subheader("⚙️ 고도화 전략 설정")
    strategy_mode = st.sidebar.radio("🎯 분석 가중치 필터 선택", ["🔥 다출수 가중치 (많이 나온 번호 선호)", "❄️ 미출수 가중치 (희귀 번호 선호)"])
    exclude_input = st.sidebar.text_input("❌ 제외 번호 입력 (쉼표 구분):", value="4, 13, 44")
    num_sets = st.sidebar.slider("🎲 생성할 조합 수", min_value=1, max_value=10, value=5)
    
    exclude_nums = []
    if exclude_input:
        try:
            exclude_nums = [int(x.strip()) for x in exclude_input.split(",") if x.strip().isdigit()]
        except:
            pass

    if st.button("🚀 특수 가중치 조합 엔진 실시간 가동"):
        st.balloons()
        
        available_numbers = [n for n in range(1, 46) if n not in exclude_nums]
        
        if strategy_mode == "🔥 다출수 가중치 (많이 나온 번호 선호)":
            weights = [frequency.get(n, 1) + 1 for n in available_numbers]
        else:
            max_freq = frequency.max()
            weights = [(max_freq - frequency.get(n, 0)) + 1 for n in available_numbers]
            
        sum_weights = sum(weights)
        norm_weights = [w / sum_weights for w in weights]
        
        generated_results = []
        for i in range(num_sets):
            set_nums = np.random.choice(available_numbers, size=6, replace=False, p=norm_weights)
            set_nums = sorted(set_nums)
            
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
