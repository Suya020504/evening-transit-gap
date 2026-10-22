"""보고서 그림 1(문제 정의)과 그림 4(분석결과 데이터 시각화 6종)를 만든다.
입력은 읍면동_최종판정.csv, 07번의 보고서_추가지표.json·막차_악화율_51.csv, 25번의 공식판정_비교.csv·json이다.
출력은 fig/보고서의 F1_문제정의.png와 F8_분석결과.png다. 그림 2·3(지도, 합천군)은 06번이 만든다.
"""
import json
import sys
from pathlib import Path

import matplotlib
import matplotlib.ticker
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.lines import Line2D
import pandas as pd

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
SRC = ROOT / '데이터' / '가공' / '통합'
OUT = ROOT / 'fig' / '보고서'
OUT.mkdir(parents=True, exist_ok=True)

for name in ('Malgun Gothic', 'Noto Sans CJK KR', 'NanumGothic'):
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams['font.family'] = name
        break
plt.rcParams.update({'axes.unicode_minus': False, 'font.size': 7.5, 'axes.spines.top': False,
                     'axes.spines.right': False, 'savefig.dpi': 300})
MM = 1 / 25.4
RED, BLUE, GREY, NAVY, GREEN = '#C0392B', '#2E6DB4', '#A7B0BA', '#34495E', '#2E8B57'

d = pd.read_csv(SRC / '읍면동_최종판정.csv', dtype={'HDCD': str})
extra = json.load(open(SRC / '보고서_추가지표.json', encoding='utf-8'))

# 저녁 악화: 유형 A·B·C(병·의원 평균 접근시간이 저녁에 10분 넘게 늘어남, 120분 상한 처리 포함)
valid = d.dropna(subset=['mid_병·의원', 'eve_병·의원'])
worse = valid['유형'].str[0].isin(['A', 'B', 'C'])
gun = valid['군'].astype(bool)
rate = {'군': (worse[gun].sum(), gun.sum()), '시·구': (worse[~gun].sum(), (~gun).sum())}


def fig_problem():
    """그림: 판정 기준과 이용자 요구의 어긋남, 저녁 공백의 지역 차이."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(120 * MM, 50 * MM), gridspec_kw={'width_ratios': [1.35, 1]})
    # 2025 대중교통 현황조사 종합결과 보고서 표 2-77(버스 이용자 개선 요구, 복수응답) 중 4개 항목
    items = ['접근·환승거리', '첫차·막차 운영시간', '요금', '배차간격']
    vals = [10.5, 29.7, 38.2, 46.5]
    notes = ['거리 기준', '판정에 없음', '', '운행횟수 기준']
    cols = [NAVY, RED, GREY, NAVY]
    a.barh(items, vals, color=cols, height=0.62)
    for y, (v, n, c) in enumerate(zip(vals, notes, cols)):
        a.text(v + 1, y, f'{v}%', va='center', fontsize=7.3)
        if n:
            a.annotate(n, (v, y), xytext=(27, 0), textcoords='offset points', va='center', fontsize=6.6,
                       color=c, fontweight='bold')
    a.set_xlim(0, 75); a.set_xlabel('개선 요구 응답 비율(%, 복수응답)', fontsize=6.8)
    a.set_title('① 버스 이용자 개선 요구 vs 최소서비스 판정 기준', fontsize=7.4, loc='left', fontweight='bold')
    a.tick_params(axis='y', length=0)
    labels = ['시·구', '군']
    pct = [rate[k][0] / rate[k][1] * 100 for k in labels]
    b.bar(labels, pct, color=[GREY, RED], width=0.55)
    for x, k in enumerate(labels):
        n, tot = rate[k]
        b.text(x, pct[x] + 1.5, f'{pct[x]:.1f}%\n({n:,}/{tot:,}곳)', ha='center', fontsize=7)
    b.set_ylim(0, 55); b.set_ylabel('읍면동 비율(%)', fontsize=6.8)
    b.set_title('② 저녁 악화 읍면동 비율', fontsize=7.4, loc='left', fontweight='bold')
    fig.tight_layout(w_pad=2.2)
    fig.savefig(OUT / 'F1_문제정의.png')
    plt.close(fig)


def fig_results():
    """그림: 분석결과 데이터 시각화 6종(분석결과 이미지란)."""
    fig, ax = plt.subplots(3, 2, figsize=(138 * MM, 158 * MM), gridspec_kw={'height_ratios': [1, 1, 1.15]})
    # ① 낮 vs 저녁 접근시간(읍면동)
    a = ax[0, 0]
    for flag, c, sz, al, lab in ((False, GREY, 2.5, 0.35, '시·구'), (True, RED, 3.5, 0.55, '군')):
        sub = valid[valid['군'].astype(bool) == flag]
        a.scatter(sub['mid_병·의원'], sub['eve_병·의원'], s=sz, c=c, alpha=al, lw=0, label=lab)
    a.plot([0, 120], [0, 120], color='#333333', lw=0.6)
    a.plot([0, 110], [10, 120], color=RED, lw=0.7, ls='--')
    a.set_xlim(0, 122); a.set_ylim(0, 122)
    a.set_xlabel('낮(12~14시) 평균 접근시간(분)', fontsize=6.5); a.set_ylabel('저녁(18~20시)(분)', fontsize=6.5)
    a.text(118, 4, f"빨간 점선 위 = 10분 넘게 악화\n군 {rate['군'][0] / rate['군'][1] * 100:.1f}% · 시·구 {rate['시·구'][0] / rate['시·구'][1] * 100:.1f}%",
           fontsize=5.8, va='bottom', ha='right', bbox=dict(fc='white', ec='none', alpha=0.85, pad=1.5))
    a.legend(frameon=False, fontsize=6, loc='upper left', markerscale=2.5)
    a.set_title(f'① 병·의원 대중교통 접근시간(읍면동 {len(valid):,}곳)', fontsize=7.2, loc='left', fontweight='bold')
    # ② 공식 판정 확보비율과 저녁 악화(군)
    a = ax[0, 1]
    cmp_ = pd.read_csv(SRC / '공식판정_비교.csv')
    g = cmp_[cmp_['군'].astype(bool)]
    hi = (g['확보비율_DRT반영후'] >= 80) & (g['저녁악화비율'] >= 50)
    a.scatter(g.loc[~hi, '확보비율_DRT반영후'], g.loc[~hi, '저녁악화비율'], s=16, c=GREY, lw=0)
    a.scatter(g.loc[hi, '확보비율_DRT반영후'], g.loc[hi, '저녁악화비율'], s=20, c=RED, lw=0)
    offs = {'무주군': (-6, 6, 'right'), '해남군': (5, 3, 'left'), '창녕군': (-5, 2, 'right'), '거창군': (-5, -7, 'right'),
            '장수군': (5, -5, 'left'), '고령군': (-5, -2, 'right'), '고창군': (5, -2, 'left')}
    for _, r in g[hi].iterrows():
        dx, dy, ha = offs.get(r['시군구'], (4, 2, 'left'))
        a.annotate(r['시군구'], (r['확보비율_DRT반영후'], r['저녁악화비율']), xytext=(dx, dy), textcoords='offset points',
                   fontsize=5.6, color=RED, ha=ha, va='center')
    a.axvline(80, color='#7F8C8D', lw=0.6, ls=':')
    a.set_xlim(30, 100); a.set_ylim(0, 100)
    a.set_xlabel('정부 판정 최소서비스 확보지역 비율(%, DRT 반영 후)', fontsize=6.3); a.set_ylabel('저녁 악화 읍면동 비율(%)', fontsize=6.5)
    cj = json.load(open(SRC / '공식판정_비교.json', encoding='utf-8'))
    r_ = cj['군_순위상관_DRT반영후']; b80 = cj['군_확보율구간']['80% 이상']
    a.text(31.5, 4, f"군 {cj['결합_군수']}곳 순위상관 ρ {r_['rho']:.2f}(p {r_['p']:.2f})\n확보율 80% 이상 {b80['군수']}개 군도\n저녁 악화 비율 평균 {b80['저녁악화비율_평균']}%",
           fontsize=5.8, va='bottom', bbox=dict(fc='white', ec='none', alpha=0.85, pad=1.2))
    a.set_title('② 정부 판정 확보율과 저녁 악화(군)', fontsize=7.2, loc='left', fontweight='bold')
    # ③ 마지막 출발 시각과 저녁 악화(51개 시·군)
    a = ax[1, 0]
    s51 = pd.read_csv(SRC / '막차_악화율_51.csv')
    city = s51['지자체명'].str.endswith('시')
    a.axvspan(18 * 60 + 30, 20 * 60, color='#FDECEA', zorder=0)
    a.text(18 * 60 + 36, 7, '20시 이후 출발\n기록 없음(10곳)', fontsize=5.6, color=RED, va='bottom')
    for flag, c, lab in ((False, RED, '군'), (True, BLUE, '시')):
        sub = s51[city == flag]
        a.scatter(sub['분'], sub['rate'], s=sub['n'] * 1.2 + 6, c=c, alpha=0.75, lw=0.4, edgecolors='white', label=lab, zorder=3)
    for nm, off in {'합천군': (5, 2), '무주군': (5, 2), '해남군': (5, -3), '의령군': (5, 2)}.items():
        r = s51[s51['지자체명'] == nm]
        if len(r):
            a.annotate(nm[:-1], (r['분'].iloc[0], r['rate'].iloc[0]), xytext=off, textcoords='offset points', fontsize=5.6)
    a.set_xticks(range(19 * 60, 24 * 60, 60)); a.set_xticklabels([f'{h}시' for h in range(19, 24)])
    a.set_xlim(18 * 60 + 30, 23 * 60 + 40); a.set_ylim(-4, 100)
    m = extra['막차_산점도']
    a.text(0.97, 0.97, f"순위상관 ρ {m['rho']:.2f}\n(95% 구간 {m['ci95'][0]:.2f}~{m['ci95'][1]:.2f})", transform=a.transAxes,
           ha='right', va='top', fontsize=5.8)
    a.set_xlabel('평일 마지막 출발 시각(등록 시간표, 군청 시간표 보정)', fontsize=6.2); a.set_ylabel('저녁 악화 읍면동 비율(%)', fontsize=6.5)
    a.legend(handles=[Line2D([], [], marker='o', ls='', color=RED, ms=4, label='군'), Line2D([], [], marker='o', ls='', color=BLUE, ms=4, label='시')],
             frameon=False, fontsize=5.8, loc='center right')
    a.set_title(f'③ 마지막 출발 시각과 저녁 악화({len(s51)}개 시·군)', fontsize=7.2, loc='left', fontweight='bold')
    # ④ 판정 구성
    a = ax[1, 1]
    cats = [('1 두 지표 일치', '두 지표 일치', RED), ('2 평균만', '평균만', '#E67E22'), ('3 하한만', '하한만', BLUE),
            ('4 평균 변화 판정 불가', '판정 불가', '#7F8C8D'), ('5 관찰', '관찰', '#D5DBDF')]
    rows = [('군', d[d['군'].astype(bool)]), ('시·구', d[~d['군'].astype(bool)])]
    for y, (name, sub) in enumerate(rows):
        sub = sub[sub['최종판정'] != '6 자료 없음']; left = 0
        for key, lab, c in cats:
            v = (sub['최종판정'] == key).mean() * 100
            a.barh(y, v, left=left, color=c, height=0.55, label=lab if y == 0 else None)
            if v >= 4:
                a.text(left + v / 2, y, f'{v:.0f}', ha='center', va='center', fontsize=6, color='white' if c not in ('#D5DBDF',) else 'black')
            left += v
    a.set_yticks([0, 1]); a.set_yticklabels([r[0] for r in rows]); a.invert_yaxis(); a.set_xlim(0, 100)
    a.set_xlabel('읍면동 비율(%)', fontsize=6.5)
    a.legend(frameon=False, fontsize=5.5, ncol=5, loc='center', bbox_to_anchor=(0.5, 0.5), handlelength=1, columnspacing=0.8)
    a.set_title('④ 두 지표 판정 구성', fontsize=7.2, loc='left', fontweight='bold')
    # ⑤ 저녁 악화 읍면동의 65세 이상, 시·군 상위 10
    a = ax[2, 0]
    worse_df = d[d['유형'].astype(str).str[0].isin(['A', 'B', 'C'])]
    top = worse_df.groupby(['HDCD_SD_NM', 'HDCD_SGG_NM'])['pop65'].sum().sort_values(ascending=False).head(10)
    labels = [s for _, s in top.index][::-1]; vals = top.values[::-1]
    a.barh(labels, vals, color=[RED if l == '합천군' else GREY for l in labels], height=0.62)
    for y, v in enumerate(vals):
        a.text(v + 150, y, f'{v:,.0f}', va='center', fontsize=5.8)
    a.tick_params(axis='y', labelsize=6.2, length=0); a.set_xlim(0, 21000)
    a.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda x, _: f'{x / 1e4:.1f}만'))
    a.set_xlabel('65세 이상(명)', fontsize=6.5)
    a.set_title('⑤ 저녁 악화 읍면동의 65세 이상, 시·군 상위 10', fontsize=7.2, loc='left', fontweight='bold')
    # ⑥ 문턱·기준선 민감도
    a = ax[2, 1]
    th = [10, 20, 30]; bases = [('lb_mid', '낮(기준)', RED), ('lb_am', '오전첨두', '#E67E22'), ('lb_all', '일평균', GREY)]
    bw = 0.26
    for k, (col, lab, c) in enumerate(bases):
        cnt = [int((d[col] >= t).sum()) for t in th]
        xs = [i + (k - 1) * bw for i in range(len(th))]
        a.bar(xs, cnt, bw, color=c, label=lab)
        for x, n in zip(xs, cnt):
            a.text(x, n + 8, str(n), ha='center', fontsize=5.5)
    a.set_xticks(range(len(th))); a.set_xticklabels([f'하한 {t}% 이상' for t in th])
    a.set_ylim(0, 640); a.set_ylabel('읍면동 수', fontsize=6.5); a.legend(frameon=False, fontsize=5.8, title='기준선', title_fontsize=5.8, loc='upper right', ncol=3, handlelength=1, columnspacing=0.8)
    a.set_title('⑥ 하한 문턱·기준선을 바꿔도 남는 대상', fontsize=7.2, loc='left', fontweight='bold')
    for a in ax.flat:
        a.tick_params(labelsize=6.2)
    fig.tight_layout(h_pad=1.6, w_pad=1.6)
    fig.savefig(OUT / 'F8_분석결과.png')
    plt.close(fig)


fig_problem(); fig_results()
print(f"저녁 악화 읍면동: 군 {rate['군'][0]}/{rate['군'][1]}, 시·구 {rate['시·구'][0]}/{rate['시·구'][1]} → {OUT}")
