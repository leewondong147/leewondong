import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.8 클린 정렬판)")
st.caption("표 밀림 현상과 데이터 누락을 해결하기 위해, 데이터를 깔끔한 5칸 테이블로 우선 정렬합니다.")

# ==========================================
# ⚙️ [사이드바] 제어판
# ==========================================
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
st.sidebar.subheader("⚖️ 거래처 분배 비율 설정")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", min_value=0, max_value=100, value=50, step=1)
incheon_ratio = 100 - ansan_ratio
st.sidebar.caption(f"👉 설정: 안산 **{ansan_ratio}%** / 인천 **{incheon_ratio}%**")

st.sidebar.divider()
st.sidebar.subheader("📞 주식회사 KT 요금 설정")
kt_threshold = st.sidebar.number_input("소액 기준 (이 금액 미만일 때)", value=55000, step=1000)
kt_new_supply = st.sidebar.number_input("👉 강제 변경할 공급가액 (0: 원본)", value=0, step=1000)

st.sidebar.divider()
st.sidebar.subheader("🛠️ 긴급 보정 (안산이 비어있을 때만)")
manual_name_idx = st.sidebar.number_input("상호 열 번호 수동 지정 (자동:-1, A열:0, B열:1...)", value=-1, step=1)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

def clean_value_secure(val):
    if pd.isna(val): return 0.0
    val_str = str(val).strip().replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try: return float(val_str)
    except: return 0.0

if uploaded_file is not None:
    try:
        # 1. 파일 안전하게 읽기
        df_raw = pd.read_excel(uploaded_file, header=None, dtype=str) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None, dtype=str)

        # 2. 데이터 시작 지점(헤더) 탐색
        header_row = 0
        for i in range(min(len(df_raw), 25)):
            row_str = "".join(df_raw.iloc[i].fillna('').values).replace(" ", "")
            if '공급가액' in row_str and ('세액' in row_str or '상호' in row_str):
                header_row = i
                break
        
        df = df_raw.iloc[header_row+1:].reset_index(drop=True)
        raw_cols = df_raw.iloc[header_row].fillna('').astype(str).tolist()
        
        # 중복 이름 방지 (Reindexing 오류 해결)
        cleaned_cols = [re.sub(r'[^가-힣a-zA-Z0-9]', '', c) for c in raw_cols]
        final_cols, col_counts = [], {}
        for c in cleaned_cols:
            if c == "": c = "빈칸"
            if c in col_counts:
                col_counts[c] += 1
                final_cols.append(f"{c}_{col_counts[c]}")
            else:
                col_counts[c] = 1
                final_cols.append(c)
        df.columns = final_cols

        # 3. 데이터 기둥 자동 탐색
        c_date = next((c for c in df.columns if '일자' in c), df.columns[1])
        c_supply = next((c for c in df.columns if '공급가액' in c), df.columns[-2])
        c_tax = next((c for c in df.columns if '세액' in c), df.columns[-1])

        # 상호명 탐색 (수동 지정 값이 -1이 아니면 그 번호 사용)
        if manual_name_idx != -1:
            c_name = df.columns[manual_name_idx]
        else:
            if job_type == "💰 매출":
                c_name = next((c for c in df.columns if '공급받는자' in c), None)
                if not c_name: c_name = next((c for c in df.columns if '상호_2' in c or '상호2' in c), None)
                if not c_name: c_name = next((c for c in df.columns if '상호' in c), df.columns[3])
            else:
                c_name = next((c for c in df.columns if '공급자' in c and '받는' not in c), None)
                if not c_name: c_name = next((c for c in df.columns if '상호' in c), df.columns[3])

        # ==========================================
        # 🚨 [핵심 해결] 4. 클린 테이블 변환 (칸 밀림 완벽 차단)
        # ==========================================
        clean_df = pd.DataFrame()
        clean_df['작성일자'] = df[c_date]
        clean_df['상호'] = df[c_name]
        clean_df['공급가액'] = df[c_supply].apply(clean_value_secure)
        clean_df['세액'] = df[c_tax].apply(clean_value_secure)
        clean_df['합계'] = clean_df['공급가액'] + clean_df['세액']

        ansan_list, incheon_list = [], []

        # 5. 분류 및 분배 로직 (깨끗한 5칸 표에서 진행)
        for idx, row in clean_df.iterrows():
            name_str = str(row['상호']).replace(" ", "").lower()
            date_str = str(row['작성일자']).replace("-", "").replace(".", "")
            sup_val = row['공급가액']
            tax_val = row['세액']
            
            is_split_target = False
            
            if '진솔법무사' in name_str or '비즈택스' in name_str:
                is_split_target = True
            elif '혜성환경' in name_str and '0511' in date_str[-4:]:
                is_split_target = True
            elif '케이티' in name_str or 'kt' in name_str:
                if sup_val < kt_threshold:
                    if kt_new_supply > 0:
                        sup_val = float(kt_new_supply)
                        tax_val = float(kt_new_supply) * 0.1
                    is_split_target = True

            if is_split_target:
                ratio = ansan_ratio / 100.0
                a_sup = np.floor(sup_val * ratio)
                a_tax = np.floor(tax_val * ratio)
                
                # 안산 데이터 추가
                ansan_list.append({'작성일자': row['작성일자'], '상호': row['상호'], '공급가액': a_sup, '세액': a_tax, '합계': a_sup + a_tax})
                
                # 인천 데이터 추가
                i_sup = sup_val - a_sup
                i_tax = tax_val - a_tax
                incheon_list.append({'작성일자': row['작성일자'], '상호': row['상호'], '공급가액': i_sup, '세액': i_tax, '합계': i_sup + i_tax})
                continue
                
            # 일반 분류
            if '남상민' in name_str or any(k in name_str for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                ansan_list.append({'작성일자': row['작성일자'], '상호': row['상호'], '공급가액': sup_val, '세액': tax_val, '합계': sup_val + tax_val})
            else:
                incheon_list.append({'작성일자': row['작성일자'], '상호': row['상호'], '공급가액': sup_val, '세액': tax_val, '합계': sup_val + tax_val})

        # 6. 화면 표출 (무조건 5칸으로 고정)
        a_df = pd.DataFrame(ansan_list) if ansan_list else pd.DataFrame(columns=['작성일자', '상호', '공급가액', '세액', '합계'])
        i_df = pd.DataFrame(incheon_list) if incheon_list else pd.DataFrame(columns=['작성일자', '상호', '공급가액', '세액', '합계'])

        # 7. 다운로드 처리
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
        st.error(f"🚨 오류 발생: {e}")
