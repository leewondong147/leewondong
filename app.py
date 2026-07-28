import streamlit as st
import pandas as pd
import numpy as np
import random
import time
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 앱 아이콘 및 페이지 설정 (Ver 4.0)
# ==========================================
st.set_page_config(page_title="이원동 로또 비밀 연구소", page_icon="🎯", layout="wide")
st.title("🎯 이원동의 '로또(Lotto) 스마트 매칭 & 패턴 연구소' (Ver 4.0)")
st.caption("1회~최신회차 전체 마스터 엑셀 파일을 완벽하게 해독하여 대시보드를 구성합니다.")

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
# 🚨 2. [핵심] 전체 엑셀 파일 스마트 주입기
# ==========================================
st.sidebar.divider()
st.sidebar.subheader("🚨 마스터 데이터 주입기")
st.sidebar.caption("동행복권에서 받은 '1회~최신회차' 전체 엑셀 파일을 드래그하여 업로드하세요.")
uploaded_file = st.sidebar.file_uploader("전체 엑셀/CSV 파일 업로드", type=['csv', 'xlsx', 'xls'])

if uploaded_file is not None:
    try:
        # 파일 형식에 맞춰 안전하게 읽기
        if uploaded_file.name.endswith('.csv'):
            df_up = pd.read_csv(uploaded_file, dtype=str, on_bad_lines='skip')
        else:
            try:
                df_up = pd.read_excel(uploaded_file, dtype=str, header=None)
            except:
                df_up = pd.read_html(uploaded_file, encoding='utf-8', header=None)[0]

        # 💡 [스마트 스캐너] 동행복권 양식의 '진짜 제목줄' 찾기
        header_idx = -1
        for i in range(min(len(df_up), 20)):
            row_str = "".join(df_up.iloc[i].fillna('').astype(str))
            if '회차' in row_str and ('1' in row_str or '번호1' in row_str):
                header_idx = i
                break
        
        clean_rows = []
        if header_idx != -1:
            df_up.columns = df_up.iloc[header_idx].fillna('').astype(str).str.replace(' ', '')
            df_data = df_up.iloc[header_idx+1:].copy()
            
            # 💡 1회부터 1234회까지 방대한 데이터에서 '번호'만 순식간에 추출합니다.
            for _, row in df_data.iterrows():
                try:
                    rnd = int(str(row.get('회차', '')).replace(',','').replace('"', '').replace('회',''))
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
            # 💡 [핵심 변경] 기존 데이터를 무시하고, 방금 올린 '마스터 데이터'로 덮어씁니다!
            df_lotto = df_cleaned_up.sort_values(by="회차", ascending=True)
            df_lotto.to_csv('lotto_data.csv', index=False) # 다음번 접속을 위해 로컬에 저장
            st.sidebar.success(f"✅ 마스터 데이터 정제 및 저장 완료! (총 {len(df_lotto)}개 회차 적용)")
        else:
            st.sidebar.error("⚠️ 번호 데이터를 추출하지 못했습니다. 동행복권 원본 파일이 맞는지 확인해 주세요.")
    except Exception as e:
        st.sidebar.error(f"⚠️ 업로드 처리 에러: {e}")

# ==========================================
# 3. 수치화 표출 및 데이터 연산 로직
# ==========================================
st.sidebar.success(f"📡 현재 상태: {load_status}")
if not df_lotto.empty:
    st.sidebar.metric(label="현재 분석 중인 최신 회차", value=f"{int(df_lotto['회차'].max())}회")

# 💡 '번호1' ~ '번호6' 기둥을 찾아 1234회 분량의 숫자를 전부 모읍니다.
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
    strat = st.sidebar.radio("🎯 전략 선택", ["🔥 다출수 가중치 (많이 나온 번호 선호)", "❄️ 미출수 가중치 (희귀 번호 선호)"])
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
