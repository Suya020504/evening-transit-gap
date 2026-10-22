"""읍면동의 저녁 접근성 유형을 분류하고 인구·행정동 경계를 결합한다.
입력은 KTDB_저녁낮_읍면동.csv, 주민등록인구 CSV, 행정동 경계 GeoJSON이다.
출력은 데이터/가공/기획의 읍면동_저녁유형.csv, 유형별_요약.csv, 시군구_저녁공백.csv다.
"""
from pathlib import Path
import json
import re
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

data_dir = ROOT / '데이터'
output_dir = data_dir / '가공' / '기획'
output_dir.mkdir(parents=True, exist_ok=True)
k = pd.read_csv(data_dir / '가공' / 'KTDB_저녁낮_읍면동.csv')
k['HDCD'] = k['HDCD'].astype(str)
facilities = ['병·의원', '공공의료시설', '버스터미널', '고등학교']
w = k[k.FACI_NM.isin(facilities)].pivot_table(
    index=['HDCD', 'HDCD_SD_NM', 'HDCD_SGG_NM', 'HDCD_EMD_NM'],
    columns='FACI_NM',
    values=['all', 'mid', 'eve', 'cap_mid', 'cap_eve'],
    aggfunc='first'
)
w.columns = [f'{a}_{b}' for a, b in w.columns]
w = w.reset_index()
g = json.load(open(
    data_dir / '원천_PC다운로드' / '행정동경계_admdongkor' / 'HangJeongDong_ver20261001.geojson',
    encoding='utf-8'
))
pr = pd.DataFrame([f['properties'] for f in g['features']])
pr['emd'] = pr.adm_nm.str.split(' ').str[-1]

def normalize_province(s):
    s = str(s)
    for a, b in [
        ('강원도', '강원'),
        ('강원특별자치도', '강원'),
        ('전라북도', '전북'),
        ('전북특별자치도', '전북'),
        ('제주특별자치도', '제주')
    ]:
        s = s.replace(a, b)
    return s[:2]

pr['sdk'] = pr.sidonm.map(normalize_province)
w['sdk'] = w.HDCD_SD_NM.map(normalize_province)
# 행정동 코드가 맞지 않으면 시도·시군구·읍면동 이름을 순서대로 대조한다.
boundary_matches = w.merge(pr[['adm_cd', 'adm_cd2']], left_on='HDCD', right_on='adm_cd', how='left')
miss = boundary_matches.adm_cd2.isna()
nm = pr.drop_duplicates(['sdk', 'sggnm', 'emd'])[['sdk', 'sggnm', 'emd', 'adm_cd2']]
fill = boundary_matches[miss].drop(columns=['adm_cd', 'adm_cd2']).merge(
    nm,
    left_on=['sdk', 'HDCD_SGG_NM', 'HDCD_EMD_NM'],
    right_on=['sdk', 'sggnm', 'emd'],
    how='left'
)
boundary_matches.loc[miss, 'adm_cd2'] = fill['adm_cd2'].values
miss = boundary_matches.adm_cd2.isna()
nm2 = pr.groupby(['sggnm', 'emd']).adm_cd2.agg(lambda x: x.iloc[0] if len(x) == 1 else None).dropna().reset_index()
f2 = boundary_matches[miss][['HDCD_SGG_NM', 'HDCD_EMD_NM']].merge(
    nm2,
    left_on=['HDCD_SGG_NM', 'HDCD_EMD_NM'],
    right_on=['sggnm', 'emd'],
    how='left'
)
boundary_matches.loc[miss, 'adm_cd2'] = f2['adm_cd2'].values
miss = boundary_matches.adm_cd2.isna()
grp = {'전남': '전남광주', '광주': '전남광주', '인천': '인천', '경기': '경기'}
pr['rg'] = pr.sidonm.map(lambda s: '전남광주' if '전남' in s or '광주' in s or '전라남' in s else normalize_province(s))
boundary_matches['rg'] = boundary_matches.sdk.map(lambda s: grp.get(s, s))
nm3 = pr.groupby(['rg', 'emd']).adm_cd2.agg(lambda x: x.iloc[0] if len(x) == 1 else None).dropna().reset_index()
f3 = boundary_matches[miss][['rg', 'HDCD_EMD_NM']].merge(
    nm3,
    left_on=['rg', 'HDCD_EMD_NM'],
    right_on=['rg', 'emd'],
    how='left'
)
boundary_matches.loc[miss, 'adm_cd2'] = f3['adm_cd2'].values
pf = next((data_dir / '원천_PC다운로드' / '공공데이터포털_지정').glob('15097972_*/*.csv'))
p = pd.read_csv(pf, encoding='cp949')
p['adm_cd2'] = p['행정기관코드'].astype(str)
age = {c: int(re.match(r'(\d+)세', c).group(1)) for c in p.columns if re.match(r'^\d+세(남자|여자)$', c)}
old = [c for c, a in age.items() if a >= 65]
# 110세 이상처럼 별도 표기된 최상위 연령도 포함한다.
old += [c for c in p.columns if '100세 이상' in c or '110세이상' in c]
teen = [c for c, a in age.items() if 13 <= a <= 18]
p['pop'] = p['계']
p['pop65'] = p[old].sum(axis=1)
p['pop1318'] = p[teen].sum(axis=1)
boundary_matches['adm_cd2'] = boundary_matches.adm_cd2.astype(str)
area_types = boundary_matches.merge(p[['adm_cd2', 'pop', 'pop65', 'pop1318']], on='adm_cd2', how='left')
midday_minutes = area_types['mid_병·의원']
evening_minutes = area_types['eve_병·의원']
evening_change = evening_minutes - midday_minutes
evening_capped = area_types['cap_eve_병·의원'].astype(bool)
midday_capped = area_types['cap_mid_병·의원'].astype(bool)

def classify_type(Mv, Dv, cM, cE, t1=60, t2=30):
    if pd.isna(Mv) or pd.isna(Dv):
        return '값 없음'
    if Mv <= t1 and (Dv >= t2 or (cE and (not cM))):
        return 'A 저녁 단절형'
    if Mv <= t1 and Dv > 10:
        return 'B 저녁 악화형'
    if Mv > t1 and Dv > 10:
        return 'C 상시 취약·저녁 악화형'
    if Mv > t1:
        return 'D 상시 취약형'
    return 'E 양호'

area_types['유형'] = [
    classify_type(a, b, c, d) for (a, b, c, d) in zip(midday_minutes, evening_change, midday_capped, evening_capped)
]
area_types['d_병의원'] = evening_change
area_types['저녁악화시설수'] = sum(((area_types[f'eve_{f}'] - area_types[f'mid_{f}'] > 10).astype(int) for f in facilities))
area_types['군'] = area_types.HDCD_SGG_NM.astype(str).str.endswith('군')
area_types.to_csv(output_dir / '읍면동_저녁유형.csv', index=False, encoding='utf-8-sig')
t = area_types.groupby('유형').agg(
    읍면동=('HDCD', 'size'),
    군소재=('군', 'sum'),
    인구=('pop', 'sum'),
    고령65=('pop65', 'sum'),
    청소년13_18=('pop1318', 'sum')
).reset_index()
t.to_csv(output_dir / '유형별_요약.csv', index=False, encoding='utf-8-sig')
sensitivity_summary = {}
for t1, t2 in [(45, 30), (90, 30), (60, 20), (60, 40)]:
    tt = pd.Series([
        classify_type(a, b, c, d, t1, t2) for (a, b, c, d) in zip(midday_minutes, evening_change, midday_capped, evening_capped)
    ]).value_counts()
    sensitivity_summary[f'{t1}/{t2}'] = dict(tt)
area_types['저녁공백'] = area_types['유형'].isin(['A 저녁 단절형', 'B 저녁 악화형', 'C 상시 취약·저녁 악화형'])
area_types['저녁단절'] = area_types['유형'].eq('A 저녁 단절형')
s = area_types.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).apply(lambda x: pd.Series({
    '읍면동': len(x),
    '저녁공백_읍면동': int(x['저녁공백'].sum()),
    '저녁단절_읍면동': int(x['저녁단절'].sum()),
    '인구': x['pop'].sum(),
    '고령65': x['pop65'].sum(),
    '저녁공백_고령65': x.loc[x['저녁공백'], 'pop65'].sum(),
    '저녁공백_청소년': x.loc[x['저녁공백'], 'pop1318'].sum(),
    '저녁공백_인구': x.loc[x['저녁공백'], 'pop'].sum(),
    '낮_병의원_가중': np.average(x['mid_병·의원'].fillna(120), weights=x['pop'].fillna(0) + 1e-09),
    '일평균_병의원_가중': np.average(x['all_병·의원'].fillna(120), weights=x['pop'].fillna(0) + 1e-09),
    '저녁_병의원_가중': np.average(x['eve_병·의원'].fillna(120), weights=x['pop'].fillna(0) + 1e-09)
})).reset_index()
s['저녁공백_고령비율'] = s['저녁공백_고령65'] / s['고령65']
s['저녁가중악화'] = s['저녁_병의원_가중'] - s['낮_병의원_가중']
s.to_csv(output_dir / '시군구_저녁공백.csv', index=False, encoding='utf-8-sig')
top_day = set(s.nlargest(50, '일평균_병의원_가중').HDCD_SGG_NM + '|' + s.nlargest(50, '일평균_병의원_가중').HDCD_SD_NM)
s2 = s.sort_values('저녁공백_고령65', ascending=False).head(50)
top_eve = set(s2.HDCD_SGG_NM + '|' + s2.HDCD_SD_NM)
s['일평균50'] = (s.HDCD_SGG_NM + '|' + s.HDCD_SD_NM).isin(top_day)
s['저녁50'] = (s.HDCD_SGG_NM + '|' + s.HDCD_SD_NM).isin(top_eve)
s.to_csv(output_dir / '시군구_저녁공백.csv', index=False, encoding='utf-8-sig')
print(
    '유형별 읍면동',
    t.set_index('유형')['읍면동'].to_dict(),
    '경계 미결합',
    int(boundary_matches.adm_cd2.isna().sum()),
    '인구 결합',
    int(area_types['pop'].notna().sum())
)
print('문턱별 유형', sensitivity_summary, '우선50 겹침', len(top_day & top_eve))
