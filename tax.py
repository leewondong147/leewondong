import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 설정
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 10.2 소계 적용판)")
st.caption("안정적인 클린 배열과 전체 텍스트 스캔 엔진에, 월별 소계 및 총계 기능을 추가했습니다.")

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
        # 4. 데이터 스플릿 및 분류
        # ==========================================
        for _, row in df_data.iterrows():
            date_str = str(row[idx_date]).strip()
            
            if not date_str or date_str == 'nan' or '조회' in date_str or '합계' in date_str or len(date_str) < 5:
                continue
                
            name_str = str(row[idx_name]).replace(" ", "").lower()
            if name_str == 'nan': continue

            # 전체 텍스트 스캔 (안산 키워드 탐색용)
            full_text = "".join(row.fillna('').astype(str)).replace(" ", "").lower()

            sup_val = clean_value_secure(row[idx_sup])
            tax_val = clean_value_secure(row[idx_tax])

            is_split = False
            current_ratio = ansan_ratio / 100.0

            # 분배 로직
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
                if '남상민' in full_text or any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                    ansan_data.append([date_str, row[idx_name], sup_val, tax_val, sup_val + tax_val])
                else:
                    incheon_data.append([date_str, row[idx_name], sup_val, tax_val, sup_val + tax_val])

        # ==========================================
        # 5. 💡 월별 소계 및 총계 생성 함수
        # ==========================================
        final_columns = ['작성일자', '상호', '공급가액', '세액', '합계']
        
        def format_with_subtotals(data_list):
            if not data_list:
                return pd.DataFrame(columns=final_columns)
            
            # 1. 임시 데이터프레임 생성 및 날짜 변환
            temp_df = pd.DataFrame(data_list, columns=final_columns)
            temp_dates = parse_flexible_date(temp_df['작성일자'])
            temp_df['월'] = temp_dates.dt.month.fillna(0).astype(int)
            
            # 2. 날짜순으로 정렬
            temp_df = temp_df.sort_values(by=['월', '작성일자'])
            
            final_rows = []
            
            # 3. 월별로 그룹화하여 소계 추가
            for month, group in temp_df.groupby('월'):
                group_clean = group.drop(columns=['월'])
                final_rows.append(group_clean)
                
                month_label = f"{int(month)}월 소계" if month > 0 else "기타(날짜미상) 소계"
                
                subtotal = pd.DataFrame([{
                    '작성일자': month_label, 
                    '상호': "", 
                    '공급가액': group['공급가액'].sum(), 
                    '세액': group['세액'].sum(), 
                    '합계': group['합계'].sum()
                }])
                final_rows.append(subtotal)
            
            # 4. 전체 총계 추가
            grand_total = pd.DataFrame([{
                '작성일자': "총 계", 
                '상호': "", 
                '공급가액': temp_df['공급가액'].sum(), 
                '세액': temp_df['세액'].sum(), 
                '합계': temp_df['합계'].sum()
            }])
            final_rows.append(grand_total)
            
            return pd.concat(final_rows, ignore_index=True)

        # 소계 및 총계 함수 적용
        a_df = format_with_subtotals(ansan_data)
        i_df = format_with_subtotals(incheon_data)

        # ==========================================
        # 6. 화면 출력 및 다운로드
        # ==========================================
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            a_df.to_excel(writer, sheet_name='안산_본점', index=False)
            i_df.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료 (소계 적용)!")
        st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_정산완료_소계.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점")
            st.dataframe(a_df, use_container_width=True)
        with c2: 
            st.subheader("🏭 인천 지점")
            st.dataframe(i_df, use_container_width=True)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e}")
