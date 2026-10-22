"""해남·칠곡 시간표 페이지에서 늦은 출발 시각과 첨부파일 후보를 확인한다.
입력은 코드에 지정한 해남군·칠곡군 공식 시간표 페이지다.
출력은 데이터/원천_PC다운로드/군청시간표의 본문 TXT와 화면 요약이다.
"""
from pathlib import Path
import re
import os
import requests
import urllib3
import hashlib
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parents[1]

urllib3.disable_warnings()
output_dir = ROOT / '데이터' / '원천_PC다운로드' / '군청시간표'
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/141.0 Safari/537.36'})
time_pattern = re.compile(r'(?<![\d:])([01]?\d|2[0-3])[:：]([0-5]\d)(?![\d:])')
county_urls = {
    '해남군': [
        'https://www.haenam.go.kr/index.9is?contentUid=18e3368f5d745106015e56138b523566',
        'https://www.haenam.go.kr/index.9is?contentUid=8ae590de99613f9001997e7a90732594'
    ],
    '칠곡군': [
        'https://www.chilgok.go.kr/portal/contents.do?mId=1101010200',
        'https://www.chilgok.go.kr/portal/contents.do?mId=1101010300'
    ]
}

def text_of(html):
    t = re.sub('<script.*?</script>|<style.*?</style>', ' ', html, flags=re.S | re.I)
    return re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', t))

for g, us in county_urls.items():
    d = output_dir / g
    os.makedirs(d, exist_ok=True)
    for u in us:
        r = session.get(u, timeout=25, verify=False)
        r.encoding = r.apparent_encoding or 'utf-8'
        txt = text_of(r.text)
        open(
            d / ('page_' + hashlib.md5(u.encode()).hexdigest()[:10] + '.txt'),
            'w',
            encoding='utf-8'
        ).write(u + '\n\n' + txt)
        times = [(
            m.start(),
            int(m.group(1)) * 60 + int(m.group(2))
        ) for m in time_pattern.finditer(txt)]
        print(
            g,
            r.status_code,
            '시각',
            len(times),
            '최대 %02d:%02d' % divmod(max((v for _, v in times)), 60) if times else ''
        )
        atts = set()
        for m in re.finditer('(?:href|src)="([^"]+)"', r.text):
            x = m.group(1).replace('&amp;', '&')
            if re.search(
                r'\.(pdf|hwp|hwpx|xlsx?|jpg|jpeg|png)(\?|$)|download|fileDown|FileDown|downFile',
                x,
                re.I
            ) and (not re.search('logo|icon|btn|common|banner|footer|header|qr|sns', x, re.I)):
                atts.add(urljoin(r.url, x))
        print('첨부·이미지 후보', len(atts))
