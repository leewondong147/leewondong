import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 6.6)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        # 2. 진짜 제목 줄 찾기
        header_row = 0
        for i in range(len(df_raw)):
            row_str = "".join([str(v) for v in df_raw.iloc[i].values])
            if '작성일자' in row_str and '공급가액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 3. 🔍 기둥 이름 강제 매칭 (기존 방식보다 훨씬 강력함)
        # 상호명: '상호'나 '공급자'가 들어간 기둥
        c_name = next((c for c in df.columns if '상호' in str(c) or '공급자' in str(c)), df.columns[6])
        # 공급가액: '공급가액' 글자가 있고, '합계'가 아닌 것
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '합계' not in str(c)), None)
        # 세액: '세액' 글자가 있고, '합계'가 아닌 것
        c_tax = next((c for c in df.columns if '세액' in str(c) and '합계' not in str(c)), None)
        # 일자
        c_date = next((c for c in df.columns if '작성일자' in str(c) or '일자' in str(c)), df.columns[0])

        # 만약 위 방법으로 못찾으면 엑셀 순서(번호)로 강제 지정 (비상용)
        if not c_supply: c_supply = df.columns[15] # 홈택스 표준 16번째 칸
        if not c_tax: c_tax = df.columns[16]    # 홈택스 표준 17번째 칸

        # 숫자 변환
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 4. 분류 작업 (질문창 로직)
        st.subheader("🔍 공동 비용 확인창 (해당사항 없으면 그냥 지나가세요)")
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower()
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            supply_val = float(row[c_supply])
            tax_val = float(row[c_tax])

            # [1] 비즈텍스 5:5
            if any(k in name_val for k in ['비즈', '택스', 'tax']):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = supply_val/2, tax_val/2
                r_i[c_supply], r_i[c_tax] = supply_val/2, tax_val/2
                ansan_list.append(r_a)
                incheon_list.append(r_i)
            
            # [2] KT 요금 질문 (무조건 상단에 표시됨)
            elif any(k in name_val for k in ['kt', '케이티', '전화']):
                ansan_v = st.number_input(f"📞 {row[c_name]} ({supply_val:,.0f}원) 중 안산분?", 0.0, float(supply_val), float(supply_val/2), key=f"kt_{idx}")
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = ansan_v, ansan_v * 0.1
                r_i[c_supply], r_i[c_tax] = supply_val - ansan_v, (supply_val - ansan_v) * 0.1
                ansan_list.append(r_a)
                incheon_list.append(r_i)

            # [3] 안산 본점 판별
            elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 5. 소계 및 합계 계산 함수
        def make_summary(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by='월')
            final_rows = []
            for month, group in temp.groupby('월'):
                final_rows.append(group)
                s_sum, t_sum = group[c_supply].sum(), group[c_tax].sum()
                final_rows.append(pd.DataFrame([{c_name: f"--- {int(month)}월 소계 ---", c_supply: s_sum, c_tax: t_sum}]))
            
            # 총 합계
            final_rows.append(pd.DataFrame([{c_name: "=== 전체 총 합계 ===", c_supply: temp[c_supply].sum(), c_tax: temp[c_tax].sum()}]))
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = make_summary(ansan_list)
        incheon_final = make_summary(incheon_list)

        # 6. 출력
        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("🏢 안산 본점")
            st.dataframe(ansan_final)
            if not ansan_final.empty:
                st.download_button("📥 안산 엑셀", ansan_final.to_csv(index=False).encode('utf-8-sig'), "ansan.csv")
        with c2:
            st.subheader("🏭 인천 지점")
            st.dataframe(incheon_final)
            if not incheon_final.empty:
                st.download_button("📥 인천 엑셀", incheon_final.to_csv(index=False).encode('utf-8-sig'), "incheon.csv")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
