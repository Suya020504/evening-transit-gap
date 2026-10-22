"""평일·휴일 시간표를 노선정보와 결합해 노선별·지자체별 마지막 출발 시각을 계산한다.
입력은 데이터/원천_PC다운로드/노선시간표의 15150451·15105964 CSV다.
출력은 데이터/가공의 노선시간표_노선별.csv와 노선시간표_지자체요약.csv다.
"""
from pathlib import Path
import glob
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

output_dir = ROOT / '데이터' / '가공'
output_dir.mkdir(parents=True, exist_ok=True)


def read_table(f):
    enc = 'utf-8-sig' if open(f, 'rb').read(3) == b'\xef\xbb\xbf' else 'cp949'
    return pd.read_csv(f, dtype=str, encoding=enc)

timetable = read_table(glob.glob(str(ROOT / '데이터' / '원천_PC다운로드' / '노선시간표' / '15150451_*' / '*.csv'))[0])
routes = read_table(glob.glob(str(ROOT / '데이터' / '원천_PC다운로드' / '노선시간표' / '15105964_*' / '*.csv'))[0])

def time_to_minutes(time_text):
    try:
        h, m = str(time_text).split(':')[:2]
        return int(h) * 60 + int(m)
    except Exception:
        return None

timetable['회수'] = pd.to_numeric(timetable['일일운행횟수'], errors='coerce')
timetable['첫차'] = timetable[['기점첫차출발시각', '종점첫차출발시각']].apply(
    lambda row: min([x for x in map(time_to_minutes, row) if x is not None], default=None),
    axis=1
)
timetable['막차'] = timetable[['기점막차출발시각', '종점막차출발시각']].apply(
    lambda row: max([x for x in map(time_to_minutes, row) if x is not None], default=None),
    axis=1
)

# 요일별 기록이 없으면 매일 운행 기록을 사용한다.
def select_service_day(g, want):
    x = g[g['요일'] == want]
    return x if len(x) else g[g['요일'] == '매일']

rows = []
for rid, g in timetable.groupby('노선 아이디'):
    w = select_service_day(g, '평일')
    h = select_service_day(g, '공휴일')
    rows.append({
        '노선ID': rid,
        '평일_회수': w['회수'].sum() if len(w) else None,
        '휴일_회수': h['회수'].sum() if len(h) else None,
        '평일_첫차': w['첫차'].min() if len(w) else None,
        '평일_막차': w['막차'].max() if len(w) else None,
        '휴일_막차': h['막차'].max() if len(h) else None,
        '휴일_운행없음': len(h) == 0
    })
route_summary = pd.DataFrame(rows).merge(
    routes.rename(columns={'노선 아이디': '노선ID'}),
    on='노선ID',
    how='left'
)
join_rate = round(route_summary['지자체명'].notna().mean() * 100, 1)
route_summary = route_summary[route_summary['평일_막차'].notna()]
route_summary.to_csv(output_dir / '노선시간표_노선별.csv', index=False, encoding='utf-8-sig')
format_time = lambda v: f'{int(v) // 60:02d}:{int(v) % 60:02d}' if pd.notna(v) else ''
area_summary = route_summary.groupby('지자체명').agg(
    노선ID수=('노선ID', 'size'),
    평일총회수=('평일_회수', 'sum'),
    일3회이하=('평일_회수', lambda x: (x <= 3).sum()),
    막차19시전=('평일_막차', lambda x: (x < 1140).sum()),
    막차20시전=('평일_막차', lambda x: (x < 1200).sum()),
    출발20시이후=('평일_막차', lambda x: (x >= 1200).sum()),
    출발21시이후=('평일_막차', lambda x: (x >= 1260).sum()),
    최종출발=('평일_막차', 'max')
).reset_index()
area_summary['최종출발'] = area_summary['최종출발'].map(format_time)
area_summary = area_summary.sort_values(['출발20시이후', '최종출발'])
area_summary.to_csv(output_dir / '노선시간표_지자체요약.csv', index=False, encoding='utf-8-sig')
print(
    '지자체',
    len(area_summary),
    '평일 노선',
    len(route_summary),
    '20시 이후 출발 없음',
    int((area_summary['출발20시이후'] == 0).sum())
)
print('노선정보 결합률(%)', join_rate)
