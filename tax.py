import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.7 스마트 에러 방어판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.7 완결판)")
st.caption("비율 슬라이더, KT 수치 입력, 매출처(호진환경) 제외 로직이 모두 적용되었습니다.")

# ==========================================
# ⚙️ [사이드바] 커스텀 설정 제어판
# ==========================================
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
st.sidebar.subheader("⚖️ 거래처 분배 비율 설정")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", min_value=0, max_value=100, value=50, step=1)
incheon_ratio = 100 - ansan_ratio
st.sidebar.caption(f"👉 현재 설정: 안산 **{ansan_ratio}%** / 인천 **{incheon_ratio}%**")

st.sidebar.divider()
st.sidebar.subheader("📞 주식회사 KT 요금 설정")
kt_threshold = st.sidebar.number_input("소액 기준 (이 금액 미만일 때 적용)", value=55000, step=1000)
kt_new_supply = st.sidebar.number_input("👉 소액일 경우 변경할 공급가액 (0원이면 원본 유지)", value=0, step=1000)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ [정밀 전처리 도구]
# ==========================================
def clean_value_secure(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try: return float(val_str)
    except: return 0.0

if uploaded_file is not None:
    try:
        # 1. 파일 전체를 문자열로 안전하게 읽기 (에러 원천 차단)
        df_raw = pd.read_excel(uploaded_file, header=None, dtype=str) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None, dtype=str)

        # 2. 스마트 헤더(제목줄) 탐색: '공급가액'이라는 글자가 있는 줄을 찾습니다.
        header_row = 0
        for i in range(min(len(df_raw), 25)):
            row_str = "".join(df_raw.iloc[i].fillna('').values).replace(" ", "")
            if '공급가액' in row_str and ('세액' in row_str or '상호' in row_str):
                header_row = i
                break
        
        # 실제 데이터프레임 구성
        df = df_raw.iloc[header_row+1:].reset_index(drop=True)
        raw_cols = df_raw.iloc[header_row].fillna('').astype(str).tolist()
        
        # 3. 컬럼명 정제 및 중복 방지 (매출 엑셀의 '상호' 중복 문제 해결)
        cleaned_cols = [re.sub(r'[^가-힣a-zA-Z0-9]', '', c) for c in raw_cols]
        final_cols = []
        for c in cleaned_cols:
            if c in final_cols:
                final_cols.append(c + "_2") # 두 번째 나오는 상호는 '상호_2'로 자동 변경
            else:
                final_cols.append(c)
        df.columns = final_cols

        # 4. 각 데이터 기둥(컬럼) 매핑
        c_date = next((c for c in df.columns if '일자' in c), df.columns[1])
        
        # 🚨 [핵심 수정] 매출일 경우 호진환경이 아닌 진짜 거래처 상호 매핑
        if job_type == "💰 매출":
            # 1순위: 공급받는자, 2순위: 두번째 상호(상호_2), 3순위: 그냥 상호
            c_name = next((c for c in df.columns if '공급받는자' in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호2' in c or '상호_2' in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c), df.columns[3])
        else:
            # 매입일 경우 첫번째 상호 사용
            c_name = next((c for c in df.columns if '공급자' in c and '받는' not in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c), df.columns[3])

        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in c), df.columns[-1])

        # 5. 금액 파싱
        df[c_supply] = df[c_supply].apply(clean_value_secure)
        df[c_tax] = df[c_tax].apply(clean_value_secure)

        ansan_list, incheon_list = [], []

        # ==========================================
        # 🚨 6. 분배 및 KT 강제 입력 로직
        # ==========================================
        for idx, row in df.iterrows():
            name_str = str(row[c_name]).replace(" ", "").lower()
            date_str = str(row[c_date]).replace("-", "").replace(".", "")
            
            is_split_target = False
            
            # [조건 1] 진솔법무사 & 비즈택스
            if '진솔법무사' in name_str or '비즈택스' in name_str:
                is_split_target = True
                
            # [조건 2] 혜성환경 (5월 11일 한정)
            elif '혜성환경' in name_str and '0511' in date_str[-4:]:
                is_split_target = True
                
            # [조건 3] 🚨 KT 소액 로직 (강제 금액 입력)
            elif '케이티' in name_str or 'kt' in name_str:
                if row[c_supply] < kt_threshold:
                    if kt_new_supply > 0:
                        # 화면에서 입력한 숫자로 강제 덮어쓰기
                        row[c_supply] = float(kt_new_supply)
                        row[c_tax] = float(kt_new_supply) * 0.1
                    is_split_target = True

            row['합계'] = row[c_supply] + row[c_tax]

            # 스플릿(분할) 실행
            if is_split_target:
                row_ansan = row.copy()
                row_incheon = row.copy()
                
                # 설정된 슬라이더 비율 적용 (안산_ratio)
                ratio = ansan_ratio / 100.0
                ansan_supply_val = np.floor(row[c_supply] * ratio)
                ansan_tax_val = np.floor(row[c_tax] * ratio)
                
                row_ansan[c_supply] = ansan_supply_val
                row_ansan[c_tax] = ansan_tax_val
                row_ansan['합계'] = ansan_supply_val + ansan_tax_val
                
                row_incheon[c_supply] = row[c_supply] - ansan_supply_val
                row_incheon[c_tax] = row[c_tax] - ansan_tax_val
                row_incheon['합계'] = row_incheon[c_supply] + row_incheon[c_tax]
                
                if ansan_ratio > 0: ansan_list.append(row_ansan)
                if incheon_ratio > 0: incheon_list.append(row_incheon)
                continue
                
            # 일반 분류 실행
            if '남상민' in name_str or any(k in name_str for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 7. 화면 표출 준비
        display_cols = [c_date, c_name, c_supply, c_tax, '합계']
        a_df = pd.DataFrame(ansan_list)[display_cols] if ansan_list else pd.DataFrame(columns=display_cols)
        i_df = pd.DataFrame(incheon_list)[display_cols] if incheon_list else pd.DataFrame(columns=display_cols)
        
        a_df.columns = ['작성일자', '상호', '공급가액', '세액', '합계']
        i_df.columns = ['작성일자', '상호', '공급가액', '세액', '합계']

        # 8. 다운로드 및 결과 출력
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            a_df.to_excel(writer, sheet_name='안산_본점', index=False)
            i_df.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_정산완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점"); st.dataframe(a_df)
        with c2: 
            st.subheader("🏭 인천 지점"); st.dataframe(i_df)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 데이터를 분석하는 중 문제가 발생했습니다.")
