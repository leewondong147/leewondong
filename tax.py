# 3. 열 번호(좌표) 추출 로직 강화
        header_list = df_raw.iloc[header_row_idx].fillna('').astype(str).tolist()
        # 헤더 이름 자체에서도 공백과 줄바꿈을 완벽히 제거합니다.
        header_list = [re.sub(r'\s+', '', col) for col in header_list]

        # 단어가 정확히 일치하지 않아도 포함되어 있으면 찾아내도록 강화
        idx_date = next((i for i, col in enumerate(header_list) if '작성일자' in col), -1)
        idx_sup = next((i for i, col in enumerate(header_list) if '공급가액' in col or '금액' in col), -1)
        idx_tax = next((i for i, col in enumerate(header_list) if '세액' in col), -1)

        # 🚨 [완벽 방어 업데이트] 진짜 거래처 알아서 찾아내는 AI 로직
        name_indices = [i for i, col in enumerate(header_list) if '상호' in col or '거래처' in col or '업체' in col]
        
        idx_name = -1
        if not name_indices:
            idx_name = -1
        elif len(name_indices) == 1:
            idx_name = name_indices[0] # 기둥이 하나면 무조건 그걸로 선택
        else:
            # 기둥이 여러 개일 경우, 그 기둥의 데이터(아래 5줄)를 미리 읽어봅니다.
            for idx in name_indices:
                sample_values = df_raw.iloc[header_row_idx+1:header_row_idx+6, idx].fillna('').astype(str).tolist()
                
                # 해당 기둥에 '호진'이라는 이름이 몇 개나 있는지 카운트합니다.
                hojin_count = sum(1 for val in sample_values if '호진' in val)
                
                # '호진'이 절반 미만인 기둥이 바로 '진짜 상대방 거래처(클라이언트)'입니다.
                if hojin_count < len(sample_values) * 0.5:
                    idx_name = idx
                    break
            
            # 혹시라도 판별이 안 되었다면 기존 로직(사이드바 버튼 기준)으로 안전하게 백업
            if idx_name == -1:
                idx_name = name_indices[1] if job_type == "💰 매출" else name_indices[0]

        # 필수 열 번호를 제대로 찾았는지 안전 검사
        if -1 in [idx_date, idx_sup, idx_name]:
             st.error("🚨 제목줄은 찾았으나, 날짜/공급가액/상호 기둥을 정확히 분류하지 못했습니다.")
             st.stop()
