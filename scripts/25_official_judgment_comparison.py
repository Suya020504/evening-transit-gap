"""정부 최소서비스 판정의 시·군별 확보지역 비율과 저녁 악화 비율을 비교한다.
입력은 2025 대중교통 현황조사 「대중교통 시설 및 수단」 PDF의 표 3-24(DRT 반영 전후, 법정구역)와 읍면동_최종판정.csv다.
출력은 데이터/가공/통합의 공식판정_비교.csv와 공식판정_비교.json이다.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pymupdf
from scipy.stats import spearmanr

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
SRC = ROOT / '데이터' / '원천_PC다운로드' / '대중교통현황조사_PTC'
OUT = ROOT / '데이터' / '가공' / '통합'
pdf = next(p for p in sorted(SRC.glob('*대중교통 시설 및 수단*.pdf')) if '(2' not in p.name)  # 2025년판(파일명에 연도 괄호 없음)


def read_table(path):
    """표 3-24의 행을 단어 좌표로 읽는다. 시군구 이름이 비어 있는 행은 건너뛴다."""
    doc = pymupdf.open(path)
    pages = [i for i, p in enumerate(doc) if 'DRT 운행 반영 전후 시' in p.get_text() and '종합지표 분석 결과(법정구역)' in p.get_text()]
    rows = []
    for i in pages:
        lines = {}
        for w in doc[i].get_text('words'):
            lines.setdefault(round((w[1] + w[3]) / 6), []).append(w)
        for key in sorted(lines):
            toks = [w[4] for w in sorted(lines[key], key=lambda w: w[0])]
            if len(toks) >= 7 and toks[0].isdigit() and toks[-1].endswith('%') and toks[-3].endswith('%'):
                rows.append({'순번': int(toks[0]), '시도': toks[1], '시군구': ' '.join(toks[2:-4]),
                             '확보비율_DRT반영전': float(toks[-3].rstrip('%')), '확보비율_DRT반영후': float(toks[-1].rstrip('%'))})
    return pd.DataFrame(rows).drop_duplicates('순번'), [i + 1 for i in pages]


official, pages = read_table(pdf)
d = pd.read_csv(OUT / '읍면동_최종판정.csv', dtype={'HDCD': str})
valid = d.dropna(subset=['mid_병·의원', 'eve_병·의원']).copy()
valid['저녁악화'] = valid['유형'].astype(str).str[0].isin(['A', 'B', 'C'])
valid['두지표일치'] = valid['최종판정'].eq('1 두 지표 일치')
ours = valid.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).agg(
    읍면동수=('HDCD', 'size'), 저녁악화비율=('저녁악화', 'mean'), 두지표일치=('두지표일치', 'sum'), 군=('군', 'max')).reset_index()
ours['key'] = ours['HDCD_SGG_NM'].str.replace(' ', '')
official['key'] = official['시군구'].str.replace(' ', '')
m = official.merge(ours, left_on=['시도', 'key'], right_on=['HDCD_SD_NM', 'key'], how='inner')
m['저녁악화비율'] = (m['저녁악화비율'] * 100).round(1)
m.drop(columns=['key', 'HDCD_SD_NM', 'HDCD_SGG_NM']).to_csv(OUT / '공식판정_비교.csv', index=False, encoding='utf-8-sig')

gun = m[m['군'].astype(bool)]
summary = {'자료': pdf.name, 'PDF쪽': pages, '표_시군수': int(len(official)), '결합_시군수': int(len(m)), '결합_군수': int(len(gun))}
rho = {}
for col, key in (('확보비율_DRT반영후', 'DRT반영후'), ('확보비율_DRT반영전', 'DRT반영전')):
    r = spearmanr(gun[col], gun['저녁악화비율'])
    rho[key] = float(r.correlation)
    summary[f'군_순위상관_{key}'] = {'rho': round(float(r.correlation), 3), 'p': round(float(r.pvalue), 3)}
# 같은 군을 복원추출(5,000회, 시드 고정)해 DRT 반영 전후 순위상관의 차이 구간을 구한다.
rng = np.random.default_rng(20261022)
X = gun[['확보비율_DRT반영후', '확보비율_DRT반영전', '저녁악화비율']].to_numpy()
diffs = []
for _ in range(5000):
    S = X[rng.integers(0, len(X), len(X))]
    after, before = spearmanr(S[:, 0], S[:, 2]).correlation, spearmanr(S[:, 1], S[:, 2]).correlation
    if not (np.isnan(after) or np.isnan(before)):
        diffs.append(after - before)
summary['군_순위상관_차이(반영후-반영전)'] = {'diff': round(rho['DRT반영후'] - rho['DRT반영전'], 3),
                                      'boot95': [round(float(np.percentile(diffs, q)), 3) for q in (2.5, 97.5)]}
bins = [('80% 이상', gun['확보비율_DRT반영후'] >= 80), ('70~80%', gun['확보비율_DRT반영후'].between(70, 80, inclusive='left')),
        ('70% 미만', gun['확보비율_DRT반영후'] < 70)]
summary['군_확보율구간'] = {name: {'군수': int(mask.sum()), '저녁악화비율_평균': round(float(gun.loc[mask, '저녁악화비율'].mean()), 1),
                                '두지표일치_읍면동': int(gun.loc[mask, '두지표일치'].sum())} for name, mask in bins}
json.dump(summary, open(OUT / '공식판정_비교.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False))
