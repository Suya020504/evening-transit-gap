"""자치법규정보시스템에서 교통 지원 조례 목록과 본문을 수집한다.
입력은 ELIS 검색 응답이며 실행 인수로 probe·list·filter·body 중 하나를 받는다.
출력은 데이터/원천_PC다운로드/자치법규_ELIS의 목록 CSV와 body/*.txt다.
"""
from pathlib import Path
import os
import re
import sys
import csv
import time
import html
import requests
import urllib3
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]

urllib3.disable_warnings()
source_dir = ROOT / '데이터' / '원천_PC다운로드' / '자치법규_ELIS'
os.makedirs(source_dir / 'body', exist_ok=True)
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0 Safari/537.36'})
keywords = [
    '어르신 교통',
    '노인 교통비',
    '청소년 교통',
    '아동 교통비',
    '학생 교통비',
    '농어촌버스 요금',
    '버스 요금 지원',
    '대중교통 이용 지원',
    '무료 버스',
    '무상교통',
    '100원 택시',
    '희망택시',
    '행복택시',
    '마을택시',
    '공공형 택시',
    '교통약자 교통비',
    '장애인 교통비',
    '대중교통 소외지역',
    '교통복지',
    '수요응답형'
]

def search(kw, page):
    u = f'https://www.elis.go.kr/main/totSrchList?ctpvCd=&sggCd=&curPage={page}&srchKwd={quote(kw)}'
    r = session.get(u, timeout=30, verify=False)
    r.encoding = 'utf-8'
    return r.text


def search_items(h):
    out = []
    for m in re.finditer(r"fnSrchDtls\('(\d+)'\s*,\s*'(\d+)'\)[^>]*>(.*?)</a>", h, re.S):
        out.append((
            m.group(1),
            m.group(2),
            re.sub(r'\s+', ' ', html.unescape(re.sub('<[^>]+>', ' ', m.group(3)))).strip()
        ))
    return out

mode = sys.argv[1] if len(sys.argv) > 1 else 'probe'
if mode == 'probe':
    h = search('어르신 교통', 1)
    print('검색 응답 길이', len(h), '조례 항목', len(search_items(h)))
elif mode == 'list':
    seen = {}
    for kw in keywords:
        for p in range(1, 40):
            its = search_items(search(kw, p))
            new = [x for x in its if (x[0], x[1]) not in seen]
            for a, hno, t in its:
                seen.setdefault((a, hno), (t, kw))
            if not its or not new:
                break
            time.sleep(0.3)
    with open(source_dir / 'list_all.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f)
        w.writerow(['alrNo', 'histNo', '제목_지자체_공포일_부서', '검색어'])
        for (a, hno), (t, kw) in seen.items():
            w.writerow([a, hno, t, kw])
    print('검색 목록 저장', len(seen))
elif mode == 'filter':
    rows = list(csv.DictReader(open(source_dir / 'list_all.csv', encoding='utf-8-sig')))
    keep = [r for r in rows if '조례' in r['제목_지자체_공포일_부서'] and re.search(
        '교통|요금|무료|무상|택시|버스|이동|수요응답',
        r['제목_지자체_공포일_부서']
    )]
    with open(source_dir / 'list_relevant.csv', 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(keep)
    print('검색 목록', len(rows), '관련 조례', len(keep))
elif mode == 'body':
    rows = list(csv.DictReader(open(source_dir / 'list_relevant.csv', encoding='utf-8-sig')))
    h0 = search('교통', 1)
    tok = re.search('name="_csrf"[^>]*value="([^"]+)"', h0) or re.search('value="([^"]+)"[^>]*name="_csrf"', h0)
    csrf = tok.group(1) if tok else ''
    for i, r in enumerate(rows):
        p = source_dir / 'body' / f"{r['alrNo']}_{r['histNo']}.txt"
        if os.path.exists(p) and os.path.getsize(p) > 2000:
            continue
        try:
            rr = session.post(
                'https://www.elis.go.kr/allalr/selectAlrBdtOne',
                data={
                    '_csrf': csrf,
                    'curPage': '1',
                    'category': 'LAW',
                    'alrNo': r['alrNo'],
                    'histNo': r['histNo'],
                    'menuNm': 'totSrch',
                    'ctpvCd': '',
                    'sggCd': '',
                    'pageSize': '10'
                },
                timeout=30,
                verify=False
            )
            rr.encoding = 'utf-8'
            t = re.sub('<script.*?</script>|<style.*?</style>', ' ', rr.text, flags=re.S)
            t = html.unescape(re.sub('<[^>]+>', '\n', t))
            t = re.sub(r'\n\s*\n+', '\n', t)
            open(p, 'w', encoding='utf-8').write(r['제목_지자체_공포일_부서'] + '\n\n' + t)
        except Exception as e:
            print('ERR', r['alrNo'], e, flush=True)
        time.sleep(0.25)
    print('조례 본문 수집 완료')
