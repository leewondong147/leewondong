import streamlit as st
import pandas as pd
import numpy as np
import io
import re

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.4 밀림 현상 영구 박멸판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.4)")
st.caption("제목에 숨은 줄바꿈 문자로 인한 '1칸 밀림(도미노) 에러'를 정규표현식 세척기로 완전히 분쇄했습니다.")

# 작업 선택
job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ [정밀 전처리 도구] 무결점 수치 및 날짜 추출기
# ==========================================
def clean_value_secure(val):
    """단일 값에 든 모든 쉼표, 한글, 공백을 물리적으로 지우고 순수 숫자로 변환합니다."""
    if pd.isna(val):
        return 0.0
    val_str = str(val).strip()
    val_str = val_str.replace(",", "").replace("원", "").replace('"', '').replace(" ", "")
    try:
        return float(val_str)
    except:
        return 0.0

def parse_flexible_date(series):
    """한글 날짜 및 기호 날짜 형식을 표준 datetime으로 동기화합니다."""
    cleaned = series.astype(str).str.replace('"', '').str.strip()
    cleaned = cleaned.str.replace('년', '-').str.replace('월', '-').str.replace('일', '')
    return pd.to_datetime(cleaned, errors='coerce')

if uploaded_file is not None:
    try:
        # 1. 파일 읽기 (글자 형식으로 안전하게)
        if uploaded_file.name.endswith('.csv'):
            df_raw = pd.read_csv(uploaded_file, header=None, dtype=str)
        else:
            df_raw = pd.read_excel(uploaded_file, header=None, dtype=str)

        # 2. 🚨 [수리 핵심] 제목 줄(Header) 강제 사냥 로직
        header_row = 0
        found_header = False
        for i in range(min(len(df_raw), 25)):
            row_str = "".join(map(str, df_raw.iloc[i].fillna('').values))
            # 숨어있는 줄바꿈과 특수문자를 완전히 무시하고 오직 글자만 봅니다!
            cleaned_row = re.sub(r'[^가-힣a-zA-Z0-9]', '', row_str)
            
            if ('승인번호' in cleaned_row and '공급가액' in cleaned_row) or \
               ('작성일자' in cleaned_row and '공급가액' in cleaned_row) or \
               ('일자' in cleaned_row and '상호' in cleaned_row):
                header_row = i
                found_header = True
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 🚨 [수리 핵심] 컬럼명 자체에 묻어있는 특수문자/줄바꿈/공백 완전 소독 (알파벳, 숫자, 한글만 남김)
        df.columns = [re.sub(r'[^가-힣a-zA-Z0-9]', '', str(c)) for c in df.columns]

        # ==========================================
        # 🚨 3. [초강력 매핑] 승인번호 밀림 방지 및 매입/매출 분리 추적
        # ==========================================
        # 가. 작성일자 열 찾기
        c_date = next((c for c in df.columns if '작성일자' in c), None)
        if not c_date: 
            c_date = next((c for c in df.columns if '일자' in c), df.columns[1] if len(df.columns)>1 else df.columns[0])

        # 나. 👑 상호명 열 찾기 (매입/매출 완벽 분리 타격!)
        if job_type == "🛒 매입":
            # 매입: 우리가 돈을 낸 것 (상대방은 첫 번째 상호인 '공급자')
            c_name = next((c for c in df.columns if c == '상호' or '공급자상호' in c), None)
        elif job_type == "💰 매출":
            # 매출: 우리가 돈을 받은 것 (상대방은 두 번째 상호인 '공급받는자', 판다스가 중복처리하여 '상호1'이 됨)
            c_name = next((c for c in df.columns if c == '상호1' or '공급받는자상호' in c), None)
            if not c_name: c_name = next((c for c in df.columns if '상호' in c), None)
        else:
            # 카드
            c_name = next((c for c in df.columns if '가맹점' in c or '상호' in c or '거래처' in c), None)
            
        if not c_name:
            c_name = df.columns[6] if len(df.columns) > 6 else df.columns[2]

        # 다. 공급가액 및 세액 열 매칭
        c_supply = next((c for c in df.columns if '공급가액' in c), None)
        if not c_supply: 
            c_supply = next((c for c in df.columns if '합계' in c or '금액' in c), df.columns[-2] if len(df.columns)>2 else df.columns[-1])
            
        c_tax = next((c for c in df.columns if '세액' in c), None)

        # 4. 데이터 안전 파싱 및 수치 형변환 전개
        df[c_supply] = df[c_supply].apply(clean_value_secure)
        if c_tax:
            df[c_tax] = df[c_tax].apply(clean_value_secure)
        else:
            df['임시세액'] = df[c_supply] * 0.1
            c_tax = '임시세액'

        df['합계'] = df[c_supply] + df[c_tax]
        
        parsed_dates = parse_flexible_date(df[c_date])
        df['월'] = parsed_dates.dt.month.fillna(0).astype(int)

        ansan_list, incheon_list = [], []

        # 5. 분류 로직
        for idx, row in df.iterrows():
            full_text = "".join(map(str, row.fillna('').values)).replace(" ", "").lower()
            
            if '남상민' in full_text:
                ansan_list.append(row)
            elif any(k in full_text for k in ['성남수정', '성남경찰서', '6114hojin', 'tpy1004']):
                ansan_list.append(row)
            else:
                incheon_list.append(row)

        # 6. 결과 정리 및 소계/총계 연산
        def format_df(data_list):
            if not data_list: return pd.DataFrame()
            temp = pd.DataFrame(data_list).sort_values(by=['월', c_date])
            display_df = pd.DataFrame()
            display_df['작성일자'] = temp[c_date]
            display_df['상호'] = temp[c_name]
            display_df['공급가액'] = temp[c_supply]
            display_df['세액'] = temp[c_tax]
            display_df['합계'] = temp['합계']
            
            final_rows = []
            temp_dates = parse_flexible_date(display_df['작성일자'])
            display_df['temp_month'] = temp_dates.dt.month.fillna(0).astype(int)
            
            for month, group in display_df.groupby('temp_month'):
                group_clean = group.drop(columns=['temp_month'])
                final_rows.append(group_clean)
                
                sub = pd.DataFrame([{
                    '작성일자': f"{int(month)}월 소계", 
                    '상호': "", 
                    '공급가액': group['공급가액'].sum(), 
                    '세액': group['세액'].sum(), 
                    '합계': group['합계'].sum()
                }])
                final_rows.append(sub)
            
            grand = pd.DataFrame([{
                '작성일자': "총 계", 
                '상호': "", 
                '공급가액': display_df['공급가액'].sum(), 
                '세액': display_df['세액'].sum(), 
                '합계': display_df['합계'].sum()
            }])
            final_rows.append(grand)
            return pd.concat(final_rows, ignore_index=True)

        ansan_final = format_df(ansan_list)
        incheon_final = format_df(incheon_list)

        # 7. 다운로드 및 결과 출력
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 정산 엑셀 다운로드", output.getvalue(), f"호진환경_{job_type}_정산완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: 
            st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 파일 형식이 평소와 다른지 확인해주세요.")
