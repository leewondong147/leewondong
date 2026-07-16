import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.4 양식 방어판)")
st.caption("국세청 엑셀의 사소한 양식 변경에도 흔들리지 않는 초강력 스마트 탐색 엔진이 탑재되었습니다.")

# ==========================================
# ⚙️ 2. [사이드바] 설정 제어판
# ==========================================
st.sidebar.header("⚙️ 상세 조건 설정")
job_type = st.sidebar.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

st.sidebar.divider()
st.sidebar.subheader("⚖️ 거래처 분배 비율")
ansan_ratio = st.sidebar.slider("안산 본점 할당 비율 (%)", min_value=0, max_value=100, value=50, step=1)
incheon_ratio = 100 - ansan_ratio

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ 3. [전처리] 안전한 데이터 추출 및 날짜 처리
# ==========================================
def clean_value_secure(val):
    try: return float(str(val).replace(",", "").replace("원", "").replace('"', '').strip())
    except: return 0.0

def parse_flexible_date(series):
    cleaned = series.astype(str).str.replace('"', '').str.strip()
    cleaned = cleaned.str.replace('년', '-').str.replace('월', '-').str.replace('일', '')
    return pd.to_datetime(cleaned, errors='coerce')

if uploaded_file is not None:
    try:
        # 1. 파일 안전하게 읽기
        df_raw = pd.read_excel(uploaded_file, header=None, dtype=str) if not uploaded_file.name.endswith('.csv') else pd.read_csv(uploaded_file, header=None, dtype=str)

        # 🚨 [강력 업데이트] 2. 초강력 진짜 제목줄(헤더) 찾기
        header_row_idx = -1
        
        # 탐색 범위를 50줄로 늘리고, 공백/특수문자를 완전히 무시하고 검색합니다.
        for i in range(min(len(df_raw), 50)):
            # 해당 줄의 모든 데이터를 하나의 문자열로 합칩니다.
            raw_row_str = "".join(df_raw.iloc[i].fillna('').astype(str))
            
            # 정규식(Regex)을 사용하여 한글, 영어, 숫자만 남기고 띄어쓰기 등 모든 것을 지웁니다.
            clean_row_str = re.sub(r'[^가-힣a-zA-Z0-9]', '', raw_row_str)
            
            # 뼈대만 남은 문자열에 핵심 단어가 있는지 확인합니다.
            if '작성일자' in clean_row_str and '공급가액' in clean_row_str:
                header_row_idx = i
                break
        
        if header_row_idx == -1:
            st.error("🚨 엑셀 파일에서 '작성일자'와 '공급가액' 항목을 찾을 수 없습니다. 국세청 양식이 완전히 바뀐 것 같습니다.")
            st.stop()

        # 3. 열 번호(좌표) 추출 로직 강화
        header_list = df_raw.iloc[header_row_idx].fillna('').astype(str).tolist()
        # 헤더 이름 자체에서도 공백과 줄바꿈을 완벽히 제거합니다.
        header_list = [re.sub(r'\s+', '', col) for col in header_list]

        # 단어가 정확히 일치하지 않아도 포함되어 있으면 찾아내도록 강화
        idx_date = next((i for i, col in enumerate(header_list) if '작성일자' in col), -1)
        idx_sup = next((i for i, col in enumerate(header_list) if '공급가액' in col or '금액' in col), -1)
        idx_tax = next((i for i, col in enumerate(header_list) if '세액' in col), -1)

        name_indices = [i for i, col in enumerate(header_list) if '상호' in col or '거래처' in col]
        
        if job_type == "💰 매출":
            idx_name = name_indices[1] if len(name_indices) > 1 else (name_indices[0] if name_indices else -1)
        else:
            idx_name = name_indices[0] if len(name_indices) > 0 else -1
            
        # 필수 열 번호를 제대로 찾았는지 안전 검사
        if -1 in [idx_date, idx_sup, idx_name]:
             st.error("🚨 제목줄은 찾았으나, 날짜/공급가액/상호 기둥을 정확히 분류하지 못했습니다.")
             st.stop()

        df_data = df_raw.iloc[header_row_idx+1:].copy()
        
        # 데이터를 돌면서 KT 내역과 일반 내역을 분리합니다.
        kt_list = []
        other_list = []

        for _, row in df_data.iterrows():
            date_str = str(row[idx_date]).strip()
            if not date_str or date_str == 'nan' or '조회' in date_str or '합계' in date_str or len(date_str) < 5:
                continue
                
            name_str = str(row[idx_name]).replace(" ", "").lower()
            if name_str == 'nan': continue
            
            sup_val = clean_value_secure(row[idx_sup])
            tax_val = clean_value_secure(row[idx_tax])
            full_text = "".join(row.fillna('').astype(str)).replace(" ", "").lower()

            item = {
                '작성일자': date_str,
                '상호': str(row[idx_name]),
                '공급가액': sup_val,
                '세액': tax_val,
                '전체텍스트': full_text 
            }

            if '케이티' in name_str or 'kt' in name_str:
                kt_list.append(item)
            else:
                other_list.append(item)

        # ==========================================
        # 4. 📝 [핵심] KT 요금 직접 수정 에디터 화면
        # ==========================================
        kt_df = pd.DataFrame(kt_list)
        
        if not kt_df.empty:
            st.subheader("📝 주식회사 KT 요금 직접 수정")
            st.caption("표 안의 **'공급가액'** 숫자를 클릭해서 원하는 금액(안산 할당분)으로 직접 수정하세요.")
            
            edited_kt_df = st.data_editor(
                kt_df[['작성일자', '상호', '공급가액']], 
                disabled=["작성일자", "상호"],
                use_container_width=True
            )
        else:
            edited_kt_df = pd.DataFrame()

        st.divider()

        # ==========================================
        # 5. 정산 실행 버튼 및 최종 로직
        # ==========================================
        if st.button("🚀 위 설정대로 최종 정산 실행", type="primary", use_container_width=True):
            
            ansan_data, incheon_data = [], []
            ratio = ansan_ratio / 100.0

            if not edited_kt_df.empty:
                for idx, row in edited_kt_df.iterrows():
                    date_str = row['작성일자']
                    name_str = row['상호']
                    
                    a_sup = float(row['공급가액']) 
                    a_tax = np.floor(a_sup * 0.1) 
                    
                    original_sup = kt_df.iloc[idx]['공급가액']
                    original_tax = kt_df.iloc[idx]['세액']
                    
                    i_sup = original_sup - a_sup
                    i_tax = original_tax - a_tax
                    
                    ansan_data.append([date_str, name_str, a_sup, a_tax, a_sup + a_tax])
                    incheon_data.append([date_str, name_str, i_sup, i_tax, i_sup + i_tax])

            for row in other_list:
                date_str = row['작성일자']
                name_str = row['상호']
                name_clean = name_str.replace(" ", "").lower()
                sup_val = row['공급가액']
                tax_val = row['세액']
                full_text = row['전체텍스트']

                is_split = False
                if '진솔법무사' in name_clean or '비즈택스' in name_clean:
                    is_split = True
                elif '혜성환경' in name_clean and '0511' in date_str.replace("-","").replace(".","")[-4:]:
                    is_split = True

                if is_split:
                    a_sup = np.floor(sup_val * ratio)
                    a_tax = np.floor(tax_val * ratio)
                    i_sup = sup_val - a_sup
                    i_tax = tax_val - a_tax
                    ansan_data.append([date_str, name_str, a_sup, a_tax, a_sup + a_tax])
                    incheon_data.append([date_str, name_str, i_sup, i_tax, i_sup + i_tax])
                else:
                    if '남상민' in full_text or any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                        ansan_data.append([date_str, name_str, sup_val, tax_val, sup_val + tax_val])
                    else:
                        incheon_data.append([date_str, name_str, sup_val, tax_val, sup_val + tax_val])

            final_columns = ['작성일자', '상호', '공급가액', '세액', '합계']
            
            def format_with_subtotals(data_list):
                if not data_list: return pd.DataFrame(columns=final_columns)
                temp_df = pd.DataFrame(data_list, columns=final_columns)
                temp_dates = parse_flexible_date(temp_df['작성일자'])
                temp_df['월'] = temp_dates.dt.month.fillna(0).astype(int)
                temp_df = temp_df.sort_values(by=['월', '작성일자'])
                final_rows = []
                for month, group in temp_df.groupby('월'):
                    group_clean = group.drop(columns=['월'])
                    final_rows.append(group_clean)
                    month_label = f"{int(month)}월 소계" if month > 0 else "기타 소계"
                    subtotal = pd.DataFrame([{'작성일자': month_label, '상호': "", '공급가액': group['공급가액'].sum(), '세액': group['세액'].sum(), '합계': group['합계'].sum()}])
                    final_rows.append(subtotal)
                grand_total = pd.DataFrame([{'작성일자': "총 계", '상호': "", '공급가액': temp_df['공급가액'].sum(), '세액': temp_df['세액'].sum(), '합계': temp_df['합계'].sum()}])
                final_rows.append(grand_total)
                return pd.concat(final_rows, ignore_index=True)

            a_df = format_with_subtotals(ansan_data)
            i_df = format_with_subtotals(incheon_data)

            st.success("✅ 정산이 완료되었습니다! 아래 결과를 확인해 주세요.")
            
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                a_df.to_excel(writer, sheet_name='안산_본점', index=False)
                i_df.to_excel(writer, sheet_name='인천_지점', index=False)
            
            st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_최종정산.xlsx")
            
            c1, c2 = st.columns(2)
            with c1: 
                st.subheader("🏢 안산 본점")
                st.dataframe(a_df, use_container_width=True)
            with c2: 
                st.subheader("🏭 인천 지점")
                st.dataframe(i_df, use_container_width=True)

    except Exception as e:
        st.error(f"🚨 예상치 못한 오류 발생: {e}")
