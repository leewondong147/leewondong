import streamlit as st
import pandas as pd
import io

st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 6.5)")

job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

if uploaded_file is not None:
    try:
        # 1. 파일 읽기
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None)

        # 2. 진짜 제목 줄 찾기 (공급가액, 세액 글자가 둘 다 있는 줄을 찾음)
        header_row = 0
        for i in range(len(df_raw)):
            row_str = "".join([str(v) for v in df_raw.iloc[i].values])
            if ('공급' in row_str or '금액' in row_str) and '세액' in row_str:
                header_row = i
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 3. 🔍 기둥 이름 정밀 수색 (상호명, 공급가액, 세액)
        # 상호명 기둥 찾기 (공급자 혹은 상호 혹은 성명)
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '공급자', '성명', '거래처'])), None)
        # 공급가액 기둥 찾기 ('총'자가 안 들어간 공급가액 최우선)
        c_supply = next((c for c in df.columns if '공급가액' in str(c) and '총' not in str(c)), None)
        if not c_supply: c_supply = next((c for c in df.columns if '금액' in str(c) or '공급' in str(c)), None)
        # 세액 기둥 찾기
        c_tax = next((c for c in df.columns if '세액' in str(c) and '총' not in str(c)), None)
        if not c_tax: c_tax = next((c for c in df.columns if '세' in str(c)), None)
        # 일자 기둥 찾기
        c_date = next((c for c in df.columns if any(k in str(c) for k in ['일자', '날짜', '작성'])), df.columns[0])

        # 데이터 숫자 변환
        df[c_supply] = pd.to_numeric(df[c_supply].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df[c_tax] = pd.to_numeric(df[c_tax].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df['월'] = pd.to_datetime(df[c_date], errors='coerce').dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 4. 분류 작업 (공동 비용 검사를 가장 먼저!)
        for idx, row in df.iterrows():
            name_val = str(row[c_name]).replace(" ", "").lower() if c_name else ""
            full_text = "".join(row.astype(str)).replace(" ", "").lower()
            supply_val = float(row[c_supply])
            tax_val = float(row[c_tax])

            # [핵심] 공동 비용 질문 로직
            # 1. 비즈텍스/택스/세무사 등
            if any(k in name_val for k in ['비즈', '택스', 'tax', '세무']):
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = supply_val/2, tax_val/2
                r_i[c_supply], r_i[c_tax] = supply_val/2, tax_val/2
                ansan_list.append(r_a)
                incheon_list.append(r_i)
            
            # 2. KT/케이티/전화/통신
            elif any(k in name_val for k in ['kt', '케이티', '전화', '통신']):
                st.warning(f"📞 공동요금 확인: {row[c_name]} ({supply_val:,.0f}원)")
                # 화면에 입력창 띄우기
                ansan_v = st.number_input(f"ㄴ {row[c_name]} 중 '안산' 공급가액은?", 0.0, float(supply_val), float(supply_val/2), key=f"kt_input_{idx}")
                
                r_a, r_i = row.copy(), row.copy()
                r_a[c_supply], r_a[c_tax] = ansan_v, ansan_v * 0.1
                r_i[c_supply], r_i[c_tax] = supply_val - ansan_v, (supply_val - ansan_v) * 0.1
                ansan_list.append(r_a)
                incheon_list.append(r_i)

            # [일반 분류] 안산 본점
            elif ('6114' in full_text) or ('hojin' in full_text and 'hojinbio' not in full_text) or ('성남경찰서' in full_text):
                ansan_list.append(row)
            # [일반 분류] 나머지 인천
            else:
                incheon_list.append(row)

        # 5. 소계 및 합계 삽입 로직
        def finalize_df(data_list):
            if not data_list: return pd.DataFrame()
            temp_df = pd.DataFrame(data_list).sort_values(by='월')
            
            result_rows = []
            for month, group in temp_df.groupby('월'):
                result_rows.append(group) # 월 데이터 추가
                # 소계 행 추가
                sub_s = group[c_supply].sum()
                sub_t = group[c_tax].sum()
                sub_row = pd.DataFrame([{c_name: f"--- {int(month)}월 소계 ---", c_supply: sub_s, c_tax: sub_t}])
                result_rows.append(sub_row)
            
            # 총 합계 추가
            total_s = temp_df[c_supply].sum()
            total_t = temp_df[c_tax].sum()
            grand_row = pd.DataFrame([{c_name: "=== 전체 총 합계 ===", c_supply: total_s, c_tax: total_t}])
            result_rows.append(grand_row)
            
            return pd.concat(result_rows, ignore_index=True)

        ansan_final = finalize_df(ansan_list)
        incheon_final = finalize_df(incheon_list)

        # 6. 화면 출력 및 다운로드
        st.divider()
        col1, col2 = st.columns(2)
        with col1:
            st.subheader(f"🏢 안산 (본점)")
            st.dataframe(ansan_final)
            if not ansan_final.empty:
                st.download_button("📥 안산 엑셀", ansan_final.to_csv(index=False).encode('utf-8-sig'), "ansan_final.csv")
        with col2:
            st.subheader(f"🏭 인천 (지점)")
            st.dataframe(incheon_final)
            if not incheon_final.empty:
                st.download_button("📥 인천 엑셀", incheon_final.to_csv(index=False).encode('utf-8-sig'), "incheon_final.csv")

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
