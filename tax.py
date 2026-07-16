import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.1 완성형)")
st.caption("표 밀림을 방지하는 클린 배열과, 놓치는 데이터가 없는 전체 텍스트 스캔 엔진을 결합했습니다.")

# ==========================================
# ⚙️ 2. [사이드바] 설정 제어판
# ==========================================
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
st.sidebar.subheader("⚖️ 일반 거래처 분배 비율")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", min_value=0, max_value=100, value=50, step=1)

st.sidebar.divider()
st.sidebar.subheader("📞 KT 요금 전용 '사용량' 설정")
kt_ansan_usage = st.sidebar.number_input("KT 안산 사용량 (숫자)", value=50, step=1)
kt_incheon_usage = st.sidebar.number_input("KT 인천 사용량 (숫자)", value=50, step=1)

# KT 퍼센트 자동 계산
kt_total = kt_ansan_usage + kt_incheon_usage
kt_ansan_percent = (kt_ansan_usage / kt_total) if kt_total > 0 else 0.5
st.sidebar.caption(f"👉 적용되는 KT 분배 비율: 안산 {kt_ansan_percent*100:.1f}%")

kt_threshold = st.sidebar.number_input("KT 소액 기준", value=55000, step=1000)

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ 3. [핵심] 지능형 좌표 추적 엔진
# ==========================================
def clean_value_secure(val):
    try: return float(str(val).replace(",", "").replace("원", "").replace('"', '').strip())
    except: return 0.0

if uploaded_file is not None:
    try:
        df_raw = pd.read_excel(uploaded_file, header=None, dtype=str) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None, dtype=str)

        # 1. 진짜 제목줄 찾기
        header_row_idx = -1
        for i in range(min(len(df_raw), 25)):
            row_list = df_raw.iloc[i].fillna('').astype(str).tolist()
            if '작성일자' in row_list and '공급가액' in row_list:
                header_row_idx = i
                break
        
        if header_row_idx == -1:
            st.error("🚨 엑셀 파일에서 '작성일자'와 '공급가액' 제목을 찾을 수 없습니다.")
            st.stop()

        # 2. 열 번호(좌표) 추출
        header_list = df_raw.iloc[header_row_idx].fillna('').astype(str).tolist()
        header_list = [re.sub(r'\s+', '', col) for col in header_list]

        idx_date = header_list.index('작성일자')
        idx_sup = header_list.index('공급가액')
        idx_tax = header_list.index('세액')

        name_indices = [i for i, col in enumerate(header_list) if '상호' in col]
        
        if job_type == "💰 매출":
            idx_name = name_indices[1] if len(name_indices) > 1 else name_indices[0]
        else:
            idx_name = name_indices[0] if len(name_indices) > 0 else -1

        df_data = df_raw.iloc[header_row_idx+1:].copy()
        ansan_data, incheon_data = [], []

        # ==========================================
        # 4. 데이터 스플릿 및 5칸 테이블 조립
        # ==========================================
        for _, row in df_data.iterrows():
            date_str = str(row[idx_date]).strip()
            
            if not date_str or date_str == 'nan' or '조회' in date_str or '합계' in date_str or len(date_str) < 5:
                continue
                
            name_str = str(row[idx_name]).replace(" ", "").lower()
            if name_str == 'nan': continue

            # 🚨 [핵심 수정 포인트] 안산 분류를 위해 해당 줄의 '모든 텍스트'를 다 합쳐서 검사합니다.
            full_text = "".join(row.fillna('').astype(str)).replace(" ", "").lower()

            sup_val = clean_value_secure(row[idx_sup])
            tax_val = clean_value_secure(row[idx_tax])

            is_split = False
            current_ratio = ansan_ratio / 100.0

            # 50:50 분배 로직 (이름 기준)
            if '진솔법무사' in name_str or '비즈택스' in name_str:
                is_split = True
            elif '혜성환경' in name_str and '0511' in date_str.replace("-","").replace(".","")[-4:]:
                is_split = True
            elif '케이티' in name_str or 'kt' in name_str:
                if sup_val < kt_threshold:
                    is_split = True
                    current_ratio = kt_ansan_percent 

            if is_split:
                a_sup = np.floor(sup_val * current_ratio)
                a_tax = np.floor(tax_val * current_ratio)
                i_sup = sup_val - a_sup
                i_tax = tax_val - a_tax
                
                ansan_data.append([date_str, row[idx_name], a_sup, a_tax, a_sup + a_tax])
                incheon_data.append([date_str, row[idx_name], i_sup, i_tax, i_sup + i_tax])
            else:
                # 🚨 [핵심 수정 포인트] 이메일이나 비고 칸에 숨은 단어도 full_text로 잡아냅니다.
                if '남상민' in full_text or any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                    ansan_data.append([date_str, row[idx_name], sup_val, tax_val, sup_val + tax_val])
                else:
                    incheon_data.append([date_str, row[idx_name], sup_val, tax_val, sup_val + tax_val])

        # ==========================================
        # 5. 화면 출력 및 다운로드
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
            st.subheader("🏢 안산 본점")
            st.dataframe(a_df, use_container_width=True)
        with c2: 
            st.subheader("🏭 인천 지점")
            st.dataframe(i_df, use_container_width=True)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
