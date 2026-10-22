"""군청 공식 시간표 페이지와 첨부파일을 수집하고 페이지의 마지막 시각을 확인한다.
입력은 코드에 지정한 군청 URL이며 실행 인수로 수집할 군을 지정할 수 있다.
출력은 데이터/원천_PC다운로드/군청시간표의 본문·첨부파일과 수집 요약 JSON이다.
"""
from pathlib import Path
import os
import re
import json
import sys
import hashlib
from urllib.parse import urljoin, urlparse
import requests
import urllib3

ROOT = Path(__file__).resolve().parents[1]

urllib3.disable_warnings()
output_dir = ROOT / '데이터' / '원천_PC다운로드' / '군청시간표'
os.makedirs(output_dir, exist_ok=True)
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'})
county_urls = {
    '창녕군': [
        'https://www.cng.go.kr/01661/02238/02248.web',
        'https://www.cng.go.kr/01661/02238/02249.web',
        'https://www.cng.go.kr/01661/02238/02244.web'
    ],
    '산청군': ['https://www.sancheong.go.kr/www/contents.do?key=267'],
    '진도군': ['https://www.jindo.go.kr/home/sub.cs?m=918', 'https://www.jindo.go.kr/home/sub.cs?m=915'],
    '합천군': ['https://www.hc.go.kr/05751/05866/05873.web', 'https://www.hc.go.kr/05896.web'],
    '거창군': [
        'https://www.geochang.go.kr/00315/00396/00408.web',
        'https://www.geochang.go.kr/00315/00396/00412.web'
    ],
    '하동군': [
        'https://www.hadong.go.kr/specialty/00218/00444.web',
        'https://www.hadong.go.kr/specialty/00218/00445.web'
    ],
    '의령군': [
        'https://www.uiryeong.go.kr/index.uiryeong?menuCd=DOM_000000204005001002',
        'https://www.uiryeong.go.kr/index.uiryeong?menuCd=DOM_000000204005001000'
    ],
    '장흥군': ['https://www.jangheung.go.kr/www/jeongnamjin/directions/city_bus'],
    '무주군': ['https://www.muju.go.kr/index.9is?contentUid=4028a6d288d81dbb0189b03d68b50c68'],
    '진안군': [
        'https://www.jinan.go.kr/index.jinan?menuCd=DOM_000000109004001002',
        'https://www.jinan.go.kr/index.jinan?menuCd=DOM_000000109004001003'
    ],
    '의성군': ['https://www.usc.go.kr/ko/page.do?mnu_uid=548'],
    '울릉군': ['https://www.ulleung.go.kr/ko/page.do?mnu_uid=1244'],
    '칠곡군': ['https://www.chilgok.go.kr/portal/contents.do?mId=1101010200'],
    '해남군': [
        'https://www.haenam.go.kr/index.9is?contentUid=18e3368f5d745106015e56138b523566',
        'https://www.haenam.go.kr/index.9is?contentUid=8ae590de99613f9001997e7a90732594'
    ]
}
time_pattern = re.compile(r'(?<![\d:])([01]?\d|2[0-3])[:：]([0-5]\d)(?![\d:])')
attachment_pattern = re.compile(
    r'\.(pdf|hwp|hwpx|xlsx?|jpg|jpeg|png)(\?|$)|download|fileDown|FileDown|downFile',
    re.I
)

def page_text(h):
    t = re.sub('<script.*?</script>|<style.*?</style>', ' ', h, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', t))

selected_counties = sys.argv[1:] or list(county_urls)
summary = {}
for g in selected_counties:
    d = output_dir / g
    os.makedirs(d, exist_ok=True)
    got = []
    pages = []
    for u in county_urls[g]:
        try:
            r = session.get(u, timeout=25, verify=False)
            r.encoding = r.apparent_encoding or 'utf-8'
        except Exception as e:
            pages.append({'url': u, 'err': str(e)[:80]})
            continue
        txt = page_text(r.text)
        fn = 'page_' + hashlib.md5(u.encode()).hexdigest()[:10] + '.txt'
        open(d / fn, 'w', encoding='utf-8').write(u + '\n\n' + txt)
        times = [int(a) * 60 + int(b) for a, b in time_pattern.findall(txt)]
        pages.append({
            'url': u,
            'file': fn,
            'n_times': len(times),
            'max': '%02d:%02d' % divmod(max(times), 60) if times else None
        })
        for m in re.finditer('(?:href|src)="([^"]+)"', r.text):
            x = urljoin(r.url, m.group(1).replace('&amp;', '&'))
            if attachment_pattern.search(x) and (not re.search(
                'logo|icon|btn|common|banner|footer|header|qr|sns|todayPic|webmark|opentype|kogl',
                x,
                re.I
            )) and (x not in got):
                got.append(x)
    saved = []
    for x in got[:30]:
        try:
            rr = session.get(x, timeout=60, verify=False)
            if len(rr.content) < 800 or 'text/html' in rr.headers.get('Content-Type', ''):
                continue
            ext = os.path.splitext(urlparse(x).path)[1] or '.bin'
            fn = hashlib.md5(x.encode()).hexdigest()[:8] + ext
            open(d / fn, 'wb').write(rr.content)
            saved.append({'url': x, 'file': fn, 'bytes': len(rr.content)})
        except Exception:
            pass
    summary[g] = {'pages': pages, 'attachments': saved}
json.dump(
    summary,
    open(
        output_dir / ('crawl_' + '_'.join(selected_counties)[:40] + '.json'),
        'w',
        encoding='utf-8'
    ),
    ensure_ascii=False,
    indent=1
)
print(
    '수집 군',
    len(summary),
    '본문',
    sum((len(v['pages']) for v in summary.values())),
    '첨부',
    sum((len(v['attachments']) for v in summary.values()))
)
