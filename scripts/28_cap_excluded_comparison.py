"""120분 상한에 걸린 읍면동을 빼고 막차 집단별 저녁 악화 비율을 다시 비교한다.
입력은 07번의 막차_악화율_51.csv와 데이터/가공/KTDB_저녁낮_읍면동.csv다.
출력은 데이터/가공/통합/상한제외_비교.json이다.
집단은 20시 이후 출발 기록이 없는 10개 시·군과 그 밖의 전국 군이다.
병·의원 낮·저녁 값 중 하나라도 상한이면 빼고, 저녁이 낮보다 10분 넘게 늘면 악화로 센다.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
DATA = ROOT / '데이터' / '가공'
OUT = DATA / '통합'

last = pd.read_csv(OUT / '막차_악화율_51.csv', encoding='utf-8-sig')
early = set(last.loc[last['분'] < 20 * 60, '지자체명'])
k = pd.read_csv(DATA / 'KTDB_저녁낮_읍면동.csv', dtype={'HDCD': str})
k = k[(k['FACI_NM'] == '병·의원')].dropna(subset=['mid', 'eve'])
k = k[k['HDCD_SGG_NM'].str.endswith('군')]
# 이름이 같은 강원 고성군은 시간표 집계와 맞추려고 뺀다(07번과 같은 처리).
k = k[~((k['HDCD_SGG_NM'] == '고성군') & ~k['HDCD_SD_NM'].astype(str).str.contains('경상남도|경남'))]
k['집단'] = k['HDCD_SGG_NM'].map(lambda s: '20시 이후 출발 없음' if s in early else '그 밖의 군')
k['상한'] = k['cap_mid'].astype(bool) | k['cap_eve'].astype(bool)
k['악화'] = k['eve'] - k['mid'] > 10

result = {}
for name, g in k.groupby('집단'):
    kept = g[~g['상한']]
    result[name] = {'유효': int(len(g)), '상한제외후': int(len(kept)), '악화': int(kept['악화'].sum()),
                   '악화비율': round(float(kept['악화'].mean() * 100), 1)}
json.dump(result, open(OUT / '상한제외_비교.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False))
