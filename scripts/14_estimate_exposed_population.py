"""시설별 연결 상실 하한을 인구로 환산하고 저녁 접근성 유형과 대조한다.
입력은 KTDB의 02_*.xlsx와 데이터/가공/기획/읍면동_저녁유형.csv다.
출력 파일은 없으며 시설별 환산 인구와 유형별 집계를 화면에 출력한다.
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

lb = {}
for fac, nm in [('22', '병의원'), ('41', '터미널'), ('13', '고교'), ('21', '공공의료')]:
    midday_transit = accessibility_ratio(fac, '2_PT', '2_T1214', 'r60')
    evening_transit = accessibility_ratio(fac, '2_PT', '3_T1820', 'r60')
    evening_car = accessibility_ratio(fac, '1_PC', '3_T1820', 'r30')
    lb[nm] = (midday_transit + evening_car - evening_transit - 100 - 0.015).clip(lower=0)
lb = pd.DataFrame(lb)
t = pd.read_csv(ROOT / '데이터' / '가공' / '기획' / '읍면동_저녁유형.csv', dtype={'HDCD': str}).set_index('HDCD')
d = lb.join(t[['HDCD_SGG_NM', 'pop', 'pop65', 'pop1318', '유형', '군']], how='inner')
population_summary = {}
for nm in ['병의원', '터미널', '고교', '공공의료']:
    v = d[d[nm].notna()]
    population_summary[nm] = {
        '65세 이상': int((v[nm] / 100 * v.pop65).sum()),
        '전체': int((v[nm] / 100 * v['pop']).sum()),
        '13~18세': int((v[nm] / 100 * v.pop1318).sum()),
        '군 65세 이상': int((v[v.군 == 1][nm] / 100 * v[v.군 == 1].pop65).sum()) if '군' in v else ''
    }
d['either'] = d[['병의원', '터미널']].max(axis=1)
v = d[d['병의원'].notna() & d['터미널'].notna()]
v2 = d[d['고교'].notna()]
d['bound20'] = d.either >= 20
type_summary = d.groupby('유형').apply(lambda accessibility_ratio: pd.Series({
    'n': len(accessibility_ratio),
    '65+': accessibility_ratio.pop65.sum(),
    '병의원하한65': (accessibility_ratio['병의원'].fillna(0) / 100 * accessibility_ratio.pop65).sum()
})).round(0).to_dict(orient='index')
print('시설별 인구 환산', population_summary)
print(
    '병의원·터미널 고령 환산',
    int((v.either / 100 * v.pop65).sum()),
    '고교 청소년 환산',
    int((v2['고교'] / 100 * v2.pop1318).sum()),
    '유형 교차표',
    pd.crosstab(d['유형'], d['bound20'], margins=True).to_dict(),
    '유형별 고령 환산',
    type_summary
)
