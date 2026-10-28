import re

REGIONS = ('东区', '西区', '中区', '广东区')
OFFICES = {'浙北': ('杭州', '绍兴', '嘉兴', '湖州'), '浙南': ('上海', '宁波', '温州', '丽水', '金华', '台州'), '江苏': ('江苏',)}


def region_identity(value):
    text = str(value or '').strip()
    if not text or text in ('/', '未填写', '未标注', '区域待确认', '归属待核验'):
        return '', ''
    text = re.sub(r'[—－/]', '-', text)
    for office, cities in OFFICES.items():
        if text in cities or any(text == city + '市' for city in cities) or text in (office, f'{office}办事处', f'东区-{office}', f'东区-{office}办事处'):
            return '东区', office
    if text in ('上海作战平台', '上海区'):
        return '东区', '浙南'
    if re.match(r'^东区(?:作战平台|-|$)', text):
        return '东区', ''
    for region in ('西区', '中区'):
        if re.match(r'^' + region + r'(?:作战平台|-|$)', text):
            return region, ''
    if re.match(r'^(广东区?|南区|华南区)(?:作战平台|-|$)', text):
        return '广东区', ''
    return '', ''


def normalize_business_regions(sheets):
    fields = {'区域', '项目归属', '*项目归属', '区域归属', '区域组织', '平台', '作战平台'}
    totals = {'联指', '公司', '公司合计', '合计', '总计', '小计', '全部', '区域合计', '区域总计'}
    result = []
    for sheet in sheets:
        headers = list(sheet.get('headers', []))
        indices = [index for index, header in enumerate(headers) if header in fields]
        if not indices:
            result.append(sheet)
            continue
        originals = headers.index('原区域归属') if '原区域归属' in headers else len(headers)
        normalized = []
        changed = False
        for source in sheet.get('rows', []):
            row = list(source) + [''] * max(0, len(headers) - len(source))
            for index in indices:
                value = str(row[index] or '').strip()
                if not value or value in totals:
                    continue
                region, office = region_identity(value)
                target = f'{region}-{office}' if office else region or '归属待核验'
                if target == value:
                    continue
                if len(row) <= originals:
                    row.extend([''] * (originals + 1 - len(row)))
                if not row[originals]:
                    row[originals] = value
                row[index] = target
                changed = True
            normalized.append(row)
        if changed and originals == len(headers):
            headers.append('原区域归属')
        result.append({**sheet, 'headers': headers, 'rows': [row + [''] * max(0, len(headers) - len(row)) for row in normalized]})
    return result
