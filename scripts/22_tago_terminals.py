"""TAGO 시외·고속버스 터미널 목록을 페이지별로 수집한다.
입력은 21_tago_api.py가 호출하는 터미널 목록 API 응답이다.
출력은 데이터/원천_API/TAGO의 서비스별 terminals_all.json이다.
"""
from pathlib import Path
import json
import time
import sys
from importlib import import_module

ROOT = Path(__file__).resolve().parents[1]

sys.path.insert(0, str(ROOT / 'scripts'))
tago_api = import_module('21_tago_api')
call, items, output_dir = (tago_api.call, tago_api.items, tago_api.output_dir)
for svc, op in [('SuburbsBusInfo', 'GetSuberbsBusTrminlList'), ('ExpBusInfo', 'GetExpBusTrminlList')]:
    terminals = []
    for pg in range(1, 20):
        j, st = call(svc, op, pageNo=pg, numOfRows=500)
        its = items(j) if j else None
        if not its:
            break
        terminals += its
        tc = j['response']['body'].get('totalCount')
        if len(terminals) >= int(tc):
            break
        time.sleep(0.2)
    (output_dir / f'{svc}_terminals_all.json').write_text(
        json.dumps(terminals, ensure_ascii=False),
        encoding='utf-8'
    )
    print(svc, '전체 터미널', tc, '수집', len(terminals))
