"""최종 판정과 시군 순위, 인구 환산, 비용·탄소 시나리오를 계산한다.
입력은 읍면동_통합판정.csv, 읍면동_저녁유형.csv, 행정동 경계 GeoJSON이다.
출력은 데이터/가공/통합의 최종 판정·순위 CSV와 최종지표.json, fig/통합의 G1~G4 PNG다.
"""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
from matplotlib.collections import PolyCollection
from matplotlib.patches import Patch, FancyBboxPatch, FancyArrowPatch

ROOT = Path(__file__).resolve().parents[1]

matplotlib.use('Agg')
import matplotlib.pyplot as plt
plt.rcParams['font.family'] = 'Malgun Gothic'
plt.rcParams['axes.unicode_minus'] = False
output_dir = ROOT / '데이터' / '가공' / '통합'
figure_dir = ROOT / 'fig' / '통합'
figure_dir.mkdir(parents=True, exist_ok=True)
BUS_LO, BUS_HI = (11000000.0, 26000000.0)
CALL_LO_N, CALL_HI_N, CALL_FARE = (3, 10, 10000.0)
DAYS_YEAR = 365
# 합천의 운행일·기록비·예비비는 비용 시나리오의 가정이다.
HC_DAY = 693030.8
HC_DAYS = 125
HC_REC = 3000000.0
HC_MARGIN = 1.2
HC_CALL_UNITS = ['초계면', '봉산면', '묘산면', '율곡면', '가회면', '대병면', '용주면']
BUS_KM_DAY, BUS_G = (30, 723)
TAXI_VKM_TRIP, TAXI_G = (20, 183)
assessment = pd.read_csv(output_dir / '읍면동_통합판정.csv', dtype={'HDCD': str})
valid = assessment['mid_병·의원'].notna() & assessment['eve_병·의원'].notna()
midday_capped = assessment['cap_mid_병·의원'].astype(bool)
evening_capped = assessment['cap_eve_병·의원'].astype(bool)
mid = assessment['mid_병·의원']
# 저녁만 상한이면 120-낮 값으로 10분 초과 악화를 확정할 수 있는지 나눈다.
one_side = valid & evening_capped & ~midday_capped & (mid > 60)
reclassify_c = one_side & (120 - mid >= 10) & assessment['유형'].astype(str).str.startswith('D')
ambiguous_change = one_side & (120 - mid < 10)
assessment.loc[reclassify_c, '유형'] = 'C 상시 취약·저녁 악화형'
NAME = {'A': 'A 저녁 급악화', 'B': 'B 저녁 악화', 'C': 'C 낮부터 원거리·저녁 악화', 'D': 'D 낮부터 원거리', 'E': 'E 기준 미해당'}
assessment['유형'] = [NAME.get(str(x)[0], '자료 없음') for x in assessment['유형']]
abc = assessment['유형'].astype(str).str[0].isin(list('ABC'))
lb20 = assessment['lb_mid'] >= 20
both_cap = valid & midday_capped & evening_capped
undecided = both_cap | ambiguous_change
assessment['평균판정유보'] = np.where(
    both_cap,
    '낮·저녁 모두 120분 초과',
    np.where(ambiguous_change, '저녁만 120분 초과(악화폭 10분 초과 여부 불명)', '')
)

def classify_final(i):
    if not valid[i]:
        return '6 자료 없음'
    if abc[i] and lb20[i]:
        return '1 두 지표 일치'
    if abc[i]:
        return '2 평균만'
    if lb20[i]:
        return '3 하한만'
    if undecided[i]:
        return '4 평균 변화 판정 불가'
    return '5 관찰'

assessment['최종판정'] = [classify_final(i) for i in assessment.index]
assessment['하한결정시설'] = np.where(
    assessment['lb_mid_clinic'].fillna(0) >= 20,
    '병·의원',
    np.where(assessment['lb_mid_term'].fillna(0) >= 20, '터미널만', '')
)
assessment['기준선유지수'] = assessment['n_base20'].fillna(0).astype(int)
summary = {}
g = assessment.groupby('최종판정').agg(
    n=('HDCD', 'size'),
    군=('군', 'sum'),
    인구결합=('pop', lambda s: int(s.notna().sum())),
    pop=('pop', 'sum'),
    pop65=('pop65', 'sum'),
    pop1318=('pop1318', 'sum')
)
summary['분류'] = {
    k: {c: int(v) if pd.notna(v) else None for c, v in row.items()} for (k, row) in g.iterrows()
}
m1 = assessment['최종판정'].str.startswith('1')
summary['일치151'] = {
    'n': int(m1.sum()),
    '다른기준선1개이상': int((m1 & (assessment.기준선유지수 >= 2)).sum()),
    '세기준모두': int((m1 & (assessment.기준선유지수 == 3)).sum()),
    '낮기준만': int((m1 & (assessment.기준선유지수 == 1)).sum()),
    '터미널하한만': int((m1 & (assessment.하한결정시설 == '터미널만')).sum())
}

def population_from_bound(col):
    return int((assessment[col].fillna(0) / 100 * assessment['pop'].fillna(0)).sum())

summary['노출65'] = {
    '낮60': int(assessment.loc[valid & (assessment['mid_병·의원'] > 60), 'pop65'].sum()),
    '저녁60': int(assessment.loc[valid & (assessment['eve_병·의원'] > 60), 'pop65'].sum()),
    '낮90': int(assessment.loc[valid & (assessment['mid_병·의원'] > 90), 'pop65'].sum()),
    '저녁90': int(assessment.loc[valid & (assessment['eve_병·의원'] > 90), 'pop65'].sum())
}
summary['하한인원_전체'] = {b: {
    '병의원': population_from_bound(f'lb_{b}_clinic'),
    '병의원또는터미널': population_from_bound(f'lb_{b}')
} for b in ['mid', 'am', 'all']}
summary['일치151_주민'] = {
    'pop': int(assessment.loc[m1, 'pop'].sum()),
    '하한인원': int((assessment.loc[m1, 'lb_mid'] / 100 * assessment.loc[m1, 'pop']).sum()),
    'pop65': int(assessment.loc[m1, 'pop65'].sum())
}
# 하한에 고령 인구를 곱한 값은 지역 순위를 위한 가중 지표다.
assessment['고령가중공백'] = assessment['lb_mid'].fillna(0) / 100 * assessment['pop65'].fillna(0)
sg = assessment.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).agg(
    일치=('최종판정', lambda s: int(s.str.startswith('1').sum())),
    평균만=('최종판정', lambda s: int(s.str.startswith('2').sum())),
    하한만=('최종판정', lambda s: int(s.str.startswith('3').sum())),
    고령가중공백=('고령가중공백', 'sum'),
    군=('군', 'max')
)
sg['ABC65'] = assessment[abc].groupby(['HDCD_SD_NM', 'HDCD_SGG_NM']).pop65.sum()
sg = sg.fillna(0)
sg['순위_ABC65'] = sg['ABC65'].rank(ascending=False, method='first').astype(int)
sg['순위_고령가중'] = sg['고령가중공백'].rank(ascending=False, method='first').astype(int)
p32 = sg[(sg.순위_ABC65 <= 50) & (sg.순위_고령가중 <= 50)].copy()
summary['우선32'] = {
    'n': len(p32),
    '군': int(p32.군.sum()),
    '일치': int(p32.일치.sum()),
    '평균만': int(p32.평균만.sum()),
    '하한만': int(p32.하한만.sum())
}
call_lo, call_hi = (CALL_LO_N * CALL_FARE * DAYS_YEAR, CALL_HI_N * CALL_FARE * DAYS_YEAR)
n1 = summary['분류']['1 두 지표 일치']['n']
n2 = summary['분류']['2 평균만']['n'] + summary['분류']['3 하한만']['n']
summary['비용_전국'] = {
    '1단계': [n1 * BUS_LO / 100000000.0, n1 * BUS_HI / 100000000.0],
    '2단계': [n2 * call_lo / 100000000.0, n2 * call_hi / 100000000.0]
}
summary['비용_전국']['합'] = [
    summary['비용_전국']['1단계'][0] + summary['비용_전국']['2단계'][0],
    summary['비용_전국']['1단계'][1] + summary['비용_전국']['2단계'][1]
]
a, b2 = (summary['우선32']['일치'], summary['우선32']['평균만'] + summary['우선32']['하한만'])
summary['비용_우선32'] = {
    '1단계': [a * BUS_LO / 100000000.0, a * BUS_HI / 100000000.0],
    '2단계': [b2 * call_lo / 100000000.0, b2 * call_hi / 100000000.0]
}
summary['비용_우선32']['합'] = [
    summary['비용_우선32']['1단계'][0] + summary['비용_우선32']['2단계'][0],
    summary['비용_우선32']['1단계'][1] + summary['비용_우선32']['2단계'][1]
]
hc3 = (HC_DAY * HC_DAYS + HC_REC) * HC_MARGIN
hc_call_year = [len(HC_CALL_UNITS) * call_lo, len(HC_CALL_UNITS) * call_hi]
hc_call_6m = [x / 2 for x in hc_call_year]
summary['비용_합천'] = {
    '3축_6개월': hc3 / 100000000.0,
    '3축_60일': (HC_DAY * 60 + HC_REC) * HC_MARGIN / 100000000.0,
    '3축_매일184일': (HC_DAY * 184 + HC_REC) * HC_MARGIN / 100000000.0,
    '호출형_7개면_연': [x / 100000000.0 for x in hc_call_year],
    '호출형_7개면_6개월': [x / 100000000.0 for x in hc_call_6m],
    '시범_6개월_합': [(hc3 + hc_call_6m[0]) / 100000000.0, (hc3 + hc_call_6m[1]) / 100000000.0],
    '60일_민감도_기록비고정': [
        ((300 * 0.8 * 766.76 + 16 * 20000) * 1.1 * 60 + HC_REC) * 1.2 / 10000.0,
        ((300 * 1.2 * 766.76 + 16 * 30000) * 1.1 * 60 + HC_REC) * 1.2 / 10000.0
    ]
}
summary['손익분기_택시운행건'] = [BUS_LO / (CALL_FARE * DAYS_YEAR), BUS_HI / (CALL_FARE * DAYS_YEAR)]
bus_t = BUS_KM_DAY * BUS_G * DAYS_YEAR / 1000000.0
taxi_t10 = CALL_HI_N * TAXI_VKM_TRIP * TAXI_G * DAYS_YEAR / 1000000.0
taxi_t3 = CALL_LO_N * TAXI_VKM_TRIP * TAXI_G * DAYS_YEAR / 1000000.0
summary['탄소'] = {
    '버스1곳': bus_t,
    '호출1곳_10건': taxi_t10,
    '호출1곳_3건': taxi_t3,
    '전국_1단계': n1 * bus_t,
    '전국_2단계_10건': n2 * taxi_t10,
    '전국_2단계_3건': n2 * taxi_t3
}
summary['판정유보_내역'] = {
    '양쪽상한': int(both_cap.sum()),
    '저녁만상한_불명': int(ambiguous_change.sum()),
    '저녁만상한_C재판정': int(reclassify_c.sum())
}
public_columns = [
    'HDCD',
    'HDCD_SD_NM',
    'HDCD_SGG_NM',
    'HDCD_EMD_NM',
    'adm_cd2',
    '군',
    'pop',
    'pop65',
    'pop1318',
    'mid_병·의원',
    'eve_병·의원',
    'cap_mid_병·의원',
    'cap_eve_병·의원',
    '유형',
    '평균판정유보',
    'lb_mid_clinic',
    'lb_mid_term',
    'lb_mid',
    'lb_am',
    'lb_all',
    '기준선유지수',
    '하한결정시설',
    '최종판정',
    '고령가중공백'
]
assessment[[c for c in public_columns if c in assessment.columns]].to_csv(
    output_dir / '읍면동_최종판정.csv',
    index=False,
    encoding='utf-8-sig'
)
sg.reset_index().to_csv(output_dir / '시군_최종순위.csv', index=False, encoding='utf-8-sig')
p32.reset_index().to_csv(output_dir / '우선32_v1.csv', index=False, encoding='utf-8-sig')
json.dump(
    summary,
    open(output_dir / '최종지표.json', 'w', encoding='utf-8'),
    ensure_ascii=False,
    indent=1,
    default=float
)
category_colors = {
    '1 두 지표 일치': '#c0392b',
    '2 평균만': '#f39c5a',
    '3 하한만': '#2e86ab',
    '4 평균 변화 판정 불가': '#8e7cc3',
    '5 관찰': '#eaeef2',
    '6 자료 없음': '#ffffff',
    '7 경계 미대응': '#bfc5cc'
}
category_labels = {
    '1 두 지표 일치': f"두 지표 일치 — 평균 악화 + 하한 20% 이상 ({summary['분류']['1 두 지표 일치']['n']}곳)",
    '2 평균만': f"평균만 — 평균 접근시간만 저녁에 악화 ({summary['분류']['2 평균만']['n']}곳)",
    '3 하한만': f"하한만 — 일부 주민의 연결 상실만 확인 ({summary['분류']['3 하한만']['n']}곳)",
    '4 평균 변화 판정 불가': f"평균 변화 판정 불가 — 120분 상한으로 악화폭 불명 ({summary['분류']['4 평균 변화 판정 불가']['n']}곳)",
    '5 관찰': '관찰',
    '6 자료 없음': '자료 없음 (흰색, 테두리)',
    '7 경계 미대응': '경계 미대응 — 판정 자료와 연결 안 된 행정동'
}
t = pd.read_csv(ROOT / '데이터' / '가공' / '기획' / '읍면동_저녁유형.csv', dtype={'HDCD': str, 'adm_cd2': str})
key = assessment.merge(t[['HDCD', 'adm_cd2']], on='HDCD', how='left', suffixes=('', '_t'))
kcol = 'adm_cd2_t' if 'adm_cd2_t' in key else 'adm_cd2'
cmap = dict(zip(key[kcol].astype(str).str.replace(r'\.0$', '', regex=True), key['최종판정']))
gj = json.load(open(
    ROOT / '데이터' / '원천_PC다운로드' / '행정동경계_admdongkor' / 'HangJeongDong_ver20261001.geojson',
    encoding='utf-8'
))
FOCUS = {'합천군', '산청군', '하동군', '거창군', '의령군', '창녕군', '해남군', '진도군', '장흥군', '강진군', '완도군'}
polys, cols, sgg, cats = ([], [], [], [])
summary['경계미대응'] = sum((1 for f in gj['features'] if f['properties']['adm_cd2'] not in cmap))
json.dump(
    summary,
    open(output_dir / '최종지표.json', 'w', encoding='utf-8'),
    ensure_ascii=False,
    indent=1,
    default=float
)
for f in gj['features']:
    c = cmap.get(f['properties']['adm_cd2'], '7 경계 미대응')
    geom = f['geometry']
    parts = geom['coordinates'] if geom['type'] == 'MultiPolygon' else [geom['coordinates']]
    for poly in parts:
        polys.append(np.array(poly[0]))
        cols.append(category_colors[c])
        sgg.append(f['properties']['sggnm'])
        cats.append(c)

def draw(ax, xlim, ylim, lw, focus=False):
    ec = [
        '#222222' if focus and s in FOCUS else '#999999' if c == '6 자료 없음' else '#ffffff' for (s, c) in zip(sgg, cats)
    ]
    ax.add_collection(PolyCollection(polys, facecolors=cols, edgecolors=ec, linewidths=lw))
    ax.set_aspect(1.2)
    ax.axis('off')
    ax.set_xlim(xlim)
    ax.set_ylim(ylim)

fig = plt.figure(figsize=(12, 9.6))
ax = fig.add_axes([0.0, 0.0, 0.58, 0.93])
draw(ax, (125.0, 131.0), (33.1, 38.65), 0.05)
ax.add_patch(plt.Rectangle((127.55, 34.85), 1.2, 1.1, fill=False, ec='#333', lw=1))
ax.add_patch(plt.Rectangle((126.0, 34.15), 1.15, 0.8, fill=False, ec='#333', lw=1))
for nm, (x0, y0, x1, y1), pos in [
    ('경남 서부', (127.55, 34.85, 128.75, 35.95), [0.6, 0.5, 0.39, 0.42]),
    ('전남 서남부', (126.0, 34.15, 127.15, 34.95), [0.6, 0.04, 0.39, 0.42])
]:
    a2 = fig.add_axes(pos)
    draw(a2, (x0, x1), (y0, y1), 0.35, focus=True)
    a2.set_title(nm + ' 확대 (검은 테두리: 집계한 군)', fontsize=12.5, loc='left')
    cen = {}
    for pgn, s in zip(polys, sgg):
        c = pgn.mean(axis=0)
        if x0 < c[0] < x1 and y0 < c[1] < y1 and s.endswith('군'):
            cen.setdefault(s, []).append(c)
    for s, cs in cen.items():
        if len(cs) >= 4:
            c = np.mean(cs, axis=0)
            a2.text(
                c[0],
                c[1],
                s,
                fontsize=11.5,
                ha='center',
                va='center',
                weight='bold',
                bbox=dict(boxstyle='round,pad=0.12', fc='white', ec='none', alpha=0.75)
            )
fig.legend(
    handles=[Patch(
        facecolor=category_colors[k],
        edgecolor='#999999' if k == '6 자료 없음' else category_colors[k],
        label=category_labels[k]
    ) for k in category_colors],
    loc='upper center',
    bbox_to_anchor=(0.5, 0.0),
    ncol=2,
    fontsize=12.5,
    frameon=False
)
fig.suptitle(
    '저녁 대중교통 공백, 두 지표가 겹치는 곳 (KTDB 2025 병·의원·터미널, 낮 12~14시 대 저녁 18~20시)',
    x=0.02,
    ha='left',
    fontsize=15.5,
    y=0.99
)
fig.text(
    0.02,
    -0.2,
    '평균 지표: 병·의원 평균 접근시간이 저녁에 10분 넘게 나빠짐(유형 A·B·C). 하한 지표: 낮 대중교통 60분 안·저녁 60분 밖·저녁 승용차 30분 안인 모형 인구가 적어도 20%(병·의원 또는 터미널).\n자료 없음 4곳 중 철원 근동·원동·원남면은 행정동 경계에 대응하는 면이 없어 지도에 나타나지 않는다. 경계 미대응 ' + str(summary.get('경계미대응', '')) + '곳은 행정구역 개편 등으로 판정 자료와 연결되지 않은 행정동이다.',
    fontsize=10.5,
    color='#444'
)
fig.savefig(figure_dir / 'G1_전국_근거강도지도.png', dpi=200, bbox_inches='tight')
plt.close(fig)
fig, axs = plt.subplots(1, 2, figsize=(12, 4.8), gridspec_kw={'width_ratios': [1.1, 1]})
a1 = axs[0]
v = [summary['노출65']['낮60'] / 10000.0, summary['노출65']['저녁60'] / 10000.0]
bb = a1.bar(['낮 12~14시', '저녁 18~20시'], v, color=['#8fb8de', '#c0392b'], width=0.55)
for bar, x in zip(bb, v):
    a1.text(
        bar.get_x() + bar.get_width() / 2,
        x + 1.5,
        f'{x:.1f}만 명',
        ha='center',
        fontsize=12,
        weight='bold'
    )
a1.set_ylim(0, 105)
a1.set_yticks([])
a1.spines[['top', 'right', 'left']].set_visible(False)
a1.set_title('① 노출: 병·의원 평균 60분 넘는 읍면동에 사는 65세 이상', fontsize=11, loc='left')
a2 = axs[1]
rows = [
    (
        '병·의원',
        summary['하한인원_전체']['mid']['병의원'],
        summary['하한인원_전체']['all']['병의원'],
        summary['하한인원_전체']['am']['병의원']
    ),
    (
        '병·의원 또는\n버스터미널',
        summary['하한인원_전체']['mid']['병의원또는터미널'],
        summary['하한인원_전체']['all']['병의원또는터미널'],
        summary['하한인원_전체']['am']['병의원또는터미널']
    )
]
for i, (nm, m, lo, hi) in enumerate(rows):
    a2.barh(i, m / 10000.0, color=['#2e86ab', '#1b4f72'][i], height=0.5)
    a2.plot([lo / 10000.0, hi / 10000.0], [i, i], color='#333', lw=1.5)
    a2.plot([lo / 10000.0] * 2, [i - 0.12, i + 0.12], color='#333')
    a2.plot([hi / 10000.0] * 2, [i - 0.12, i + 0.12], color='#333')
    a2.text(
        hi / 10000.0 + 1.5,
        i,
        f'환산 약 {m / 10000.0:.1f}만 명',
        va='center',
        fontsize=12,
        weight='bold'
    )
a2.set_yticks([0, 1], [r[0] for r in rows])
a2.invert_yaxis()
a2.set_xlim(0, 105)
a2.set_xlabel('만 명 (막대: 낮 12~14시 기준, 선: 일평균~오전첨두 기준)')
a2.spines[['top', 'right']].set_visible(False)
a2.set_title('② 하한 비율의 인구 환산: 낮엔 버스 60분 안·저녁엔 밖·차로는 30분 안', fontsize=11, loc='left')
fig.text(
    0.01,
    -0.07,
    '[계산·추정] ① KTDB 2025에서 병·의원 평균접근시간이 60분을 넘는 읍면동을 고른 뒤, 그 지역의 2026년 9월 65세 이상 거주인구를 합산했다.\n② KTDB 2025 모형 인구의 하한 비율(프레셰 경계)을 2026년 9월 전체 주민등록인구에 적용한 참고 환산값. 같은 인구 구성과 접근성 관계를 가정한 값이며, 현재 주민의 실제 피해 인원이나 그 최솟값을 보장하지 않는다.',
    fontsize=8.1,
    color='#444'
)
fig.savefig(figure_dir / 'G2_두가지셈법.png', dpi=200, bbox_inches='tight')
plt.close(fig)
h = assessment[assessment.HDCD_SGG_NM == '합천군'].copy().sort_values('lb_mid')
short = {'1': '두 지표 일치', '2': '평균만', '3': '하한만', '4': '평균 변화 판정 불가', '5': '관찰', '6': '자료 없음'}
fig, ax = plt.subplots(figsize=(10.5, 7))
y = np.arange(len(h))
ax.barh(
    y,
    h.lb_mid,
    color=[category_colors[c] if not c.startswith('5') else '#c9d1d9' for c in h['최종판정']],
    height=0.62
)
for yy, (_, r) in zip(y, h.iterrows()):
    cm, ce = (bool(r['cap_mid_병·의원']), bool(r['cap_eve_병·의원']))
    if cm and ce:
        dtxt = '낮·저녁 모두 120분 초과'
    elif ce and 120 - r['mid_병·의원'] < 10:
        dtxt = f"저녁만 120분 초과(+{120 - r['mid_병·의원']:.2f}분 초과, 10분 넘는지 불명)"
    elif ce:
        dtxt = f"+{120 - r['mid_병·의원']:.2f}분 초과"
    else:
        dtxt = f"+{r['eve_병·의원'] - r['mid_병·의원']:.1f}분"
    ax.text(
        max(r.lb_mid, 21) + 1.5,
        yy,
        f"{short[r['최종판정'][0]]} | {r['유형'][0]}형 · {dtxt} · 65세+ {int(r.pop65):,}명",
        va='center',
        fontsize=11.5,
        color='#333'
    )
ax.set_yticks(y, h.HDCD_EMD_NM, fontsize=12)
ax.set_xlim(0, 100)
ax.set_xticks(range(0, 101, 20))
ax.axvline(20, color='#555', ls='--', lw=1)
ax.text(21, len(h) - 0.4, '하한 20%', fontsize=8.5, color='#555')
ax.set_xlabel('저녁 연결 상실 하한(%, 전체 모형 인구) — 병·의원·터미널 중 큰 값')
ax.spines[['top', 'right']].set_visible(False)
ax.legend(
    handles=[
        Patch(color=category_colors['1 두 지표 일치'], label='두 지표 일치 → 저녁 시각 고정 연결'),
        Patch(color=category_colors['2 평균만'], label='평균만 → 저녁 호출형'),
        Patch(color=category_colors['4 평균 변화 판정 불가'], label='평균 변화 판정 불가 → 주간·저녁 함께 점검'),
        Patch(color='#c9d1d9', label='관찰')
    ],
    loc='upper center',
    bbox_to_anchor=(0.5, -0.11),
    ncol=2,
    fontsize=11.5,
    frameon=False
)
ax.set_title('합천군 17개 읍·면: 같은 규칙으로 정한 저녁 처방', fontsize=13, loc='left')
fig.text(
    0.01,
    -0.13,
    '[계산] KTDB 2025, 주민등록 2026.9. 막대 0은 공백이 없다는 뜻이 아니라 집계표로 양의 하한을 확인할 수 없다는 뜻. 저녁만 120분 상한인 곳은 "120 - 낮 값"보다 더 나빠졌다는 뜻(초과).',
    fontsize=10,
    color='#444'
)
fig.savefig(figure_dir / 'G3_합천_17개읍면.png', dpi=200, bbox_inches='tight')
plt.close(fig)
steps = [
    ('① 측정', '9월', 'KTDB 접근성 공표\n시간표·주민등록 갱신', '#2b6cb0'),
    ('② 판정', '10월', '두 지표로 재계산\n일치·평균만·하한만', '#c0392b'),
    ('③ 처방', '11~12월', '저녁 시각 고정 연결·호출형\n조례 정의·거리·시각 검토', '#e67e22'),
    ('④ 재원', '1~3월', '기존 교통모델·군비 검토\n지방소멸기금 적격성 확인', '#7b3294'),
    ('⑤ 시범 운행', '3~8월', '60일 운영 점검\n6개월 중간평가', '#2e8b57'),
    ('⑥ 평가·갱신', '9월 이후', '운행 장부·비용·배출 공개\n개편 운행표가 담긴\nKTDB 판으로 보조 검증', '#4a5568')
]
fig, ax = plt.subplots(figsize=(9.6, 7.8))
ax.set_xlim(-1.95, 1.95)
ax.set_ylim(-1.8, 1.8)
ax.axis('off')
ax.set_aspect('equal')
n = len(steps)
circle_radius = 1.34
pos = [(
    circle_radius * np.cos(np.pi / 2 - 2 * np.pi * i / n),
    circle_radius * np.sin(np.pi / 2 - 2 * np.pi * i / n)
) for i in range(n)]
for i, ((tt, when, body, c), (x, yv)) in enumerate(zip(steps, pos)):
    ax.add_patch(FancyBboxPatch(
        (x - 0.53, yv - 0.27),
        1.06,
        0.54,
        boxstyle='round,pad=0.02,rounding_size=0.06',
        fc='white',
        ec=c,
        lw=2.2,
        zorder=3
    ))
    ax.text(
        x,
        yv + 0.14,
        f'{tt}  ·  {when}',
        ha='center',
        va='center',
        fontsize=11,
        weight='bold',
        color=c,
        zorder=4
    )
    ax.text(x, yv - 0.1, body, ha='center', va='center', fontsize=8.2, color='#222222', zorder=4)
    th0 = np.pi / 2 - 2 * np.pi * i / n
    th1 = th0 - 2 * np.pi / n
    dd = 0.42
    p0 = (circle_radius * 0.97 * np.cos(th0 - dd), circle_radius * 0.97 * np.sin(th0 - dd))
    p1 = (circle_radius * 0.97 * np.cos(th1 + dd), circle_radius * 0.97 * np.sin(th1 + dd))
    ax.add_patch(FancyArrowPatch(
        p0,
        p1,
        connectionstyle='arc3,rad=-0.18',
        arrowstyle='-|>',
        mutation_scale=18,
        color='#9aa5b1',
        lw=2,
        zorder=2
    ))
ax.text(0, 0.16, '저녁 교통\n판정표', ha='center', va='center', fontsize=15, weight='bold', color='#c0392b')
ax.text(
    0,
    -0.24,
    '공개 코드로 누구나 재계산\n현황조사 보조지표로 제도화 제안',
    ha='center',
    va='center',
    fontsize=8.8,
    color='#555555'
)
fig.savefig(figure_dir / 'G4_순환흐름.png', dpi=200, bbox_inches='tight')
plt.close(fig)
print('최종 판정', {name: values['n'] for name, values in summary['분류'].items()}, '우선 시군', len(p32))
print('CSV 3개·최종지표.json·그림 G1~G4 저장 완료')
