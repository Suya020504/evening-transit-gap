"""낮·저녁 접근시간의 상한 여부를 결합하고 판정 불가 범주를 구분한다.
입력은 읍면동_통합판정.csv와 데이터/가공/기획/읍면동_저녁유형.csv다.
출력은 데이터/가공/통합의 읍면동_통합판정.csv와 통합지표_보조.json이다.
"""
from pathlib import Path
import pandas as pd
import json

ROOT = Path(__file__).resolve().parents[1]

output_dir = ROOT / '데이터' / '가공' / '통합'
assessment = pd.read_csv(output_dir / '읍면동_통합판정.csv', dtype={'HDCD': str})
area_types = pd.read_csv(ROOT / '데이터' / '가공' / '기획' / '읍면동_저녁유형.csv', dtype={'HDCD': str})
area_types = area_types.set_index('HDCD')
assessment = assessment.set_index('HDCD')
for c in ['cap_mid_병·의원', 'cap_eve_병·의원', 'mid_병·의원', 'eve_병·의원']:
    assessment[c] = area_types[c]
valid = assessment['mid_병·의원'].notna() & assessment['eve_병·의원'].notna()
gun = assessment['군'] == 1
worse = assessment['eve_병·의원'] - assessment['mid_병·의원'] > 10
summary = {}
summary['군_유효'] = int((valid & gun).sum())
summary['군_10분초과악화'] = int((valid & gun & worse).sum())
summary['시구_유효'] = int((valid & ~gun).sum())
summary['시구_10분초과악화'] = int((valid & ~gun & worse).sum())
summary['군_악화율'] = round(100 * summary['군_10분초과악화'] / summary['군_유효'], 2)
summary['시구_악화율'] = round(100 * summary['시구_10분초과악화'] / summary['시구_유효'], 2)
both_capped = valid & assessment['cap_mid_병·의원'].astype(bool) & assessment['cap_eve_병·의원'].astype(bool)
summary['양쪽상한'] = int(both_capped.sum())
summary['양쪽상한_D'] = int((both_capped & assessment['유형'].astype(str).str.startswith('D')).sum())
summary['양쪽상한_65'] = int(assessment.loc[both_capped, 'pop65'].sum())
summary['양쪽상한_군'] = int((both_capped & gun).sum())
summary['양쪽상한_하한20'] = int((both_capped & (assessment.lb_mid >= 20)).sum())
e60 = assessment['유형'].astype(str).str.startswith('E') & (assessment['eve_병·의원'] > 60)
summary['E_저녁60초과'] = int(e60.sum())

def classify_capped(r, b):
    if r['판정2'].startswith('4') and b:
        return '5 판정 불가: 낮·저녁 모두 120분 초과'
    return r['판정2']

assessment['판정3'] = [classify_capped(r, b) for (_, r), b in zip(assessment.iterrows(), both_capped)]
g = assessment.groupby('판정3').agg(
    n=('pop65', 'size'),
    군=('군', 'sum'),
    pop65=('pop65', 'sum'),
    pop1318=('pop1318', 'sum'),
    하한65=('lb65_mid', 'sum')
)
h = assessment[(assessment.HDCD_SGG_NM == '합천군') & assessment['판정2'].str.startswith('1')]
assessment.reset_index().to_csv(output_dir / '읍면동_통합판정.csv', index=False, encoding='utf-8-sig')
json.dump(
    summary,
    open(output_dir / '통합지표_보조.json', 'w', encoding='utf-8'),
    ensure_ascii=False,
    indent=1
)
print('상한·악화율', summary)
print(
    '판정별 읍면동',
    g['n'].to_dict(),
    '합천 일치 지역',
    len(h),
    '인구',
    int(h['pop'].sum()),
    '전국 하한65',
    int(assessment.lb65_mid.sum())
)
