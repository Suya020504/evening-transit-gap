"""세 시간대 기준선의 연결 상실 하한을 계산하고 평균 접근성 유형과 결합한다.
입력은 KTDB의 02_*.xlsx와 데이터/가공/기획/읍면동_저녁유형.csv다.
출력은 데이터/가공/통합의 읍면동_통합판정.csv, 시군구_통합판정.csv, 통합지표_요약.json이다.
"""
from pathlib import Path
import pandas as pd
import glob
import json
import os

ROOT = Path(__file__).resolve().parents[1]

output_dir = ROOT / '데이터' / '가공' / '통합'
os.makedirs(output_dir, exist_ok=True)
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

# 공표 비율의 반올림 오차를 고려해 하한에서 0.015%p를 뺀다.
cols = {}
for base_nm, tz in [('mid', '2_T1214'), ('am', '1_T0709'), ('all', '0_ALLDAY')]:
    for fac, fn in [('22', 'clinic'), ('41', 'term')]:
        baseline_transit = accessibility_ratio(fac, '2_PT', tz, 'r60')
        evening_transit = accessibility_ratio(fac, '2_PT', '3_T1820', 'r60')
        evening_car = accessibility_ratio(fac, '1_PC', '3_T1820', 'r30')
        cols[f'lb_{base_nm}_{fn}'] = (baseline_transit + evening_car - evening_transit - 100 - 0.015).clip(lower=0)
for base_nm, tz in [('mid', '2_T1214')]:
    baseline_transit = accessibility_ratio('13', '2_PT', tz, 'r60')
    evening_transit = accessibility_ratio('13', '2_PT', '3_T1820', 'r60')
    evening_car = accessibility_ratio('13', '1_PC', '3_T1820', 'r30')
    cols['lb_mid_hs'] = (baseline_transit + evening_car - evening_transit - 100 - 0.015).clip(lower=0)
bounds = pd.DataFrame(cols)
for b in ['mid', 'am', 'all']:
    bounds[f'lb_{b}'] = bounds[[f'lb_{b}_clinic', f'lb_{b}_term']].max(axis=1, skipna=False)
bounds['n_base20'] = sum(((bounds[f'lb_{b}'] >= 20).astype(int) for b in ['mid', 'am', 'all']))
t = pd.read_csv(ROOT / '데이터' / '가공' / '기획' / '읍면동_저녁유형.csv', dtype={'HDCD': str}).set_index('HDCD')
assessment = t[[
    'HDCD_SD_NM',
    'HDCD_SGG_NM',
    'HDCD_EMD_NM',
    'pop',
    'pop65',
    'pop1318',
    '유형',
    'd_병의원',
    '군'
]].join(bounds, how='left')
assessment['ABC'] = assessment['유형'].astype(str).str[0].isin(list('ABC'))
assessment['robust2'] = assessment.n_base20 >= 2
assessment['all3'] = assessment.n_base20 == 3

def classify_robustness(r):
    if r.ABC and r.robust2:
        return '1 저녁 우선(두 방법 모두)'
    if r.robust2:
        return '2 하한만(평균은 양호·상시취약)'
    if r.ABC:
        return '3 평균만(하한 미확인)'
    return '4 해당 없음'

assessment['통합판정'] = assessment.apply(classify_robustness, axis=1)
summary = {}
for b in ['mid', 'am', 'all']:
    s = assessment[f'lb_{b}'] >= 20
    summary[f'n20_{b}'] = int(s.sum())
    summary[f'n20_{b}_gun'] = int((s & (assessment.군 == 1)).sum())
    summary[f'lb65_{b}'] = int((assessment[f'lb_{b}'].fillna(0) / 100 * assessment.pop65).sum())
    summary[f'lb65_{b}_clinic'] = int((assessment[f'lb_{b}_clinic'].fillna(0) / 100 * assessment.pop65).sum())
summary['n_all3'] = int(assessment.all3.sum())
summary['n_robust2'] = int(assessment.robust2.sum())
summary['hs_lb1318_mid'] = int((assessment['lb_mid_hs'].fillna(0) / 100 * assessment.pop1318).sum())
assessment['lb65_mid'] = assessment.lb_mid.fillna(0) / 100 * assessment.pop65
assessment['우선'] = assessment['통합판정'].str.startswith('1')
sg = assessment.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).agg(
    우선읍면동=('우선', 'sum'),
    우선_65=('pop65', lambda s: s[assessment.loc[s.index, '우선']].sum()),
    하한65=('lb65_mid', 'sum'),
    군=('군', 'max')
).sort_values('우선_65', ascending=False)
sg['순위'] = range(1, len(sg) + 1)
assessment.to_csv(output_dir / '읍면동_통합판정.csv', encoding='utf-8-sig')
sg.to_csv(output_dir / '시군구_통합판정.csv', encoding='utf-8-sig')
json.dump(
    summary,
    open(output_dir / '통합지표_요약.json', 'w', encoding='utf-8'),
    ensure_ascii=False,
    indent=1
)
assessment['lb20'] = assessment.lb_mid >= 20

def classify_evidence(r):
    if r.ABC and r.lb20:
        return '1 확정: 정기 저녁편'
    if r.ABC:
        return '2 평균만: 저녁 호출형'
    if r.lb20:
        return '3 하한만: 마을 단위 호출형+자료 점검'
    return '4 관찰'

assessment['판정2'] = assessment.apply(classify_evidence, axis=1)
assessment['robust_any'] = (assessment.lb_am >= 20) | (assessment.lb_all >= 20)
c2 = assessment.groupby('판정2').agg(
    n=('pop', 'size'),
    군=('군', 'sum'),
    pop65=('pop65', 'sum'),
    pop1318=('pop1318', 'sum'),
    하한65=('lb65_mid', 'sum'),
    다른기준도20=('robust_any', 'sum')
)
lo = {
    '1 확정: 정기 저녁편': (11000000.0, 26000000.0),
    '2 평균만: 저녁 호출형': (18250000.0, 36500000.0),
    '3 하한만: 마을 단위 호출형+자료 점검': (18250000.0, 36500000.0)
}
tot_lo = sum((c2.loc[k, 'n'] * v[0] for k, v in lo.items()))
tot_hi = sum((c2.loc[k, 'n'] * v[1] for k, v in lo.items()))
assessment['확정'] = assessment['판정2'].str.startswith('1')
sg2 = assessment.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).agg(
    확정=('확정', 'sum'),
    평균만=('판정2', lambda s: int(s.str.startswith('2').sum())),
    하한만=('판정2', lambda s: int(s.str.startswith('3').sum())),
    확정_65=('pop65', lambda s: s[assessment.loc[s.index, '확정']].sum()),
    하한65=('lb65_mid', 'sum'),
    군=('군', 'max')
)
sg2['저녁공백65'] = assessment[assessment.ABC].groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).pop65.sum()
sg2 = sg2.fillna(0).sort_values(['하한65'], ascending=False)
sg2['하한순위'] = range(1, len(sg2) + 1)
sg2 = sg2.sort_values('저녁공백65', ascending=False)
sg2['평균순위'] = range(1, len(sg2) + 1)
both50 = sg2[(sg2.하한순위 <= 50) & (sg2.평균순위 <= 50)]
assessment.to_csv(output_dir / '읍면동_통합판정.csv', encoding='utf-8-sig')
sg2.to_csv(output_dir / '시군구_통합판정.csv', encoding='utf-8-sig')
print('기준선별 하한 집계', summary)
print(
    '판정별 읍면동',
    c2['n'].to_dict(),
    '두 순위 모두 50위 안',
    len(both50),
    '전국 연비용(억)',
    round(tot_lo / 100000000.0, 1),
    round(tot_hi / 100000000.0, 1)
)
