"""Validated content contract and output protection, shared by the LaTeX renderer and PDF checker."""

import math, re

from pathlib import Path

PROFILES = {
    'comfortable': (8.2, 9.0),
    'dense': (7.2, 8.2),
    'ultra': (6.6, 7.2),
}

DEFAULT_CHEAT_MARGIN_MM = 4.8

SUMMARY_MIN_FONT_PT = 5.0

LANGUAGES = ('en', 'zh', 'zh-en')

LABELS = {
    'en': {
        'course': 'Course study guide', 'title': 'Lecture Review',
        'subtitle': 'Lecture logic + Exam concepts',
        'source_note': 'Based on supplied course materials. References identify original source pages.',
        'coverage': 'Coverage', 'logic': 'PART I · Teaching Logic',
        'ideas': 'PART II · Key Ideas and Exam Review', 'question': 'Core question',
        'priority': 'Priority', 'keywords': 'Keywords', 'example': 'Example',
        'caution': 'Pitfall', 'connections': 'Connections', 'self_checks': 'Self Check',
        'cheat_title': 'Cheat Sheet', 'front': 'FRONT', 'back': 'BACK', 'sources': 'Sources',
    },
    'zh': {
        'course': '课程复习资料', 'title': '课程复习', 'subtitle': '讲解逻辑与考试概念',
        'source_note': '根据提供的课程资料整理；出处页码对应原始资料。',
        'coverage': '覆盖范围', 'logic': '第一部分 · 课程内容与讲解逻辑',
        'ideas': '第二部分 · 重要概念与考试复习', 'question': '核心问题',
        'priority': '优先级', 'keywords': '关键词', 'example': '例子', 'caution': '易错点',
        'connections': '跨讲联系', 'self_checks': '临考自测',
        'cheat_title': '考试速查表', 'front': '正面', 'back': '背面', 'sources': '来源',
    },
    'zh-en': {
        'course': '课程复习资料 / Course study guide', 'title': '课程复习 / Lecture Review',
        'subtitle': '讲解逻辑与考试概念 / Lecture logic + Exam concepts',
        'source_note': '根据提供的课程资料整理；出处页码对应原始资料。 / References identify original source pages.',
        'coverage': '覆盖范围 / Coverage', 'logic': 'PART I · 课程内容与讲解逻辑 / Teaching Logic',
        'ideas': 'PART II · 重要概念与考试复习 / Key Ideas', 'question': '核心问题 / Core question',
        'priority': '优先级 / Priority', 'keywords': '关键词 / Keywords',
        'example': '例子 / Example', 'caution': '易错点 / Pitfall',
        'connections': '跨讲联系 / Connections', 'self_checks': '临考自测 / Self Check',
        'cheat_title': '考试速查表 / Cheat Sheet', 'front': '正面 / FRONT', 'back': '背面 / BACK', 'sources': '来源 / Sources',
    },
}

def require(obj, key, typ, path='$', *, optional=False, nonempty=False):
    field = f'{path}.{key}'
    if key not in obj:
        if optional:
            return
        raise ValueError(f'{field}: required field is missing')
    if type(obj[key]) is not typ:
        raise ValueError(f'{field}: expected {typ.__name__}, got {type(obj[key]).__name__}')
    if nonempty and not obj[key].strip():
        raise ValueError(f'{field}: must not be empty')

def object_fields(value, path, allowed):
    if not isinstance(value, dict):
        raise ValueError(f'{path}: expected object, got {type(value).__name__}')
    unknown = set(value) - set(allowed)
    if unknown:
        raise ValueError(f'{path}: unknown field(s): {", ".join(sorted(unknown))}')

def string_fields(obj, fields, path, *, required=False):
    for key in fields:
        require(obj, key, str, path, optional=not required, nonempty=required)

def validate_checks(checks, path):
    if not isinstance(checks, list):
        raise ValueError(f'{path}: expected list')
    for i, check in enumerate(checks):
        p = f'{path}[{i}]'
        object_fields(check, p, ('question', 'answer'))
        string_fields(check, ('question', 'answer'), p, required=True)

def finite_number(value, path):
    try:
        valid = type(value) in (float, int) and math.isfinite(value)
    except OverflowError:
        valid = False
    if not valid:
        raise ValueError(f'{path}: expected finite number')
    return float(value)

def resolve_font_bounds(settings):
    low, high = PROFILES[settings['font_profile']]
    if 'min_font_pt' in settings:
        requested = finite_number(settings['min_font_pt'], '$.settings.min_font_pt')
        if not low <= requested <= high:
            raise ValueError(f'$.settings.min_font_pt: must be between {low} and {high} for the selected profile')
        low = requested
    return low, high

def validate(d):
    object_fields(d, '$', ('mode', 'meta', 'settings', 'lectures', 'cross_lecture_links', 'self_checks'))
    require(d,'mode',str)
    require(d,'lectures',list)
    if not d['lectures']:
        raise ValueError('Must include at least one lecture')
    require(d,'settings',dict)
    require(d,'meta',dict)
    if d['mode'] not in ('summary','cheat'):
        raise ValueError('$.mode: must be summary or cheat')
    object_fields(d['meta'], '$.meta', ('title', 'course', 'course_code', 'subtitle', 'source_note'))
    string_fields(d['meta'], ('title', 'course', 'course_code', 'subtitle', 'source_note'), '$.meta')
    code=d['meta'].get('course_code','')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9-]{1,31}', code) or re.fullmatch(r'(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])',code):
        raise ValueError('meta.course_code must contain the confirmed course code (e.g. IERG4190)')
    if 'cross_lecture_links' in d:
        require(d, 'cross_lecture_links', list)
        for i, link in enumerate(d['cross_lecture_links']):
            if not isinstance(link, str) or not link.strip():
                raise ValueError(f'$.cross_lecture_links[{i}]: expected nonempty string')
    if 'self_checks' in d:
        validate_checks(d['self_checks'], '$.self_checks')
    ids = set()
    for i, lec in enumerate(d['lectures']):
        p = f'$.lectures[{i}]'
        object_fields(lec, p, ('id', 'title', 'source_name', 'core_question', 'overview', 'logic_steps', 'concept_entries', 'self_checks'))
        for k in ('id','title','source_name'):
            require(lec,k,str,p,nonempty=True)
        identity = lec['id'].strip()
        if identity in ids:
            raise ValueError(f'{p}.id: duplicate lecture ID {identity!r}')
        ids.add(identity)
        string_fields(lec, ('core_question', 'overview'), p)
        for key in ('logic_steps', 'concept_entries'):
            require(lec, key, list, p, optional=True)
        if 'self_checks' in lec:
            validate_checks(lec['self_checks'], p + '.self_checks')
        if not lec.get('concept_entries') and not lec.get('logic_steps'):
            raise ValueError(f'{p}: must include at least one logic step or concept entry')
        if d['mode'] == 'cheat' and not lec.get('concept_entries'):
            raise ValueError(f'{p}.concept_entries: each cheat lecture requires at least one concept entry')
        for j, step in enumerate(lec.get('logic_steps', [])):
            q = f'{p}.logic_steps[{j}]'
            object_fields(step, q, ('heading', 'detail', 'source_pages'))
            string_fields(step, ('heading', 'detail', 'source_pages'), q, required=True)
        for j, entry in enumerate(lec.get('concept_entries', [])):
            q = f'{p}.concept_entries[{j}]'
            object_fields(entry, q, ('heading', 'details', 'keywords', 'formula', 'example', 'caution', 'priority', 'source_pages', 'cheat_text', 'page'))
            string_fields(entry, ('heading', 'source_pages'), q, required=True)
            string_fields(entry, ('details', 'formula', 'example', 'caution', 'priority', 'cheat_text'), q)
            if d['mode'] == 'summary' and not any(entry.get(k, '').strip() for k in ('details', 'formula', 'example', 'caution')):
                raise ValueError(f'{q}: summary entry needs details, formula, example or caution')
            raw=re.sub(r'\$\$[\s\S]+?\$\$|\$[^$\n]+?\$', '', entry.get('formula',''))
            if re.search(r'[_^]|[∫Σ∑]', raw):
                raise ValueError(f'{q}.formula: use math delimiters for mathematical notation')
            if 'keywords' in entry:
                require(entry, 'keywords', list, q)
                for k, keyword in enumerate(entry['keywords']):
                    if not isinstance(keyword, str) or not keyword.strip():
                        raise ValueError(f'{q}.keywords[{k}]: expected nonempty string')
            if entry.get('page') is not None and (type(entry['page']) is not int or entry['page'] not in (1, 2)):
                raise ValueError(f'{q}.page: must be null, 1 or 2')
            if d['mode'] == 'cheat':
                require(entry, 'cheat_text', str, q, nonempty=True)
                if d['settings'].get('sides') == 'single' and entry.get('page') == 2:
                    raise ValueError(f'{q}.page: page 2 is incompatible with settings.sides=single')
    s=d['settings']
    object_fields(s, '$.settings', ('layout', 'sides', 'orientation', 'columns', 'font_profile', 'language', 'margin_mm', 'min_font_pt'))
    applicable = {'layout', 'language'} if d['mode'] == 'summary' else {'sides', 'orientation', 'columns', 'font_profile', 'language', 'margin_mm', 'min_font_pt'}
    unused = set(s) - applicable
    if unused:
        raise ValueError(f'$.settings: unsupported in {d["mode"]} mode: {", ".join(sorted(unused))}')
    require(s, 'language', str, '$.settings')
    if s['language'] not in LANGUAGES:
        raise ValueError('$.settings.language: must be en, zh or zh-en')
    for key, values in (('layout', ('combined', 'separate')), ('sides', ('single', 'duplex')),
                        ('orientation', ('portrait', 'landscape')), ('font_profile', tuple(PROFILES))):
        if key in s:
            require(s, key, str, '$.settings')
            if s[key] not in values:
                raise ValueError(f'$.settings.{key}: must be one of {", ".join(values)}')
    if 'columns' in s and (type(s['columns']) is not int or s['columns'] not in (2, 3)):
        raise ValueError('$.settings.columns: must be integer 2 or 3')
    if 'margin_mm' in s:
        margin = finite_number(s['margin_mm'], '$.settings.margin_mm')
        if not 4.0 <= margin <= 12.0:
            raise ValueError('$.settings.margin_mm: must be between 4 and 12 mm')
    if 'min_font_pt' in s:
        if 'font_profile' not in s:
            raise ValueError('$.settings.min_font_pt: requires font_profile')
        resolve_font_bounds(s)
    if d['mode']=='cheat':
        if s.get('sides') not in ('single','duplex'):
            raise ValueError('cheat mode requires explicit settings.sides = single|duplex')
        if s.get('orientation') not in ('portrait','landscape'):
            raise ValueError('cheat mode requires explicit settings.orientation = portrait|landscape')
        if s.get('columns') not in (2,3):
            raise ValueError('cheat mode requires explicit settings.columns = 2|3')
        if s.get('font_profile') not in PROFILES:
            raise ValueError('cheat mode requires explicit settings.font_profile = comfortable|dense|ultra')
    elif s.get('layout') not in ('combined','separate'):
        raise ValueError('summary mode requires explicit settings.layout = combined|separate')
    if d['mode'] == 'summary' and s['layout'] == 'separate' and (d.get('cross_lecture_links') or d.get('self_checks')):
        raise ValueError('summary/separate cannot contain nonempty global cross_lecture_links or self_checks; move source-specific checks into lectures[].self_checks or choose combined')
    if d['mode'] == 'cheat':
        items = cheat_items(d)
        if s['sides'] == 'duplex':
            split_two(items)

def cheat_items(d):
    items=[]
    for lec in d['lectures']:
        for entry in lec.get('concept_entries',[]):
            items.append({'lecture':lec['id'], 'topic':entry.get('heading',''), 'text':entry['cheat_text'],
                          'formula':entry.get('formula',''), 'pages':entry.get('source_pages',''),
                          'page':entry.get('page',None)})
    if not items: raise ValueError('No concept entries for cheat sheet')
    return items

def item_weight(item):
    # CJK characters occupy more width; formulas often cost extra line breaks.
    t=item['text']+' '+item['topic']+' '+item['formula']
    han=sum(1 for c in t if '\u3400'<=c<='\u9fff')
    return 55 + 1.3*han + .8*(len(t)-han) + 15*t.count('\n')

def split_two(items):
    user_assigned=[v for v in items if v['page'] is not None]
    if user_assigned:
        for v in user_assigned:
            if v['page'] not in (1,2):raise ValueError('cheat page must be 1 or 2')
        loads = {p: sum(item_weight(v) for v in items if v['page'] == p) for p in (1, 2)}
        pages = {1: [], 2: []}
        for v in items:
            p = v['page']
            if p is None:
                p = min((1, 2), key=lambda face: loads[face])
                loads[p] += item_weight(v)
            pages[p].append(v)
        if not pages[1] or not pages[2]:
            raise ValueError('Duplex requires content on both faces; revise concept_entries[].page assignments')
        return [pages[1],pages[2]]
    if len(items)<2:
        raise ValueError('Duplex requires at least two concept entries; provide content for both faces')
    cumulative=[]; running=0
    for i in items[:-1]:
        running+=item_weight(i);cumulative.append(running)
    half=(running+item_weight(items[-1]))/2
    split=min(range(1,len(items)),key=lambda i:abs(cumulative[i-1]-half))
    return [items[:split],items[split:]]

def output_paths(d, output):
    if output.suffix.lower() == '.pdf':
        raise ValueError('--output is the shared Skills repository output directory, not a PDF filename')
    code=d['meta']['course_code']
    def clean(value):
        value=re.sub('[^A-Za-z0-9_-]+', '_', value).strip('_')
        if not value:
            raise ValueError('Lecture ID must contain letters or digits for file naming')
        return value
    scopes=[clean(x['id']) for x in d['lectures']]
    if d['mode']=='summary' and d['settings']['layout']=='separate':
        names=[f'{code}_{scope}_StudyGuide.pdf' for scope in scopes]
    else:
        kind='StudyGuide' if d['mode']=='summary' else 'CheatSheet'
        names=[f'{code}_{"-".join(scopes)}_{kind}.pdf']
    if len(set(x.casefold() for x in names)) != len(names):
        raise ValueError('Lecture IDs produce colliding filenames')
    return [output/'lecture-review-pdf'/code/name for name in names]

def paths_alias(left, right):
    if left.resolve() == right.resolve():
        return True
    return left.exists() and right.exists() and left.samefile(right)

def preflight_outputs(paths, input_path=None, overwrite=False):
    for target in paths:
        if input_path is not None and paths_alias(target, input_path):
            raise ValueError(f'Output aliases input: {target}; choose a different destination')
        if target.exists():
            if not target.is_file():
                raise ValueError(f'Output is not a regular file: {target}')
            if not overwrite:
                raise ValueError(f'Output already exists: {target}; use --overwrite only to intentionally replace it')
        for parent in target.parents:
            if parent.exists():
                if not parent.is_dir():
                    raise ValueError(f'Output parent is not a directory: {parent}')
                break

def save_pdf(path, content, *, overwrite=False, input_path=None):
    preflight_outputs([path], input_path, overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('wb' if overwrite else 'xb') as stream:
        stream.write(content)

def font_candidates(low, high):
    font = high
    while font > low + 1e-8:
        yield round(font, 4)
        font = round(font - .2, 4)
    yield low
