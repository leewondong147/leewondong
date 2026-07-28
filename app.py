import streamlit as st
import pandas as pd
import numpy as np
import random
import urllib3
from datetime import datetime
from itertools import combinations

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 0. 🛠️ [신규] 고급 통계 필터 함수 (AC값 계산기)
# ==========================================
def calculate_ac_value(numbers):
    """
    6개 숫자의 모든 조합 간 차이(간격)를 구하고 중복을 제거한 개수에서 5를 뺍니다.
    실제 1등 당첨 번호들은 대부분 AC값이 7 이상입니다.
    """
    diffs = set()
    for a, b in combinations(numbers, 2):
        diffs.add(abs(a - b))
    ac_value = len(diffs) - 5
    return ac_value

# ==========================================
# 앱 아이콘 및 페이지 설정 (Ver 5.0)
# ==========================================
st.set_page_config(page_title="이원동 로또 비밀 연구소", page_icon="🎯", layout="wide")
st.title("🎯 이원동의 '로또(Lotto) 스마트 매칭 & 패턴 연구소' (Ver 5.0 퀀트 분석판)")
st.caption("단순 생성을 넘어 합계 필터, AC값 분석, 최근 트렌드 가중치가 결합된 최첨단 하이브리드 엔진이 탑재되었습니다.")

# ==========================================
# 1. 🛡️ [로컬 데이터베이스 로드]
# ==========================================
@st.cache_data(ttl=3600)
def load_local_data():
    try:
        df_base = pd.read_csv('lotto_data.csv', on_bad_lines='skip')
        df_base["회차"] = pd.to_numeric(df_base["회차"].astype(str).str.replace('"', '').str.replace(',', ''), errors="coerce")
        df_base = df_base.dropna(subset=["회차"]).astype({"회차": int})
        return df_base, "로컬 데이터베이스 가동 중"
    except:
        return pd.DataFrame(), "⚠️ 데이터 없음 (엑셀 파일을 업로드해주세요)"

df_lotto, load_status = load_local_data()

# ==========================================
# 🚨 2. 전체 엑셀 파일 스마트 주입기 (좌표 탐색 유지)
# ==========================================
st.sidebar.divider()
st.sidebar.subheader("🚨 마스터 데이터 주입기")
uploaded_file = st.sidebar.file_uploader("전체 엑셀/CSV 파일 업로드", type=['csv', 'xlsx', 'xls'])

if uploaded_file is not None:
    try:
        try:
            df_up = pd.read_excel(uploaded_file, header=None)
        except:
            uploaded_file.seek(0)
            df_up = pd.read_html(uploaded_file.getvalue().decode('utf-8', errors='ignore'), header=None)[0]

        header_idx = -1
        idx_round = -1
        
        for i in range(min(len(df_up), 20)):
            row_list = df_up.iloc[i].fillna('').astype(str).tolist()
            row_str = "".join(row_list).replace(" ", "")
            if '회차' in row_str and '당첨번호' in row_str:
                header_idx = i
                for j, col_val in enumerate(row_list):
                    if '회차' in col_val:
                        idx_round = j
                        break
                break
        
        clean_rows = []
        if header_idx != -1 and idx_round != -1:
            df_data = df_up.iloc[header_idx+1:].copy()
            for _, row in df_data.iterrows():
                try:
                    rnd_str = str(row.iloc[idx_round]).replace(',','').replace('"', '').replace('회','').strip()
                    if not rnd_str.isdigit(): continue 
                    rnd = int(rnd_str)
                    n1 = int(float(str(row.iloc[idx_round+1]).replace(',','').strip()))
                    n2 = int(float(str(row.iloc[idx_round+2]).replace(',','').strip()))
                    n3 = int(float(str(row.iloc[idx_round+3]).replace(',','').strip()))
                    n4 = int(float(str(row.iloc[idx_round+4]).replace(',','').strip()))
                    n5 = int(float(str(row.iloc[idx_round+5]).replace(',','').strip()))
                    n6 = int(float(str(row.iloc[idx_round+6]).replace(',','').strip()))
                    bn = int(float(str(row.iloc[idx_round+7]).replace(',','').strip()))
                    if n1 > 0 and n6 > 0:
                        clean_rows.append({
                            "회차": rnd, "년도": "2024",
                            "번호1": n1, "번호2": n2, "번호3": n3, 
                            "번호4": n4, "번호5": n5, "번호6": n6, "보너스": bn
                        })
                except:
                    pass
        
        df_cleaned_up = pd.DataFrame(clean_rows)
        if not df_cleaned_up.empty:
            df_lotto = df_cleaned_up.sort_values(by="회차", ascending=True)
            df_lotto.to_csv('lotto_data.csv', index=False)
            st.sidebar.success(f"✅ 마스터 데이터 정제 및 저장 완료! (총 {len(df_lotto)}개 회차 적용)")
        else:
            st.sidebar.error("⚠️ 번호 데이터를 추출하지 못했습니다.")
    except Exception as e:
        st.sidebar.error(f"⚠️ 업로드 처리 에러: {e}")

# ==========================================
# 3. 수치화 표출 및 데이터 연산 로직
# ==========================================
st.sidebar.success(f"📡 현재 상태: {load_status}")
if not df_lotto.empty:
    st.sidebar.metric(label="현재 분석 중인 최신 회차", value=f"{int(df_lotto['회차'].max())}회")

all_numbers, even_count, odd_count = [], 0, 0
recent_15_numbers = [] # 💡 최신 15주 트렌드를 담을 빈 바구니

if not df_lotto.empty:
    target_cols = ["번호1", "번호2", "번호3", "번호4", "번호5", "번호6"]
    
    # 전체 누적 빈도 계산
    for col in target_cols:
        if col in df_lotto.columns:
            vals = pd.to_numeric(df_lotto[col], errors="coerce").dropna().astype(int).tolist()
            all_numbers.extend(vals)
            for v in vals:
                if v % 2 == 0: even_count += 1
                else: odd_count += 1
                
    # 💡 최신 15주 데이터만 별도로 잘라내서 빈도 계산
    df_recent = df_lotto.tail(15)
    for col in target_cols:
        if col in df_recent.columns:
            recent_vals = pd.to_numeric(df_recent[col], errors="coerce").dropna().astype(int).tolist()
            recent_15_numbers.extend(recent_vals)

frequency = pd.Series(all_numbers).value_counts().reindex(range(1, 46), fill_value=0)
recent_frequency = pd.Series(recent_15_numbers).value_counts().reindex(range(1, 46), fill_value=0)

# ==========================================
# 4. 🔮 UI 탭 구성
# ==========================================
tab1, tab2 = st.tabs(["📊 역대 통계 및 비율 분석", "🚀 필터 장착 가중치 번호 추출기"])

with tab1:
    st.subheader("📊 역대 당첨 데이터 패턴 종합 대시보드")
    df_freq_disp = pd.DataFrame({"숫자": [f"{i}번" for i in frequency.index], "출현횟수": frequency.values}).sort_values(by="출현횟수", ascending=False)
    
    c1, c2, c3 = st.columns([1, 1.2, 1.8])
    with c1:
        st.write("🏆 **최다 출현 Top 7**")
        st.dataframe(df_freq_disp.head(7), use_container_width=True, hide_index=True)
    with c2:
        st.write("📉 **최소 출현 Top 7**")
        st.dataframe(df_freq_disp.tail(7), use_container_width=True, hide_index=True)
    with c3:
        st.write("⚖️ **역대 홀짝 비율**")
        tot = even_count + odd_count
        if tot > 0:
            st.info(f"🔵 **홀수: {(odd_count/tot)*100:.1f}%**  |  🔴 **짝수: {(even_count/tot)*100:.1f}%**")
        st.bar_chart(pd.DataFrame({"출현빈도": [float(v) for v in frequency.values]}, index=list(range(1, 46))))

with tab2:
    st.subheader("🚀 하이브리드 필터가 적용된 정밀 번호 추출기")
    strat = st.sidebar.radio("🎯 핵심 확률 전략 선택", [
        "🔥 하이브리드 가중치 (전체 다출수 + 최근 15주 트렌드 반영)", 
        "❄️ 역발상 가중치 (희귀 번호 선호)"
    ])
    ex_input = st.sidebar.text_input("❌ 제외 번호 (쉼표 구분):", "4, 13, 44")
    n_sets = st.sidebar.slider("🎲 통과시킬 조합 수", 1, 10, 5)
    
    ex_nums = [int(x.strip()) for x in ex_input.split(",") if x.strip().isdigit()] if ex_input else []

    if st.button("🚀 정밀 필터링 조합 엔진 가동"):
        st.balloons()
        avail = [n for n in range(1, 46) if n not in ex_nums]
        
        # 💡 전략에 따른 가중치 부여 (가중치가 높을수록 뽑힐 확률이 올라갑니다)
        if "🔥" in strat:
            # 전체 출현 횟수와 최근 15주 출현 횟수를 섞어 강력한 트렌드 가중치를 만듭니다.
            w = [(frequency.get(n, 1) + (recent_frequency.get(n, 0) * 3)) for n in avail]
        else:
            w = [(frequency.max() - frequency.get(n, 0)) + 1 for n in avail]
            
        norm_w = [x / sum(w) for x in w]
        
        res = []
        attempts = 0 # 코드가 번호를 뽑기 위해 시도한 횟수를 기록합니다.
        
        # 💡 [핵심 알고리즘] 원하는 조합 수가 채워질 때까지 무한 반복합니다.
        while len(res) < n_sets:
            attempts += 1
            # 가중치를 바탕으로 번호 6개를 뽑습니다.
            nums = sorted(np.random.choice(avail, 6, replace=False, p=norm_w))
            
            # [필터 1] 합계가 120 미만이거나 180을 초과하면 버립니다.
            total_sum = sum(nums)
            if total_sum < 120 or total_sum > 180:
                continue
                
            # [필터 2] AC값이 7 미만인 단순한 패턴은 버립니다.
            ac = calculate_ac_value(nums)
            if ac < 7:
                continue
                
            # 모든 필터를 통과한 '정예 번호'만 결과 바구니에 담습니다.
            odds = len([x for x in nums if x%2!=0])
            evens = len([x for x in nums if x%2==0])
            
            res.append({
                "조합": f"✨ 세트 {len(res)+1}", 
                "번호1": nums[0], "번호2": nums[1], "번호3": nums[2],
                "번호4": nums[3], "번호5": nums[4], "번호6": nums[5],
                "총합 (120~180)": total_sum,
                "AC값 (7이상)": ac,
                "홀짝 분포": f"{odds} : {evens}"
            })
            
        st.success(f"🎯 촘촘한 필터링을 거쳐 번호 매칭을 완료했습니다! (내부 필터링 횟수: {attempts}회)")
        st.dataframe(pd.DataFrame(res), use_container_width=True, hide_index=True)
