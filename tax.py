import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (9.7 KT 사용량 + 정렬판)")
st.caption("표 밀림 현상을 완벽히 차단하고, KT 사용량 기반 분배 엔진을 적용했습니다.")

# ==========================================
# ⚙️ 2. [사이드바] 설정 제어판
# ==========================================
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
st.sidebar.subheader("⚖️ 일반 거래처 분배 비율")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", min_value=0, max_value=100, value=50, step=1)
incheon_ratio = 100 - ansan_ratio

st.sidebar.divider()
st.sidebar.subheader("📞 KT 요금 전용 '사용량' 설정")
kt_ansan_usage = st.sidebar.number_input("KT 안산 사용량 (숫자)", value=50, step=1)
kt_incheon_usage = st.sidebar.number_input("KT 인천 사용량 (숫자)", value=50, step=1)

# 자동 퍼센트 계산
kt_total = kt_ansan_usage + kt_incheon_usage
kt_ansan_percent = (kt_ansan_usage / kt_total) if kt_total > 0 else 0.5
st.sidebar.caption(f"👉 적용되는 KT 분배 비율: 안산 {kt_ansan_percent*100:.1f}%")

kt_threshold = st.sidebar.number_input("KT 소액 기준 (이 금액 미만일 때)", value=55000, step=1000)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ 3. [전처리] 안전한 데이터 추출기
# ==========================================
def clean_value_secure(val):
    try: return float(str(val).replace(",", "").replace("원", "").replace('"', '').strip())
    except: return 0.0

if uploaded_file is not None:
    try:
        # 파일 읽기 및 헤더 찾기
        df_raw = pd.read_excel(uploaded_file, header=None, dtype=str) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None, dtype=str)

        header_row = 0
        for i in range(min(len(df_raw), 25)):
            row_str = "".join(df_raw.iloc[i].fillna('').astype(str)).replace(" ", "")
            if '공급가액' in row_str:
                header_row = i
                break
        
        df = df_raw.iloc[header_row+1:].reset_index(drop=True)
        raw_cols = df_raw.iloc[header_row].fillna('').astype(str).tolist()
        
        # 중복 열 이름 방지
        final_cols, seen = [], {}
        for c in raw_cols:
            clean_c = re.sub(r'[^가-힣a-zA-Z0-9]', '', c)
            if not clean_c: clean_c = "빈칸"
            if clean_c in seen:
                seen[clean_c] += 1
                final_cols.append(f"{clean_c}_{seen[clean_c]}")
            else:
                seen[clean_c] = 1
                final_cols.append(clean_c)
        df.columns = final_cols

        # 데이터 기둥 매핑 (유연하게 찾기)
        c_date = next((c for c in df.columns if '일자' in c), df.columns[1] if len(df.columns) > 1 else df.columns[0])
        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2] if len(df.columns) > 2 else df.columns[0])
        c_tax = next((c for c in df.columns if '세액' in c), df.columns[-1] if len(df.columns) > 1 else df.columns[0])

        # 🚨 [중요] 안산 누락 방지를 위한 상호명 정밀 탐색
        if job_type == "💰 매출":
            c_name = next((c for c in df.columns if '공급받는자' in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c and '상호_2' in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c or '거래처' in c), df.columns[3] if len(df.columns) > 3 else df.columns[0])
        else:
            c_name = next((c for c in df.columns if '가맹점' in c or '거래처' in c or ('공급자' in c and '받는' not in c)), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c), df.columns[3] if len(df.columns) > 3 else df.columns[0])

        # ==========================================
        # 🚨 4. [핵심 해결] 칸 밀림을 100% 방지하는 데이터 분류
        # ==========================================
        ansan_data = []
        incheon_data = []

        for idx, row in df.iterrows():
            name_str = str(row[c_name]).replace(" ", "").lower()
            date_str = str(row[c_date]).replace("-", "").replace(".", "")
            
            sup_val = clean_value_secure(row[c_supply])
            tax_val = clean_value_secure(row[c_tax])
            
            is_split = False
            current_ratio = ansan_ratio / 100.0 # 기본은 슬라이더 비율
            
            # 분배 로직
            if '진솔법무사' in name_str or '비즈택스' in name_str:
                is_split = True
            elif '혜성환경' in name_str and '0511' in date_str[-4:]:
                is_split = True
            elif '케이티' in name_str or 'kt' in name_str:
                if sup_val < kt_threshold:
                    is_split = True
                    current_ratio = kt_ansan_percent # KT는 사용량 비율 적용!

            # [밀림 방지] 딕셔너리가 아닌 리스트 형태로 5칸을 강제 고정하여 넣음
            if is_split:
                a_sup = np.floor(sup_val * current_ratio)
                a_tax = np.floor(tax_val * current_ratio)
                i_sup = sup_val - a_sup
                i_tax = tax_val - a_tax
                
                ansan_data.append([row[c_date], row[c_name], a_sup, a_tax, a_sup + a_tax])
                incheon_data.append([row[c_date], row[c_name], i_sup, i_tax, i_sup + i_tax])
            else:
                if '남상민' in name_str or any(k in name_str for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                    ansan_data.append([row[c_date], row[c_name], sup_val, tax_val, sup_val + tax_val])
                else:
                    incheon_data.append([row[c_date], row[c_name], sup_val, tax_val, sup_val + tax_val])

        # ==========================================
        # 5. 화면 표출 및 다운로드 (고정된 5칸 테이블 생성)
        # ==========================================
        final_columns = ['작성일자', '상호', '공급가액', '세액', '합계']
        
        a_df = pd.DataFrame(ansan_data, columns=final_columns)
        i_df = pd.DataFrame(incheon_data, columns=final_columns)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            a_df.to_excel(writer, sheet_name='안산_본점', index=False)
            i_df.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_정산완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점"); st.dataframe(a_df, use_container_width=True)
        with c2: 
            st.subheader("🏭 인천 지점"); st.dataframe(i_df, use_container_width=True)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
