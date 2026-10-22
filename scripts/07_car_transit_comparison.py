"""승용차 대비 대중교통 접근시간 배율과 막차 시각·저녁 악화율의 상관을 계산한다.
입력은 KTDB 평균접근시간 XLSX, 읍면동_최종판정.csv, 노선시간표·KTDB 집계 CSV다.
출력은 데이터/가공/통합의 막차_악화율_51.csv·보고서_추가지표.json과 fig/통합의 G5 PNG다.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parents[1]

matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
data_dir = ROOT / '데이터'
output_dir = data_dir / '가공' / '통합'
figure_dir = ROOT / 'fig' / '통합'
summary = {}
x = pd.read_excel(
    data_dir / '원천_PC다운로드' / 'KTDB_교통접근성지표_2025' / 'unzip' / '01_평균접근시간_2025.xlsx',
    sheet_name='평균접근시간',
    header=5,
    dtype={'HDCD': str}
)
x = x[(x.HDCD.astype(str).str.len() == 8) & x.FACI_NM.astype(str).str.contains('의원')]
tz = x.TIME_ZONE_NM.astype(str)
x = x[tz.str.contains('12') | tz.str.contains('18')].copy()
x['tz'] = np.where(x.TIME_ZONE_NM.astype(str).str.contains('18'), 'eve', 'mid')
x['md'] = np.where(x.MODE.astype(str).str.contains('PC'), 'car', 'pt')
v = x['평균접근시간(분)'].astype(str).str.strip()
x['cap'] = v.str.startswith('>')
x['val'] = pd.to_numeric(v.str.replace('>', '', regex=False), errors='coerce')
p = x.pivot_table(index='HDCD', columns=['md', 'tz'], values='val', aggfunc='first')
p.columns = [f'{a}_{b}' for a, b in p.columns]
p = p.reset_index()
summary['병의원_시설명'] = sorted(x.FACI_NM.astype(str).unique().tolist())
d = pd.read_csv(output_dir / '읍면동_최종판정.csv', dtype={'HDCD': str})
m = d.merge(p, on='HDCD', how='left')

def summarize_ratios(s):
    s = s.dropna(subset=['pt_mid', 'pt_eve', 'car_mid', 'car_eve'])
    return {
        'n': int(len(s)),
        '승용차_낮_중앙': float(s.car_mid.median()),
        '승용차_저녁_중앙': float(s.car_eve.median()),
        '대중교통_낮_중앙': float(s.pt_mid.median()),
        '대중교통_저녁_중앙': float(s.pt_eve.median()),
        '배율_낮_중앙': float((s.pt_mid / s.car_mid).median()),
        '배율_저녁_중앙': float((s.pt_eve / s.car_eve).median()),
        '저녁_대중교통60초과_승용차30이내_비율': float(((s.pt_eve > 60) & (s.car_eve <= 30)).mean()),
        '낮_대중교통60초과_승용차30이내_비율': float(((s.pt_mid > 60) & (s.car_mid <= 30)).mean())
    }

summary['배율'] = {
    '두지표일치151': summarize_ratios(m[m['최종판정'].str.startswith('1')]),
    '군_전체': summarize_ratios(m[m['군'] == True]),
    '시구_전체': summarize_ratios(m[m['군'] != True])
}
t = pd.read_csv(data_dir / '가공' / '노선시간표_지자체요약.csv', encoding='utf-8-sig')
# 수록률이 낮은 칠곡을 제외하고 군청 시간표로 확인한 세 군의 막차를 반영한다.
t = t[t['지자체명'] != '칠곡군'].copy()
fix = {'의령군': '21:10', '장흥군': '20:30', '산청군': '19:40'}
t['최종'] = [fix.get(a, b) for a, b in zip(t['지자체명'], t['최종출발'])]
t['분'] = [int(s.split(':')[0]) * 60 + int(s.split(':')[1]) for s in t['최종']]
k = pd.read_csv(data_dir / '가공' / 'KTDB_저녁낮_읍면동.csv', dtype={'HDCD': str})
k = k[k.FACI_NM == '병·의원'].dropna(subset=['mid', 'eve'])
k = k[~((k.HDCD_SGG_NM == '고성군') & ~k.HDCD_SD_NM.astype(str).str.contains('경상남도|경남'))]
k['worse'] = k.eve - k.mid > 10
g = k.groupby('HDCD_SGG_NM').agg(n=('worse', 'size'), w=('worse', 'sum')).reset_index()
s = t.merge(g, left_on='지자체명', right_on='HDCD_SGG_NM', how='left')
s['rate'] = s.w / s.n * 100
rho = spearmanr(s['분'], s['rate']).correlation
# 재표집 결과를 재현하도록 난수 시드를 고정한다.
rng = np.random.default_rng(20261022)
bootstrap_correlations = []
for _ in range(2000):
    ix = rng.integers(0, len(s), len(s))
    r = spearmanr(s['분'].values[ix], s['rate'].values[ix]).correlation
    if not np.isnan(r):
        bootstrap_correlations.append(r)
summary['막차_산점도'] = {
    'n': int(len(s)),
    'rho': float(rho),
    'ci95': [
        float(np.percentile(bootstrap_correlations, 2.5)),
        float(np.percentile(bootstrap_correlations, 97.5))
    ],
    '20시전_집단': {
        '지자체': int((s['분'] < 1200).sum()),
        '악화': int(s[s['분'] < 1200].w.sum()),
        '유효': int(s[s['분'] < 1200].n.sum())
    }
}
s.to_csv(output_dir / '막차_악화율_51.csv', index=False, encoding='utf-8-sig')
fig, ax = plt.subplots(figsize=(7.2, 3.9))
city = s['지자체명'].str.endswith('시')
ax.axvspan(18 * 60 + 30, 20 * 60, color='#fdecea', zorder=0)
ax.text(18 * 60 + 35, 96, '20시 이후 출발 기록 없음(10곳)', fontsize=9.5, color='#a93226', va='top')
ax.scatter(
    s.loc[~city, '분'],
    s.loc[~city, 'rate'],
    s=s.loc[~city, 'n'] * 4 + 12,
    c='#c0392b',
    alpha=0.75,
    edgecolors='white',
    linewidths=0.6,
    label='군',
    zorder=3
)
ax.scatter(
    s.loc[city, '분'],
    s.loc[city, 'rate'],
    s=s.loc[city, 'n'] * 4 + 12,
    c='#2e86ab',
    alpha=0.8,
    edgecolors='white',
    linewidths=0.6,
    label='시',
    zorder=3
)
label_offsets = {
    '합천군': (5, 4),
    '무주군': (5, 4),
    '해남군': (6, 2),
    '거창군': (-30, -2),
    '진도군': (5, 3),
    '당진시': (-6, 7),
    '통영시': (-16, -13),
    '의령군': (5, 4),
    '울릉군': (5, 3),
    '창녕군': (5, 4)
}
for nm, off in label_offsets.items():
    r = s[s['지자체명'] == nm]
    if len(r):
        ax.annotate(
            nm[:-1],
            (r['분'].iloc[0], r['rate'].iloc[0]),
            xytext=off,
            textcoords='offset points',
            fontsize=10
        )
ax.set_xticks(range(19 * 60, 24 * 60, 60), [f'{h}:00' for h in range(19, 24)])
ax.set_xlim(18 * 60 + 30, 23 * 60 + 40)
ax.set_ylim(-4, 100)
ax.set_xlabel('등록 시간표상 평일 마지막 출발 시각(노선 양끝 기준, 2026년 7월 파일 + 군청 시간표 보정)', fontsize=9.5)
ax.set_ylabel('저녁에 병·의원 접근이\n10분 넘게 나빠진 읍면동(%)', fontsize=10)
ax.spines[['top', 'right']].set_visible(False)
ax.legend(frameon=False, fontsize=10, loc='upper right')
ax.set_title(f'막차가 이른 시·군일수록 저녁 접근성이 더 나빠진다 (51개 시·군, 스피어만 ρ = {rho:.2f})', fontsize=11.5, loc='left')
fig.text(
    0.01,
    -0.02,
    '[계산] 한국교통안전공단 버스 노선·시간표(2026-07) × KTDB 교통접근성지표 2025(낮 12~14시 대 저녁 18~20시). 점 크기 = 읍면동 수. 칠곡(시간표 수록 4/96)은 제외. 상관이며 인과가 아님.',
    fontsize=8.3,
    color='#444'
)
fig.savefig(figure_dir / 'G5_막차_악화율.png', dpi=220, bbox_inches='tight')
plt.close(fig)
json.dump(
    summary,
    open(output_dir / '보고서_추가지표.json', 'w', encoding='utf-8'),
    ensure_ascii=False,
    indent=1
)
print('접근시간 배율', summary['배율'])
print('막차·악화율', summary['막차_산점도'], '그림 G5 저장 완료')
