import streamlit as st
import pandas as pd
import numpy as np
import random
import requests
import time
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def get_latest_draw_number():
    first_draw_date = datetime(2002, 12, 7, 21, 0, 0)
    return ((datetime.now() - first_draw_date).days // 7) + 1

# ==========================================
# 앱 아이콘 및 페이지 설정 (Ver 3.2)
# ==========================================
st.set_page_config(page_title="이원동 로또 비밀 연구소", page_icon="🎯", layout="wide")
st.title("🎯 이원동의 '로또(Lotto) 스마트 매칭 & 패턴 연구소' (Ver 3.2)")
st.caption("동행복권 원본 엑셀의 불필요한 정보를 제거하고 순수 번호만 추출하는 '스마트 정수기 필터'가 장착되었습니다.")

# ==========================================
# 1. 📡 [데이터 크롤링 및 정제 엔진]
# ==========================================
def fetch_lotto_api(drw_no):
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={drw_no}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    try:
        res = requests.get(url, headers=headers, timeout=5, verify=False)
        if res.status_code == 200:
            data = res.json()
            if data.get("returnValue") == "success":
                return {
                    "회차": int(data["drwNo"]), "년도": data["drwNoDate"].split("-")[0],
                    "번호1": int(data["drwtNo1"]), "번호2": int(data["drwtNo2"]),
                    "번호3": int(data["drwtNo3"]), "번호4": int(data["drwtNo4"]),
                    "번호5": int(data["drwtNo5"]), "번호6": int(data["drwtNo6"]),
                    "보너스": int(data["bnusNo"])
                }
    except:
        pass
    return None

@st.cache_data(ttl=3600)
def load_and_sync_lotto_data():
    df_base = pd.DataFrame()
    status_msg = ""
    try:
        df_base = pd.read_csv('lotto_data.csv', on_bad_lines='skip')
        df_base["회차"] = pd.to_numeric(df_base["회차"].astype(str).str.replace('"', '').str.replace(',', ''), errors="coerce")
        df_base = df_base.dropna(subset=["회차"]).astype({"회차": int})
        status_msg = "로컬 데이터베이스 로드 완료"
        
        last_saved = int(df_base["회차"].max())
        target_latest = get_latest_draw_number()
        
        if last_saved < target_latest:
            new_rows = []
            for n_round in range(last_saved + 1, target_latest + 1):
                data = fetch_lotto_api(n_round)
                if data is None:
                    status_msg += " (⚠️ 클라우드 차단 우회 대기중)"
                    break 
                new_rows.append(data)
                time.sleep(0.5)
            
            if new_rows:
                df_base = pd.concat([df_base, pd.DataFrame(new_rows)], ignore_index=True).drop_duplicates(subset=["회차"], keep="last")
                df_base.to_csv('lotto_data.csv', index=False)
                status_msg += f" (🚀 {len(new_rows)}개 최신 회차 동기화 완료)"
    except Exception:
        status_msg = "⚠️ 초기 데이터 로드 실패"
        
    return df_base, status_msg

df_lotto, load_status = load_and_sync_lotto_data()

# ==========================================
# 🚨 2. [핵심] 엑셀 스마트 정수기 (데이터 주입부)
# ==========================================
st.sidebar.divider()
st.sidebar.subheader("🚨 수동 데이터 주입기")
uploaded_file = st.sidebar.file_uploader("동행복권 원본 엑셀 업로드", type=['csv', 'xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # 파일 형식에 따라 안전하게 읽기
        if uploaded_file.name.endswith('.csv'):
            df_up = pd.read_csv(uploaded_file, dtype=str, on_bad_lines='skip')
        else:
            try:
                df_up = pd.read_excel(uploaded_file, dtype=str, header=None)
            except:
                df_up = pd.read_html(uploaded_file, encoding='utf-8', header=None)[0]

        # 💡 [스마트 필터] 동행복권 양식에서 진짜 제목줄(회차, 1~6 번호가 있는 줄)을 찾아냅니다.
        header_idx = -1
        for i in range(min(len(df_up), 15)):
            row_str = "".join(df_up.iloc[i].fillna('').astype(str))
            if '회차' in row_str and ('1' in row_str or '번호1' in row_str):
                header_idx = i
                break
        
        clean_rows = []
        if header_idx != -1:
            df_up.columns = df_up.iloc[header_idx].fillna('').astype(str).str.replace(' ', '')
            df_data = df_up.iloc[header_idx+1:].copy()
            
            # 💡 이물질(당첨금 등)을 버리고 순수한 번호만 새 통(clean_rows)에 옮겨 담습니다.
            for _, row in df_data.iterrows():
                try:
                    rnd = int(str(row.get('회차', '')).replace(',','').replace('"', '').replace('회',''))
                    # 원본 엑셀의 컬럼명이 '1'이든, 우리 앱의 '번호1'이든 유연하게 대처합니다.
                    n1 = int(str(row.get('1', row.get('번호1', '0'))).replace(',',''))
                    n2 = int(str(row.get('2', row.get('번호2', '0'))).replace(',',''))
                    n3 = int(str(row.get('3', row.get('번호3', '0'))).replace(',',''))
                    n4 = int(str(row.get('4', row.get('번호4', '0'))).replace(',',''))
                    n5 = int(str(row.get('5', row.get('번호5', '0'))).replace(',',''))
                    n6 = int(str(row.get('6', row.get('번호6', '0'))).replace(',',''))
                    bn = int(str(row.get('보너스', '0')).replace(',',''))
                    
                    if n1 > 0 and n6 > 0:
                        clean_rows.append({
                            "회차": rnd, "년도": "2024",
                            "번호1": n1, "번호2": n2, "번호3": n3, "번호4": n4, "번호5": n5, "번호6": n6, "보너스": bn
                        })
                except:
                    pass
        
        df_cleaned_up = pd.DataFrame(clean_rows)
        
        if not df_cleaned_up.empty:
            # 완벽하게 씻어낸 번호 데이터를 기존 데이터와 합칩니다.
            df_lotto = pd.concat([df_lotto, df_cleaned_up]).drop_duplicates(subset=["회차"], keep="last")
            df_lotto = df_lotto.sort_values(by="회차", ascending=True)
            st.sidebar.success(f"✅ 원본 엑셀 정제 완료! (최신 {int(df_lotto['회차'].max())}회 적용)")
        else:
            st.sidebar.error("⚠️ 번호 데이터를 추출하지 못했습니다.")
    except Exception as e:
        st.sidebar.error(f"⚠️ 업로드 처리 에러: {e}")

# ==========================================
# 3. 수치화 표출 및 데이터 연산 로직
# ==========================================
st.sidebar.success(f"📡 네트워크 상태: {load_status}")
if not df_lotto.empty:
    st.sidebar.metric(label="현재 확보된 최신 회차", value=f"{int(df_lotto['회차'].max())}회")

# 💡 [핵심 계산법 교체] 열 순서에 의존하지 않고, 정확히 이름이 "번호O"인 기둥만 모아서 계산합니다!
all_numbers, even_count, odd_count = [], 0, 0
if not df_lotto.empty:
    target_cols = ["번호1", "번호2", "번호3", "번호4", "번호5", "번호6"]
    for col in target_cols:
        if col in df_lotto.columns:
            vals = pd.to_numeric(df_lotto[col], errors="coerce").dropna().astype(int).tolist()
            all_numbers.extend(vals)
            for v in vals:
                if v % 2 == 0: even_count += 1
                else: odd_count += 1

frequency = pd.Series(all_numbers).value_counts().reindex(range(1, 46), fill_value=0)

# ==========================================
# 4. 🔮 UI 탭 구성
# ==========================================
tab1, tab2 = st.tabs(["📊 역대 통계 및 비율 분석", "🔮 가중치 전략 번호 생성기"])

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
    st.subheader("🔮 패턴 전략 가중치 번호 추출기")
    strat = st.sidebar.radio("🎯 전략 선택", ["🔥 다출수 가중치", "❄️ 미출수 가중치"])
    ex_input = st.sidebar.text_input("❌ 제외 번호 (쉼표 구분):", "4, 13, 44")
    n_sets = st.sidebar.slider("🎲 생성 조합 수", 1, 10, 5)
    
    ex_nums = [int(x.strip()) for x in ex_input.split(",") if x.strip().isdigit()] if ex_input else []

    if st.button("🚀 조합 엔진 가동"):
        st.balloons()
        avail = [n for n in range(1, 46) if n not in ex_nums]
        
        if "🔥" in strat:
            w = [frequency.get(n, 1) + 1 for n in avail]
        else:
            w = [(frequency.max() - frequency.get(n, 0)) + 1 for n in avail]
            
        norm_w = [x / sum(w) for x in w]
        
        res = []
        for i in range(n_sets):
            nums = sorted(np.random.choice(avail, 6, replace=False, p=norm_w))
            res.append({
                "조합": f"✨ 세트 {i+1}", "번호1": nums[0], "번호2": nums[1], "번호3": nums[2],
                "번호4": nums[3], "번호5": nums[4], "번호6": nums[5],
                "홀짝 분포": f"{len([x for x in nums if x%2!=0])} : {len([x for x in nums if x%2==0])}"
            })
        st.success("🎯 매칭 완료!")
        st.dataframe(pd.DataFrame(res), use_container_width=True, hide_index=True)
