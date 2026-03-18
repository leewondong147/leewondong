import pandas as pd
import random
from collections import Counter

def get_recommendation(df):
    # 실제 CSV 컬럼명에 맞춰 수정하세요!
    cols = ['번호1', '번호2', '번호3', '번호4', '번호5', '번호6']
    all_numbers = df[cols].values.flatten().tolist()
    
    # 핫 넘버 (자주 나온 번호 상위 15개)
    counts = Counter(all_numbers)
    hot_candidates = [num for num, count in counts.most_common(15)]
    
    # 콜드 넘버 (최근 10회차 미출현)
    recent_numbers = df[cols].head(10).values.flatten().tolist()
    cold_candidates = [n for n in range(1, 45) if n not in recent_numbers]
    
    # 조합: 핫 3개 + 콜드 3개
    res = set(random.sample(hot_candidates, 3))
    res.update(random.sample(cold_candidates, 6 - len(res)))
    
    return sorted(list(res)), counts
