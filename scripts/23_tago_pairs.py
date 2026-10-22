"""지정한 날짜의 군·거점도시 간 시외·고속버스 시간표를 양방향으로 수집한다.
입력은 코드의 터미널 쌍·운행일과 21_tago_api.py의 API 응답이다.
출력은 데이터/원천_API/TAGO의 날짜별 pairs 원문 JSON과 요약 CSV다.
"""
from pathlib import Path
import json
import time
import sys
import csv
from importlib import import_module

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / 'scripts'))
tago_api = import_module('21_tago_api')
call, items, output_dir = (tago_api.call, tago_api.items, tago_api.output_dir)
service_date = '20261022'
terminal_pairs = [
    ('거창', '대구서부', 'S', 'NAI5282201', 'NAI4248201'),
    ('거창', '진주개양', 'S', 'NAI5282201', 'NAI5282204'),
    ('합천', '대구서부', 'S', 'NAI5023301', 'NAI4248201'),
    ('합천', '진주개양', 'S', 'NAI5023301', 'NAI5282204'),
    ('산청', '진주개양', 'S', 'NAI5222501', 'NAI5282204'),
    ('하동', '진주개양', 'S', 'NAI5232503', 'NAI5282204'),
    ('의령', '마산', 'S', 'NAI5213801', 'NAI5135601'),
    ('의령', '진주개양', 'S', 'NAI5213801', 'NAI5282204'),
    ('남해', '진주개양', 'S', 'NAI5241401', 'NAI5282204'),
    ('무주', '전주(고속)', 'E', 'NAEK655', 'NAEK600'),
    ('진안', '전주(고속)', 'E', 'NAEK650', 'NAEK600'),
    ('진도', '광주(유스퀘어)', 'E', 'NAEK590', 'NAEK500'),
    ('해남', '광주(유스퀘어)', 'E', 'NAEK595', 'NAEK500'),
    ('장흥', '광주(유스퀘어)', 'E', 'NAEK580', 'NAEK500'),
    ('담양', '광주(유스퀘어)', 'E', 'NAEK582', 'NAEK500'),
    ('화순', '광주(유스퀘어)', 'E', 'NAEK586', 'NAEK500'),
    ('함평', '광주(유스퀘어)', 'E', 'NAEK581', 'NAEK500'),
    ('나주', '광주(유스퀘어)', 'E', 'NAEK530', 'NAEK500'),
    ('순창', '광주(유스퀘어)', 'E', 'NAEK645', 'NAEK500'),
    ('홍천', '춘천', 'E', 'NAEK242', 'NAEK250'),
    ('화천', '춘천', 'E', 'NAEK260', 'NAEK250'),
    ('괴산', '청주(센트럴)', 'E', 'NAEK457', 'NAEK401'),
    ('공주', '대전복합', 'E', 'NAEK320', 'NAEK300'),
    ('금산', '대전복합', 'E', 'NAEK330', 'NAEK300'),
    ('서산', '대전복합', 'E', 'NAEK313', 'NAEK300'),
    ('무주', '대전복합', 'E', 'NAEK655', 'NAEK300')
]
service_operations = {
    'S': ('SuburbsBusInfo', 'GetStrtpntAlocFndSuberbsBusInfo'),
    'E': ('ExpBusInfo', 'GetStrtpntAlocFndExpbusInfo')
}
rows, raw = ([], {})
for gun, hub, s, g, h in terminal_pairs:
    svc, op = service_operations[s]
    for d, a, direction in [(g, h, '군→거점'), (h, g, '거점→군')]:
        j, st = call(
            svc,
            op,
            depTerminalId=d,
            arrTerminalId=a,
            depPlandTime=service_date,
            numOfRows=200
        )
        its = items(j) if j else None
        hdr = None
        try:
            hdr = j['response']['header']
        except Exception:
            pass
        raw[f'{gun}|{hub}|{direction}'] = {'status': st, 'header': hdr, 'items': its}
        n = 0 if not its else len(its)
        deps = sorted((str(i.get('depPlandTime'))[8:12] for i in its or []))
        arrs = sorted((str(i.get('arrPlandTime'))[8:12] for i in its or []))
        rows.append([
            gun,
            hub,
            s,
            direction,
            st,
            (hdr or {}).get('resultCode'),
            n,
            deps[0] if deps else '',
            deps[-1] if deps else '',
            arrs[0] if arrs else '',
            arrs[-1] if arrs else ''
        ])
        time.sleep(0.25)
(output_dir / f'pairs_{service_date}_raw.json').write_text(
    json.dumps(raw, ensure_ascii=False),
    encoding='utf-8'
)
with open(output_dir / f'pairs_{service_date}_summary.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['군', '거점', 'API', '방향', 'HTTP', 'resultCode', '편수', '첫출발', '막출발', '첫도착', '막도착'])
    w.writerows(rows)
print(
    '운행일',
    service_date,
    '조회 구간·방향',
    len(rows),
    '시간표 응답',
    sum((bool(v['items']) for v in raw.values()))
)
