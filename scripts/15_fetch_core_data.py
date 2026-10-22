"""공공데이터포털과 KTDB에서 시간표·인구·접근성 원자료를 내려받는다.
입력은 코드에 지정한 자료 ID와 제공기관의 파일 응답이다.
출력은 데이터/원천_PC다운로드의 분류별 원자료와 manifest.csv다.
"""
from pathlib import Path
import os
import re
import csv
import time
import requests
import urllib3
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]

urllib3.disable_warnings()
source_dir = ROOT / '데이터' / '원천_PC다운로드'
os.makedirs(source_dir, exist_ok=True)
session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0 Safari/537.36',
    'Referer': 'https://www.data.go.kr/'
})
dataset_ids = {
    '노선시간표': [
        '15150451',
        '15105964',
        '15005337',
        '3072400',
        '15156335',
        '3067173',
        '15131478',
        '15142567',
        '15038342',
        '15150949',
        '15041760',
        '15053575',
        '15053577'
    ],
    '공공데이터포털_지정': ['15162136', '15119713', '15097972', '15066774', '15067528', '15128614']
}
download_log = []

def save_response(resp, d, fallback):
    cd = resp.headers.get('Content-Disposition', '')
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd) or re.search('filename="?([^";]+)', cd)
    name = unquote(m.group(1)) if m else fallback
    try:
        name = name.encode('latin-1').decode('utf-8')
    except Exception:
        pass
    name = re.sub(r'[\\/:*?"<>|]', '_', name)
    p = d / name
    open(p, 'wb').write(resp.content)
    return p

for cat, ids in dataset_ids.items():
    for i in ids:
        url = f'https://www.data.go.kr/data/{i}/fileData.do'
        try:
            r = session.get(url, timeout=30, verify=False)
            r.encoding = 'utf-8'
            title = re.search('<title>(.*?)</title>', r.text, re.S)
            title = re.sub(r'\s+', ' ', title.group(1)).split('|')[0].strip() if title else i
            title = re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
            pairs = sorted(set(re.findall(
                r'atchFileId=(FILE_[0-9A-Za-z]+)&(?:amp;)?fileDetailSn=(\d+)',
                r.text
            )))
            if not pairs:
                pairs = sorted(set(re.findall(r"'(FILE_[0-9A-Za-z]+)'\s*,\s*'(\d+)'", r.text)))
            d = source_dir / cat / f'{i}_{title}'
            os.makedirs(d, exist_ok=True)
            if not pairs:
                download_log.append((cat, i, title, '', 0, 'no atchFileId(외부링크/API형)'))
                continue
            for fid, sn in pairs[:3]:
                dl = f'https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId={fid}&fileDetailSn={sn}&insertDataPrcus=N'
                rr = session.get(dl, timeout=180, verify=False)
                if rr.status_code == 200 and len(rr.content) > 200 and (b'<html' not in rr.content[:400].lower()):
                    p = save_response(rr, d, f'{i}_{sn}.bin')
                    download_log.append((cat, i, title, p, len(rr.content), 'ok'))
                else:
                    download_log.append((cat, i, title, dl, len(rr.content), f'fail {rr.status_code}'))
                time.sleep(0.5)
        except Exception as e:
            download_log.append((cat, i, '', '', 0, 'ERR ' + str(e)[:80]))
d = source_dir / 'KTDB_교통접근성지표_2025'
os.makedirs(d, exist_ok=True)
for no, nm in [('13963', '교통접근성지표_기획서.pdf'), ('13964', '2025년_교통접근성지표.zip')]:
    try:
        rr = session.get(
            f'https://www.ktdb.go.kr/downloadBbsFile.do?atchmnflNo={no}',
            timeout=300,
            verify=False,
            headers={'Referer': 'https://www.ktdb.go.kr/'}
        )
        p = d / nm
        open(p, 'wb').write(rr.content)
        download_log.append((
            'KTDB',
            no,
            nm,
            p,
            len(rr.content),
            'ok' if len(rr.content) > 100000 else 'small'
        ))
    except Exception as e:
        download_log.append(('KTDB', no, nm, '', 0, 'ERR ' + str(e)[:80]))
with open(source_dir / 'manifest.csv', 'w', newline='', encoding='utf-8-sig') as f:
    w = csv.writer(f)
    w.writerow(['분류', 'ID', '제목', '경로', '바이트', '상태'])
    w.writerows(download_log)
print('수집 기록', len(download_log), '저장', 'manifest.csv')
