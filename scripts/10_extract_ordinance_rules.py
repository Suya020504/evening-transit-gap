"""저장된 조례 본문에서 대상·연령·지원 조건을 정규식으로 추출한다.
입력은 자치법규_ELIS/list_relevant.csv와 body/*.txt다.
출력은 데이터/가공/조례790_규칙추출.csv다.
"""
from pathlib import Path
import csv
import re
import collections

ROOT = Path(__file__).resolve().parents[1]

source_dir = ROOT / '데이터' / '원천_PC다운로드' / '자치법규_ELIS'
output_dir = ROOT / '데이터' / '가공'
province_names = [
    '서울특별시',
    '부산광역시',
    '대구광역시',
    '인천광역시',
    '광주광역시',
    '대전광역시',
    '울산광역시',
    '세종특별자치시',
    '경기도',
    '강원특별자치도',
    '강원도',
    '충청북도',
    '충청남도',
    '전북특별자치도',
    '전라북도',
    '전라남도',
    '경상북도',
    '경상남도',
    '제주특별자치도'
]
rows = list(csv.DictReader(open(source_dir / 'list_relevant.csv', encoding='utf-8-sig')))
extracted_rules = []
for r in rows:
    f = source_dir / 'body' / f"{r['alrNo']}_{r['histNo']}.txt"
    if not f.exists():
        continue
    t = f.read_text(encoding='utf-8', errors='ignore')
    m = re.search(r'제1조\s*\(목적\)\s*이\s', t)
    body = t[m.start():] if m else ''
    # 개정 이력의 조건이 섞이지 않도록 본문 뒤 부칙을 제외한다.
    k = body.rfind('\n부칙')
    if k > 0:
        body = body[:k]
    meta = r['제목_지자체_공포일_부서']
    title = meta.split(' 조례')[0] + ' 조례' if ' 조례' in meta else meta[:40]
    sido = next((s for s in province_names if s in meta), '')
    cat = '어르신' if re.search('어르신|노인|경로', title) else '청소년·아동' if re.search('청소년|아동|학생|어린이', title) else '장애인' if '장애인' in title else '택시형' if re.search('택시', title) else '농어촌·소외' if re.search('농어촌|소외|오지|벽지|마을', title) else '기타'
    ages = [int(a) for a in re.findall(r'(\d{2})세\s*이상', body)]
    age = collections.Counter(ages).most_common(1)[0][0] if ages else None
    extracted_rules.append({
        'alrNo': r['alrNo'],
        '시도': sido,
        '제목': title,
        '분류': cat,
        '본문추출': bool(body),
        '본문길이': len(body),
        '최빈연령기준': age,
        '금액문구': bool(re.search(r'\d[\d,]*\s*원', body)),
        '예산범위위임': bool(re.search(r'예산의?\s*범위', body)),
        '관내한정문구': bool(re.search(r'관내|관할\s*구역', body)),
        '관외인접문구': bool(re.search(r'관외|인접|다른\s*(시|군|지방자치단체)', body)),
        '교통카드': '교통카드' in body,
        '수요응답': bool(re.search('수요응답', body))
    })
output_dir.mkdir(exist_ok=True)
with open(output_dir / '조례790_규칙추출.csv', 'w', newline='', encoding='utf-8-sig') as fo:
    w = csv.DictWriter(fo, fieldnames=list(extracted_rules[0].keys()))
    w.writeheader()
    w.writerows(extracted_rules)
old = [o for o in extracted_rules if o['분류'] == '어르신' and re.search('교통', o['제목'])]
bys = collections.defaultdict(collections.Counter)
for o in old:
    bys[o['시도']][o['최빈연령기준']] += 1
print(
    '추출 조례',
    len(extracted_rules),
    '본문 추출',
    sum((o['본문추출'] for o in extracted_rules)),
    '분류',
    dict(collections.Counter((o['분류'] for o in extracted_rules)))
)
print(
    '어르신 교통 조례',
    len(old),
    '연령',
    dict(collections.Counter((o['최빈연령기준'] for o in old))),
    '시도별 연령',
    {s: dict(c) for s, c in sorted(bys.items())}
)
