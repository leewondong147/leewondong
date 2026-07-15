import streamlit as st
import pandas as pd
import numpy as np
import io

# ==========================================
# 1. 페이지 및 기본 환경 설정 (Ver 9.2 상호/날짜 정렬 수리판)
# ==========================================
st.set_page_config(page_title="호진환경 정산기", layout="wide")
st.title("📊 (주)호진환경 부가세 정산기 (Ver 9.2)")
st.caption("상호 칸에 날짜가 기입되고 수치가 0으로 나오던 컬럼 매핑 인지 꼬임 오류를 완벽하게 수리 완료했습니다.")

# 작업 선택
job_type = st.radio("👇 작업 선택", ["🛒 매입", "💰 매출", "💳 카드"])

uploaded_file = st.file_uploader("📂 원본 파일 올리기", type=["csv", "xlsx", "xls"])

# ==========================================
# 🛠️ [정밀 전처리 도구] 무결점 수치 추출기
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

        # 2. 제목 줄(Header) 찾기 로직
        header_row = 0
        found_header = False
        for i in range(min(len(df_raw), 25)):
            row_vals = df_raw.iloc[i].fillna('').values
            row_str = "".join(map(str, row_vals)).replace(" ", "")
            if any(k in row_str for k in ['일자', '공급가액', '승인번호', '거래처', '상호', '세액']):
                header_row = i
                found_header = True
                break
        
        uploaded_file.seek(0)
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file, skiprows=header_row)
        else:
            df = pd.read_excel(uploaded_file, skiprows=header_row)

        # 컬럼 양끝 공백 제거 및 정형화
        df.columns = [str(c).strip() for c in df.columns]

        # ==========================================
        # 🚨 3. [수리 완료] 정밀 기둥 매칭 알고리즘 (위치 수동 보정 가드레일)
        # ==========================================
        # 가. 작성일자 열 찾기
        c_date = next((c for c in df.columns if any(k in str(c) for k in ['작성일자', '작성일', '일자', '일시'])), None)
        if not c_date:
            c_date = df.columns[1] if len(df.columns) > 1 else df.columns[0] # 없으면 두 번째 열 강제 지정
            
        # 나. 상호명 열 찾기 (작성일자 기둥과 중복 선택되는 현상을 원천 방어합니다!)
        c_name = next((c for c in df.columns if any(k in str(c) for k in ['상호', '가맹점', '거래처', '회사명', '공급자']) and str(c) != c_date), None)
        if not c_name:
            # 엑셀 배치 구조상 일자 뒤에 상호가 위치하므로 안전한 하드 매핑 대입
            c_name = df.columns[3] if len(df.columns) > 3 else df.columns[1]
            
        # 다. 공급가액 및 세액 열 매칭
        c_supply = next((c for c in df.columns if any(k in str(c) for k in ['공급가액', '공급가', '공급가액(원)']) and str(c) not in [c_date, c_name]), None)
        if not c_supply:
            c_supply = next((c for c in df.columns if any(k in str(c) for k in ['금액', '합계', '승인금액', '이용금액']) and str(c) not in [c_date, c_name]), df.columns[-1])
            
        c_tax = next((c for c in df.columns if any(k in str(c) for k in ['세액', '부가세', '세액(원)']) and str(c) not in [c_date, c_name, c_supply]), None)

        # ==========================================
        # 🚨 [하드 보정 회로] 표준 홈택스 엑셀 파일일 때의 컬럼 번호 강제 보정
        # ==========================================
        # 컬럼명에 매칭이 실패했거나 잘못되었을 때 강제로 인덱스로 정밀 타격합니다.
        if "공급자" in df.columns or "상호" in df.columns:
            # 홈택스 표준 칼럼 매칭
            col_list = list(df.columns)
            for col_name in col_list:
                if "작성일자" in col_name or "작성일" in col_name:
                    c_date = col_name
                elif ("상호" in col_name or "공급자" in col_name or "대표자" in col_name) and "일자" not in col_name:
                    c_name = col_name
                elif "공급가액" in col_name:
                    c_supply = col_name
                elif "세액" in col_name:
                    c_tax = col_name

        # 4. 데이터 정제 및 실수형 매핑
        df[c_supply] = df[c_supply].apply(clean_value_secure)
        if c_tax:
            df[c_tax] = df[c_tax].apply(clean_value_secure)
        else:
            df['임시세액'] = df[c_supply] * 0.1 / 1.1 
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

        # 6. 결과 정리 및 그룹 연산
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

        # 7. 다운로드 및 표시
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            ansan_final.to_excel(writer, sheet_name='안산_본점', index=False)
            incheon_final.to_excel(writer, sheet_name='인천_지점', index=False)
        
        st.divider()
        st.success(f"✅ {job_type} 정산 완료!")
        st.download_button("📥 카드정산 엑셀 다운로드", output.getvalue(), "호진환경_정산_완료.xlsx")
        
        c1, c2 = st.columns(2)
        with c1: 
            st.subheader("🏢 안산 본점"); st.dataframe(ansan_final)
        with c2: 
            st.subheader("🏭 인천 지점"); st.dataframe(incheon_final)

    except Exception as e:
        st.error(f"🚨 오류 발생: {e} - 파일 형식이 평소와 다른지 확인해주세요.")
