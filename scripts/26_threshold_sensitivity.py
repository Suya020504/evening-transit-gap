"""저녁 악화 문턱(5·10·15·20·30분)을 바꿔 군·시구 악화 비율과 두 지표 일치 곳 수를 다시 센다.
입력은 데이터/가공/통합/읍면동_최종판정.csv다.
출력은 데이터/가공/통합/문턱민감도.json이다.
저녁만 120분 상한이면 실제 악화폭이 120 - 낮 값보다 크므로 그 값이 문턱 이상일 때 악화로 센다.
낮·저녁 모두 상한이거나 낮만 상한이면 악화로 세지 않는다.
"""
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
OUT = ROOT / '데이터' / '가공' / '통합'

d = pd.read_csv(OUT / '읍면동_최종판정.csv', dtype={'HDCD': str})
v = d.dropna(subset=['mid_병·의원', 'eve_병·의원'])
mid, eve = v['mid_병·의원'], v['eve_병·의원']
cap_mid, cap_eve = v['cap_mid_병·의원'].astype(bool), v['cap_eve_병·의원'].astype(bool)
gun = v['군'].astype(bool)


def worse_at(t):
    return (~cap_mid & ~cap_eve & (eve - mid > t)) | (cap_eve & ~cap_mid & (120 - mid >= t))


# 10분 문턱은 보고서 판정(유형 A·B·C, 두 지표 일치)과 같아야 한다.
assert (worse_at(10) == v['유형'].astype(str).str[0].isin(['A', 'B', 'C'])).all()
assert ((worse_at(10) & (v['lb_mid'] >= 20)) == v['최종판정'].eq('1 두 지표 일치')).all()

result = {}
for t in (5, 10, 15, 20, 30):
    w = worse_at(t)
    result[f'{t}분'] = {'군': [int(w[gun].sum()), int(gun.sum()), round(float(w[gun].mean() * 100), 1)],
                       '시·구': [int(w[~gun].sum()), int((~gun).sum()), round(float(w[~gun].mean() * 100), 1)],
                       '두지표일치': int((w & (v['lb_mid'] >= 20)).sum())}
json.dump(result, open(OUT / '문턱민감도.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(result, ensure_ascii=False))
