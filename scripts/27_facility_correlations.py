"""막차 시각과 저녁 악화 비율의 순위상관을 목적지 시설별로 다시 계산한다.
입력은 07번의 막차_악화율_51.csv(51개 시·군의 보정 막차 시각)와 데이터/가공/KTDB_저녁낮_읍면동.csv다.
출력은 데이터/가공/통합/시설별_막차상관.json이다. 악화는 07번과 같이 저녁이 낮보다 10분 넘게 늘어난 경우다.
"""
import json
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
DATA = ROOT / '데이터' / '가공'
OUT = DATA / '통합'

last = pd.read_csv(OUT / '막차_악화율_51.csv', encoding='utf-8-sig')[['지자체명', '분']]
k = pd.read_csv(DATA / 'KTDB_저녁낮_읍면동.csv', dtype={'HDCD': str})
# 이름이 같은 강원 고성군은 빼고 경남 고성군만 쓴다(07번과 같은 처리).
k = k[~((k['HDCD_SGG_NM'] == '고성군') & ~k['HDCD_SD_NM'].astype(str).str.contains('경상남도|경남'))]

result = {}
for facility in ('병·의원', '공공의료시설', '버스터미널', '고등학교'):
    f = k[k['FACI_NM'] == facility].dropna(subset=['mid', 'eve'])
    rate = (f.assign(worse=f['eve'] - f['mid'] > 10).groupby('HDCD_SGG_NM')['worse'].mean() * 100).rename('rate')
    m = last.merge(rate, left_on='지자체명', right_index=True, how='inner')
    r = spearmanr(m['분'], m['rate'])
    result[facility] = {'n': int(len(m)), 'rho': round(float(r.correlation), 3), 'p': round(float(r.pvalue), 4)}
json.dump(result, open(OUT / '시설별_막차상관.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False))
