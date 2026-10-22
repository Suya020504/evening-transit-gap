"""연결 상실 하한을 원자료에서 다시 계산하고 평균 접근성 유형과 대조한다.
입력은 KTDB의 02_*.xlsx와 데이터/가공/기획/읍면동_저녁유형.csv다.
출력 파일은 없으며 문턱별 지역 수와 두 지표의 겹침을 화면에 출력한다.
"""
from pathlib import Path
import pandas as pd
import glob

ROOT = Path(__file__).resolve().parents[1]

f = glob.glob(str(ROOT / '데이터' / '원천_PC다운로드' / 'KTDB_교통접근성지표_2025' / 'unzip' / '02_*.xlsx'))[0]
accessibility = pd.read_excel(f, sheet_name=1, header=5, dtype=str)
accessibility = accessibility[accessibility.HDCD_LEV == '4'].copy()
cols = list(accessibility.columns)
accessibility.columns = cols[:15] + ['r15', 'r30', 'r45', 'r60']
for c in ['r15', 'r30', 'r45', 'r60']:
    accessibility[c] = pd.to_numeric(accessibility[c], errors='coerce')

def accessibility_ratio(fac, mode, tz, col):
    s = accessibility[(accessibility.FACI_CD == fac) & (accessibility.MODE == mode) & (accessibility.TIME_ZONE == tz)].set_index('HDCD')[col]
    return s

out = {}
for fac in ['22', '41']:
    midday_transit = accessibility_ratio(fac, '2_PT', '2_T1214', 'r60')
    evening_transit = accessibility_ratio(fac, '2_PT', '3_T1820', 'r60')
    evening_car = accessibility_ratio(fac, '1_PC', '3_T1820', 'r30')
    lb = (midday_transit + evening_car - evening_transit - 100).clip(lower=0)
    out[fac] = lb
lb = pd.concat(out, axis=1)
valid = lb.notna().all(axis=1)
meta = accessibility.drop_duplicates('HDCD').set_index('HDCD')[['HDCD_SD_NM', 'HDCD_SGG_NM', 'HDCD_EMD_NM']]
lb = lb.join(meta)
lb['either'] = lb[['22', '41']].max(axis=1)
v = lb[valid]
cnt = lambda m: int(m.sum())
# 탐색용 문턱 비교와 보호값을 뺀 하한의 정확 재계산을 모두 유지한다.
threshold_summary = {}
for thr in [10, 20, 30]:
    e = v.either >= thr - 0.015
    threshold_summary[thr] = {
        '병의원': cnt(v['22'] >= thr - 0.015),
        '터미널': cnt(v['41'] >= thr - 0.015),
        '어느시설이든': cnt(e),
        '군': cnt(e & v.HDCD_SGG_NM.str.endswith('군'))
    }
lb2 = {}
for fac in ['22', '41']:
    midday_transit = accessibility_ratio(fac, '2_PT', '2_T1214', 'r60')
    evening_transit = accessibility_ratio(fac, '2_PT', '3_T1820', 'r60')
    evening_car = accessibility_ratio(fac, '1_PC', '3_T1820', 'r30')
    lb2[fac] = (midday_transit + evening_car - evening_transit - 100 - 0.015).clip(lower=0)
lb2 = pd.concat(lb2, axis=1)[valid.reindex(lb.index).values]
e2 = lb2.max(axis=1) >= 20
t = pd.read_csv(ROOT / '데이터' / '가공' / '기획' / '읍면동_저녁유형.csv', dtype={'HDCD': str})
tc = [c for c in t.columns if '유형' in c][0]
t = t.set_index('HDCD')
bound_areas = set(lb2.index[e2])
average_areas = set(t.index[t[tc].astype(str).str[0].isin(list('ABC'))])
print('유효 지역', len(v), '문턱별 하한', threshold_summary)
print(
    '보호값 적용 하한20',
    int(e2.sum()),
    '군',
    int((e2 & meta.loc[lb2.index, 'HDCD_SGG_NM'].str.endswith('군')).sum()),
    '평균 유형',
    len(average_areas),
    '교집합',
    len(bound_areas & average_areas),
    '하한만',
    len(bound_areas - average_areas),
    '평균만',
    len(average_areas - bound_areas)
)
