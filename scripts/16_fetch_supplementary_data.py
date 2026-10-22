"""공공데이터 추가 자료, 대중교통 현황조사 PDF와 행정동 경계를 내려받는다.
입력은 공공데이터포털·교통안전공단·행정동 경계 저장소의 응답이다.
출력은 데이터/원천_PC다운로드의 원자료와 manifest_batch2.csv다.
"""
from pathlib import Path
import os
import re
import csv
import time
import requests
import urllib3
from urllib.parse import unquote, urljoin

ROOT = Path(__file__).resolve().parents[1]

urllib3.disable_warnings()
source_dir = ROOT / '데이터' / '원천_PC다운로드'
session = requests.Session()
session.headers.update({'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36'})
download_log = []

def response_filename(resp, fallback):
    cd = resp.headers.get('Content-Disposition', '')
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search('filename="?([^";]+)', cd)
    n = unquote(m.group(1)) if m else fallback
    try:
        n = n.encode('latin-1').decode('utf-8')
    except Exception:
        pass
    return re.sub(r'[\\/:*?"<>|]', '_', n)

for i in [
    '15060936',
    '15066754',
    '15066765',
    '15066791',
    '15066795',
    '15066799',
    '15106057',
    '15106061',
    '15129754',
    '15149997',
    '15157020',
    '15160379',
    '15161178',
    '15162302',
    '15134586',
    '15123179'
]:
    try:
        r = session.get(
            f'https://www.data.go.kr/data/{i}/fileData.do',
            timeout=30,
            verify=False,
            headers={'Referer': 'https://www.data.go.kr/'}
        )
        r.encoding = 'utf-8'
        t = re.search('<title>(.*?)</title>', r.text, re.S)
        t = re.sub(r'[\\/:*?"<>|\s]+', ' ', t.group(1)).split('|')[0].strip()[:60] if t else i
        pairs = sorted(set(re.findall(
            r'atchFileId=(FILE_[0-9A-Za-z]+)&(?:amp;)?fileDetailSn=(\d+)',
            r.text
        )))
        d = source_dir / '공공데이터포털_지정' / f'{i}_{t}'
        os.makedirs(d, exist_ok=True)
        if not pairs:
            download_log.append(('dgk', i, t, 'no file'))
            continue
        for fid, sn in pairs[:3]:
            rr = session.get(
                f'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={fid}&fileDetailSn={sn}&insertDataPrcus=N',
                timeout=300,
                verify=False,
                headers={'Referer': 'https://www.data.go.kr/'}
            )
            if rr.status_code == 200 and len(rr.content) > 200 and (b'<html' not in rr.content[:400].lower()):
                p = d / response_filename(rr, f'{i}_{sn}.bin')
                open(p, 'wb').write(rr.content)
                download_log.append(('dgk', i, p, len(rr.content)))
            else:
                download_log.append(('dgk', i, t, f'fail {rr.status_code}'))
            time.sleep(0.4)
    except Exception as e:
        download_log.append(('dgk', i, '', 'ERR ' + str(e)[:80]))
d = source_dir / '대중교통현황조사_PTC'
os.makedirs(d, exist_ok=True)
try:
    r = session.get('https://www.kotsa.or.kr/ptc/ptcData.do', timeout=30, verify=False)
    r.encoding = r.apparent_encoding or 'utf-8'
    open(d / '_ptcData.html', 'w', encoding='utf-8').write(r.text)
    links = sorted(set(re.findall(
        r'href="([^"]*(?:download|fileDown|FileDown|\.pdf)[^"]*)"',
        r.text,
        re.I
    )))
    js = sorted(set(re.findall(r'(?:fn_?[Ff]ile[Dd]own|fnDownload|download)\(([^)]*)\)', r.text)))
    download_log.append(('ptc', 'page', len(links), len(js)))
    for u in links[:20]:
        u = urljoin(r.url, u.replace('&amp;', '&'))
        rr = session.get(u, timeout=300, verify=False, headers={'Referer': r.url})
        if rr.status_code == 200 and rr.content[:4] == b'%PDF':
            p = d / response_filename(rr, os.path.basename(u)[:60] + '.pdf')
            open(p, 'wb').write(rr.content)
            download_log.append(('ptc', u, p, len(rr.content)))
except Exception as e:
    download_log.append(('ptc', '', '', 'ERR ' + str(e)[:80]))
d = source_dir / '행정동경계_admdongkor'
os.makedirs(d, exist_ok=True)
try:
    api = session.get('https://api.github.com/repos/vuski/admdongkor/contents', timeout=30).json()
    vers = sorted([x['name'] for x in api if x['type'] == 'dir' and x['name'].startswith('ver')])
    last = vers[-1]
    files = session.get(
        f'https://api.github.com/repos/vuski/admdongkor/contents/{last}',
        timeout=30
    ).json()
    for x in files:
        if x['name'].endswith('.geojson') and 'HangJeongDong' in x['name']:
            rr = session.get(x['download_url'], timeout=300)
            open(d / x['name'], 'wb').write(rr.content)
            download_log.append(('admdong', last, x['name'], len(rr.content)))
except Exception as e:
    download_log.append(('admdong', '', '', 'ERR ' + str(e)[:80]))
with open(source_dir / 'manifest_batch2.csv', 'w', newline='', encoding='utf-8-sig') as f:
    csv.writer(f).writerows(download_log)
print('수집 기록', len(download_log), '저장', 'manifest_batch2.csv')
