"""시간대에 따른 우선지역 선정 변화와 최종 판정별 청소년 인구를 계산한다.
입력은 KTDB의 01_평균접근시간_2025.xlsx와 읍면동_최종판정.csv다.
출력은 데이터/가공/통합/보고서_추가지표2.json이다.
"""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

data_dir = ROOT / '데이터'
output_dir = data_dir / '가공' / '통합'
x = pd.read_excel(
    data_dir / '원천_PC다운로드' / 'KTDB_교통접근성지표_2025' / 'unzip' / '01_평균접근시간_2025.xlsx',
    sheet_name='평균접근시간',
    header=5,
    dtype={'HDCD': str}
)
x = x[(x.HDCD.astype(str).str.len() == 8) & (x.FACI_NM.astype(str) == '병·의원') & x.MODE.astype(str).str.contains('PT')].copy()
v = x['평균접근시간(분)'].astype(str).str.strip()
x['val'] = pd.to_numeric(v.str.replace('>', '', regex=False), errors='coerce')
p = x.pivot_table(index='HDCD', columns='TIME_ZONE_NM', values='val', aggfunc='first')
cols = {c: 'all' if '일평균' in c else 'am' if '오전' in c else 'mid' if '낮' in c else 'eve' for c in p.columns}
p = p.rename(columns=cols).dropna()
summary = {'n': int(len(p))}

def worst_time_areas(col):
    th = p[col].quantile(0.9)
    return (set(p.index[p[col] >= th]), float(th))

base, th0 = worst_time_areas('all')
for c in ['mid', 'am', 'eve']:
    s, th = worst_time_areas(c)
    summary[f'일평균_vs_{c}'] = {
        '일평균집합': len(base),
        '비교집합': len(s),
        '겹침': len(base & s),
        '일평균에서빠짐': len(base - s),
        '비율': round(len(base - s) / len(base) * 100, 1),
        '문턱': th
    }
d = pd.read_csv(output_dir / '읍면동_최종판정.csv', dtype={'HDCD': str})
summary['1318'] = d.groupby('최종판정')['pop1318'].sum().round(0).to_dict()
json.dump(
    summary,
    open(output_dir / '보고서_추가지표2.json', 'w', encoding='utf-8'),
    ensure_ascii=False,
    indent=1,
    default=float
)
print('시간대별 선정 변화·청소년 인구', summary)
