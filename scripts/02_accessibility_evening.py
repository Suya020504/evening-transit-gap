"""KTDB의 낮·저녁 접근시간을 비교하고 막차 시각과 악화율의 상관을 계산한다.
입력은 KTDB_교통접근성지표_2025 원자료와 노선시간표_지자체요약.csv다.
출력은 데이터/가공의 KTDB_저녁낮_읍면동.csv와 KTDB_저녁악화_시군구.csv다.
"""
from pathlib import Path
import os
import zipfile
import glob
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]

source_dir = ROOT / '데이터' / '원천_PC다운로드' / 'KTDB_교통접근성지표_2025'
archive_path = source_dir / '2025년_교통접근성지표.zip'
extract_dir = source_dir / 'unzip'
if not os.path.isdir(extract_dir):
    with zipfile.ZipFile(archive_path) as z:
        for info in z.infolist():
            name = info.filename
            try:
                name = name.encode('cp437').decode('cp949')
            except Exception:
                pass
            p = extract_dir / name
            if info.is_dir():
                os.makedirs(p, exist_ok=True)
                continue
            os.makedirs(os.path.dirname(p), exist_ok=True)
            open(p, 'wb').write(z.read(info))
xl = [f for f in glob.glob(str(extract_dir / '**' / '*.xlsx'), recursive=True)]
f = [x for x in xl if '평균' in os.path.basename(x)] or xl
d = pd.read_excel(f[0], sheet_name='평균접근시간', header=5, dtype=str)
d = d[(d['HDCD_LEV'] == '4') & (d['MODE'] == '2_PT')].copy()
v = d['평균접근시간(분)'].astype(str).str.strip()
d['cap'] = v.str.startswith('>')
d['val'] = pd.to_numeric(v.str.replace('>', '', regex=False), errors='coerce')
area_facility_keys = ['HDCD', 'HDCD_SD_NM', 'HDCD_SGG_NM', 'HDCD_EMD_NM', 'FACI_NM']
time_comparison = None
for tz, nm in [('0_ALLDAY', 'all'), ('2_T1214', 'mid'), ('3_T1820', 'eve')]:
    x = d[d['TIME_ZONE'] == tz][area_facility_keys + ['val', 'cap']].rename(columns={'val': nm, 'cap': 'cap_' + nm}).drop_duplicates(area_facility_keys)
    time_comparison = x if time_comparison is None else time_comparison.merge(x, on=area_facility_keys, how='outer')
time_comparison['d_eve_mid'] = time_comparison['eve'] - time_comparison['mid']
focus_counties = [
    '거창군',
    '울릉군',
    '해남군',
    '진안군',
    '의성군',
    '산청군',
    '칠곡군',
    '무주군',
    '하동군',
    '의령군',
    '진도군',
    '장흥군',
    '합천군'
]
time_comparison['grp'] = np.where(
    time_comparison['HDCD_SGG_NM'].isin(focus_counties),
    '13개 군',
    np.where(time_comparison['HDCD_SGG_NM'].str.endswith('군'), '다른 군', '시·구')
)
time_comparison.to_csv(ROOT / '데이터' / '가공' / 'KTDB_저녁낮_읍면동.csv', index=False, encoding='utf-8-sig')
facility_summary = {}
for fac in ['병·의원', '공공의료시설', '버스터미널']:
    q = time_comparison[time_comparison['FACI_NM'] == fac]
    t = q.groupby('grp').agg(
        읍면동=('HDCD', 'size'),
        낮중앙=('mid', 'median'),
        저녁중앙=('eve', 'median'),
        저녁10분악화=('d_eve_mid', lambda s: round((s > 10).mean() * 100, 1))
    )
    facility_summary[fac] = t.to_dict(orient='index')
q = time_comparison[time_comparison['FACI_NM'] == '병·의원']
g = q.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).agg(
    읍면동=('HDCD', 'size'),
    악화비율=('d_eve_mid', lambda s: (s > 10).mean())
).reset_index()
g.to_csv(ROOT / '데이터' / '가공' / 'KTDB_저녁악화_시군구.csv', index=False, encoding='utf-8-sig')
s = pd.read_csv(ROOT / '데이터' / '가공' / '노선시간표_지자체요약.csv')
s['last'] = s['최종출발'].map(lambda t: int(t[:2]) * 60 + int(t[3:5]))
area_matches = g.copy()
area_matches['key'] = area_matches['HDCD_SGG_NM']
# 시간표의 고성군은 경상남도이므로 동명 군을 제외한다.
area_matches = area_matches[~((area_matches['HDCD_SGG_NM'] == '고성군') & (area_matches['HDCD_SD_NM'] != '경상남도'))]
m = s.merge(area_matches, left_on='지자체명', right_on='key', how='left')
r = spearmanr(m['last'], m['악화비율'])
k = int(round(len(q) * 0.1))

def worst_time_areas(col):
    qq = q.dropna(subset=[col])
    thr = qq[col].sort_values(ascending=False).iloc[k - 1]
    return set(qq[qq[col] >= thr]['HDCD'])

A, E = (worst_time_areas('all'), worst_time_areas('eve'))
print(
    '읍면동×시설',
    len(time_comparison),
    '시군구',
    len(g),
    '시간표 결합',
    int(m['읍면동'].notna().sum()),
    '시설별 집계',
    facility_summary
)
print(
    '막차·악화율 상관',
    round(r.statistic, 3),
    'p',
    round(r.pvalue, 4),
    '일평균·저녁 하위10% 겹침',
    len(A & E),
    '저녁에만',
    len(E - A)
)
