"""지정한 공공데이터포털 파일데이터 한 건의 첨부파일을 내려받는다.
입력은 실행 인수의 자료 ID와 저장 폴더 이름이다.
출력은 데이터/원천_PC다운로드 아래 지정 폴더의 첨부파일이다.
"""
from pathlib import Path
import re
import sys
import requests

ROOT = Path(__file__).resolve().parents[1]

dataset_id, name = (sys.argv[1], sys.argv[2])
output_dir = ROOT / '데이터' / '원천_PC다운로드' / name
output_dir.mkdir(parents=True, exist_ok=True)
session = requests.Session()
session.headers['User-Agent'] = 'Mozilla/5.0'
h = session.get(f'https://www.data.go.kr/data/{dataset_id}/fileData.do', timeout=30).text
attachment_ids = sorted(set(re.findall(
    r'atchFileId=(FILE_[0-9A-Za-z]+)&(?:amp;)?fileDetailSn=(\d+)',
    h
)))
for a, sn in attachment_ids:
    r = session.get(
        'https://www.data.go.kr/cmm/cmm/fileDownload.do',
        params={'atchFileId': a, 'fileDetailSn': sn, 'insertDataPrcus': 'N'},
        timeout=60
    )
    cd = r.headers.get('Content-Disposition', '')
    m = re.search('filename\\*?=(?:UTF-8\'\')?\\"?([^\\";]+)', cd)
    fn = requests.utils.unquote(m.group(1)) if m else f'{dataset_id}_{sn}.bin'
    try:
        fn = fn.encode('latin-1').decode('utf-8')
    except Exception:
        pass
    (output_dir / fn).write_bytes(r.content)
print('자료 ID', dataset_id, '첨부파일', len(attachment_ids), '저장 폴더', output_dir)
