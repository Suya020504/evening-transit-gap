"""연결 상실 하한의 기준선 민감도와 시군구 인구 가중 순위를 확인한다.
입력은 KTDB의 02_*.xlsx, 읍면동_저녁유형.csv, 조례790_규칙추출.csv다.
출력 파일은 없으며 기준선별 지역 수와 합천군 집계를 화면에 출력한다.
"""
from pathlib import Path
import pandas as pd
import glob

ROOT = Path(__file__).resolve().parents[1]

f = glob.glob(str(ROOT / '데이터' / '원천_PC다운로드' / 'KTDB_교통접근성지표_2025' / 'unzip' / '02_*.xlsx'))[0]
accessibility = pd.read_excel(f, sheet_name=1, header=5, dtype=str)
accessibility = accessibility[accessibility.HDCD_LEV == '4'].copy()
accessibility.columns = list(accessibility.columns[:15]) + ['r15', 'r30', 'r45', 'r60']
for c in ['r15', 'r30', 'r45', 'r60']:
    accessibility[c] = pd.to_numeric(accessibility[c], errors='coerce')

def accessibility_ratio(fac, mode, tz, col):
    return accessibility[
        (accessibility.FACI_CD == fac)
        & (accessibility.MODE == mode)
        & (accessibility.TIME_ZONE == tz)
    ].set_index('HDCD')[col]

meta = accessibility.drop_duplicates('HDCD').set_index('HDCD')[['HDCD_SD_NM', 'HDCD_SGG_NM', 'HDCD_EMD_NM']]

def connection_bound(base_tz):
    out = {}
    for fac in ['22', '41']:
        baseline_transit = accessibility_ratio(fac, '2_PT', base_tz, 'r60')
        evening_transit = accessibility_ratio(fac, '2_PT', '3_T1820', 'r60')
        evening_car = accessibility_ratio(fac, '1_PC', '3_T1820', 'r30')
        out[fac] = (baseline_transit + evening_car - evening_transit - 100 - 0.015).clip(lower=0)
    d = pd.DataFrame(out)
    d = d[d.notna().all(axis=1)]
    return d.max(axis=1)

res = {}
baseline_summary = {}
retention_summary = {}
for nm, tz in [('낮12-14', '2_T1214'), ('오전첨두07-09', '1_T0709'), ('일평균', '0_ALLDAY')]:
    b = connection_bound(tz)
    s = b >= 20
    res[nm] = s
    gun = meta.loc[b.index, 'HDCD_SGG_NM'].str.endswith('군')
    baseline_summary[nm] = {'하한20 이상': int(s.sum()), '군': int((s & gun).sum())}
base = res['낮12-14']
for nm in ['오전첨두07-09', '일평균']:
    o = res[nm].reindex(base.index).fillna(False)
    retention_summary[nm] = {'낮 기준에서 유지': int((base & o).sum()), '새로 들어옴': int((~base & o).sum())}
t = pd.read_csv(ROOT / '데이터' / '가공' / '기획' / '읍면동_저녁유형.csv', dtype={'HDCD': str}).set_index('HDCD')
b = connection_bound('2_T1214')
d = t[[
    'HDCD_SD_NM',
    'HDCD_SGG_NM',
    'HDCD_EMD_NM',
    'pop',
    'pop65',
    '군'
]].join(b.rename('lb'), how='inner')
d['lb65'] = d.lb / 100 * d.pop65
sg = d.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).agg(
    lb65=('lb65', 'sum'),
    n20=('lb', lambda s: int((s >= 20).sum())),
    pop65=('pop65', 'sum')
).sort_values('lb65', ascending=False)
sg['rank'] = range(1, len(sg) + 1)
h = d[(d.HDCD_SGG_NM == '합천군') & d.HDCD_EMD_NM.isin(['쌍책면', '대양면', '삼가면', '야로면', '가야면', '쌍백면'])]
o = pd.read_csv(ROOT / '데이터' / '가공' / '조례790_규칙추출.csv')
m = o[o.astype(str).apply(lambda r: r.str.contains('합천').any(), axis=1)]
print('기준선별 하한20', baseline_summary, '낮 기준 대비', retention_summary)
print(
    '전국 고령 가중 합',
    int(d.lb65.sum()),
    '합천 6개 면 인구',
    int(h['pop'].sum()),
    '65세 이상',
    int(h.pop65.sum()),
    '합천 조례',
    len(m),
    '시군구 순위',
    sg[sg.index.get_level_values(1).isin([
        '합천군',
        '해남군',
        '상주시',
        '창녕군',
        '의령군',
        '산청군',
        '하동군',
        '장성군'
    ])].round(0).to_dict(orient='index')
)
