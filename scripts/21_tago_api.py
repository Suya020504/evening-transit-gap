"""TAGO 시외·고속버스 API의 도시·터미널 목록 응답을 확인한다.
입력은 API 응답과 데이터/.env의 DATA_GO_KR_KEY이며 인증키는 출력하지 않는다.
출력은 데이터/원천_API/TAGO의 서비스·기능별 목록 JSON이다.
"""
from pathlib import Path
import sys
import json
import time
import requests

ROOT = Path(__file__).resolve().parents[1]

output_dir = ROOT / '데이터' / '원천_API' / 'TAGO'
output_dir.mkdir(parents=True, exist_ok=True)
api_key = None
for line in (ROOT / '데이터' / '.env').read_text(encoding='utf-8-sig').splitlines():
    if line.startswith('DATA_GO_KR_KEY='):
        api_key = line.split('=', 1)[1].strip()
assert api_key and len(api_key) == 64

def call(svc, op, **params):
    url = f'https://apis.data.go.kr/1613000/{svc}/{op}'
    p = {'serviceKey': api_key, '_type': 'json', 'numOfRows': 1000, 'pageNo': 1}
    p.update(params)
    try:
        r = requests.get(url, params=p, timeout=30)
    except Exception as e:
        return (None, f'EXC {type(e).__name__}')
    txt = r.text.replace(api_key, '***')
    try:
        j = r.json()
    except Exception:
        return (None, f'HTTP {r.status_code} nonjson {txt[:200]}')
    return (j, f'HTTP {r.status_code}')


def items(j):
    try:
        it = j['response']['body']['items']
        if not it:
            return []
        it = it['item']
        return it if isinstance(it, list) else [it]
    except Exception:
        return None

if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'probe'
    if mode == 'probe':
        for svc, op in [
            ('SuburbsBusInfo', 'GetCtyCodeList'),
            ('ExpBusInfo', 'GetCtyCodeList'),
            ('SuburbsBusInfo', 'GetSuberbsBusTrminlList'),
            ('ExpBusInfo', 'GetExpBusTrminlList')
        ]:
            j, st = call(svc, op)
            its = items(j) if j else None
            print(svc, op, st, '항목', None if its is None else len(its))
            if its:
                (output_dir / f'{svc}_{op}.json').write_text(
                    json.dumps(its, ensure_ascii=False, indent=0),
                    encoding='utf-8'
                )
            time.sleep(0.3)
