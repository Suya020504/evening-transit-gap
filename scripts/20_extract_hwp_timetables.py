"""HWP 첨부파일의 본문을 추출하고 저녁 운행시각을 확인한다.
입력은 실행 인수의 다운로드 URL과 프로젝트 기준 저장 경로다.
출력은 지정한 HWP 파일과 같은 경로에 .txt를 붙인 본문 파일이다.
"""
from pathlib import Path
import sys
import re
import zlib
import struct
import requests
import urllib3
import olefile

ROOT = Path(__file__).resolve().parents[1]

urllib3.disable_warnings()
url = sys.argv[1]
output_path = ROOT / sys.argv[2]
r = requests.get(url, timeout=40, verify=False, headers={'User-Agent': 'Mozilla/5.0'})
open(output_path, 'wb').write(r.content)
f = olefile.OleFileIO(output_path)
parts = []
for e in f.listdir():
    if e[0] == 'BodyText':
        d = f.openstream(e).read()
        try:
            d = zlib.decompress(d, -15)
        except Exception:
            pass
        i = 0
        while i < len(d) - 4:
            h = struct.unpack_from('<I', d, i)[0]
            tag = h & 1023
            size = h >> 20 & 4095
            i += 4
            # HWP 레코드 크기가 확장 표기이면 뒤의 4바이트에서 실제 크기를 읽는다.
            if size == 4095:
                size = struct.unpack_from('<I', d, i)[0]
                i += 4
            if tag == 67:
                parts.append(d[i:i + size].decode('utf-16le', 'ignore'))
            i += size
t = re.sub(r'[\x00-\x08\x0b-\x1f]', ' ', '\n'.join(parts))
open(str(output_path) + '.txt', 'w', encoding='utf-8').write(t)
time_pattern = re.compile(r'(?<![\d:])([01]?\d|2[0-3])[:：]([0-5]\d)(?![\d:])')
times = [(m.start(), int(m.group(1)) * 60 + int(m.group(2))) for m in time_pattern.finditer(t)]
print(
    'bytes',
    len(r.content),
    '시각',
    len(times),
    '최대 %02d:%02d' % divmod(max((v for _, v in times)), 60) if times else ''
)
print('19시 이후 시각 분포', sorted(set(('%02d:%02d' % divmod(v, 60) for _, v in times if v >= 1140))))
