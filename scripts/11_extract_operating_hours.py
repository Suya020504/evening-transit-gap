"""교통 대체수단 조례에서 고정 운행시각과 조건부 운행 문구를 추출한다.
입력은 조례790_규칙추출.csv와 자치법규_ELIS/body/*.txt다.
출력은 데이터/가공/통합/조례_운행시각_v3.csv다.
"""
from pathlib import Path
import re
import glob
import os
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

o = pd.read_csv(ROOT / '데이터' / '가공' / '조례790_규칙추출.csv', dtype={'alrNo': str})
body_files = {}
for f in glob.glob(str(ROOT / '데이터' / '원천_PC다운로드' / '자치법규_ELIS' / 'body' / '*.txt')):
    body_files.setdefault(os.path.basename(f).split('_')[0], []).append(f)
include_title = re.compile('택시|콜버스|수요응답|행복버스|마을버스|한정면허|교통복지|대중교통 소외|통학')
exclude_title = re.compile(r'셔틀|순환\s*버스|자전거|공원|청소년\s*시설|문화시설|체육|특별교통수단|장애인|요금|정류소|버스정보|공영주차')

def hour_24(ampm, x):
    x = int(x)
    if ampm == '오후' and x < 12:
        x += 12
    return x

korean_time_range = re.compile(r'(오전|오후)?\s*(\d{1,2})\s*시\s*(?:\d{1,2}\s*분\s*)?(?:부터|에서)\s*(?:익일\s*)?(오전|오후)?\s*(\d{1,2})\s*시\s*(?:\d{1,2}\s*분\s*)?까지')
colon_time_range = re.compile(r'(\d{1,2}):(\d{2})\s*[~∼-]\s*(\d{1,2}):(\d{2})')
colon_word_range = re.compile(r'(\d{1,2}):\d{2}\s*(?:부터|에서)\s*(\d{1,2}):\d{2}\s*까지')
# 막차 연계 등 종료 시각이 확정되지 않은 조건을 따로 분류한다.
conditional_service = re.compile(r'(오전|오후)?\s*(\d{1,2})\s*시\s*이후까지|막차[^.。]{0,40}이후')
rows = []
for _, r in o.iterrows():
    title = str(r.제목)
    if not include_title.search(title) or exclude_title.search(title):
        continue
    fs = body_files.get(str(r.alrNo), [])
    if not fs:
        continue
    t = re.sub(r'\s+', ' ', open(fs[0], encoding='utf-8', errors='ignore').read())
    k = t.find('관리책임부서명')
    body = t[k:] if k > 0 else t
    found = None
    for m in re.finditer(r'(운행\s*시간|운영\s*시간|이용\s*시간|운행시간대)', body):
        win = body[m.start():m.start() + 260]
        a = korean_time_range.search(win)
        b = colon_time_range.search(win) or colon_word_range.search(win)
        c = conditional_service.search(win)
        if a:
            found = (
                '고정',
                hour_24(a.group(1), a.group(2)),
                hour_24(a.group(3) or (a.group(1) if a.group(1) == '오후' else None), a.group(4)),
                win[:200]
            )
            break
        if b:
            found = (
                '고정',
                int(b.group(1)),
                int(b.group(3) if b.re is colon_time_range else b.group(2)),
                win[:200]
            )
            break
        if c:
            found = ('조건부', None, None, win[:200])
            break
    if not found:
        c = conditional_service.search(body)
        if c and '막차' in body[max(0, c.start() - 80):c.end()]:
            found = ('조건부', None, None, body[max(0, c.start() - 80):c.end() + 40])
    if found:
        rows.append({
            'alrNo': r.alrNo,
            '시도': r.시도,
            '제목': title,
            '유형': found[0],
            '시작': found[1],
            '종료': found[2],
            '예외문구': bool(re.search('다만|달리 정할|협의하여|조정할 수', found[3])),
            '원문': found[3],
            '파일': os.path.basename(fs[0])
        })
d = pd.DataFrame(rows).drop_duplicates('제목')
f = d[d.유형 == '고정']
d.to_csv(ROOT / '데이터' / '가공' / '통합' / '조례_운행시각_v3.csv', index=False, encoding='utf-8-sig')
print('운행시각 조례', len(d), '유형', d.groupby('유형').size().to_dict())
print('고정 운행 종료 시각', f['종료'].value_counts().sort_index().to_dict())
