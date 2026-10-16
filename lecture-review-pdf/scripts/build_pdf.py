#!/usr/bin/env python3
"""Render structured lecture JSON into selectable study guides or A4 exam sheets.
Dependencies: weasyprint, pymupdf. No font files are bundled. CJK fonts must exist
on the host. Overflow in cheat mode is an error, NOT an excuse to omit content.
"""
from __future__ import annotations
import argparse
import html
import json
import math
import re
import sys
from pathlib import Path

FONTS = "'Noto Sans CJK SC', 'Noto Sans SC', 'Microsoft YaHei', 'PingFang SC', 'WenQuanYi Micro Hei', sans-serif"
PROFILES = {
    'comfortable': (8.2, 9.0),
    'dense': (7.2, 8.2),
    'ultra': (6.6, 7.2),
}
DEFAULT_CHEAT_MARGIN_MM = 4.8
SUMMARY_MIN_FONT_PT = 7.7
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

def esc(v):
    return html.escape(str(v or ''), quote=True)

@__import__('functools').lru_cache(maxsize=2048)
def math_svg(tex, display=False):
    # Paths embed the math font outlines, independent of the PDF viewer fonts.
    import base64, io
    try:
        import matplotlib
        matplotlib.use('svg')
        from matplotlib.mathtext import math_to_image
        from matplotlib.font_manager import FontProperties
    except ImportError as exc:
        raise RuntimeError('Math rendering requires matplotlib; install requirements.txt') from exc
    buf = io.BytesIO()
    try:
        with matplotlib.rc_context({'svg.fonttype': 'path', 'mathtext.fontset': 'stix', 'savefig.transparent': True}):
            math_to_image('$' + (tex.strip().replace(r'\frac',r'\dfrac') if display else tex.strip()) + '$', buf,
                          prop=FontProperties(size=11), format='svg')
    except Exception as exc:
        raise ValueError(f'Invalid/unsupported math: {tex!r}: {exc}') from exc
    svg = buf.getvalue()
    header = svg.decode().split('<svg', 1)[1].split('>', 1)[0]
    w = float(re.search(r'width="([\d.]+)pt"', header).group(1))
    h = float(re.search(r'height="([\d.]+)pt"', header).group(1))
    src = base64.b64encode(svg).decode()
    cls = 'math-display' if display else 'math-inline'
    return f'<img class="{cls}" src="data:image/svg+xml;base64,{src}" alt="{esc(tex)}" style="width:{w/11:.5f}em;height:{h/11:.5f}em;vertical-align:middle"/>'

def rich(v):
    value = str(v or '')
    if value.count('$') % 2:
        raise ValueError('Unmatched math delimiter')
    parts = re.split(r'(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)', value)
    result = []
    for part in parts:
        if part.startswith('$$') and part.endswith('$$'):
            result.append('<div class="math-block">'+math_svg(part[2:-2], True)+'</div>')
        elif part.startswith('$') and part.endswith('$'):
            result.append(math_svg(part[1:-1]))
        else:
            if '$' in part:
                raise ValueError('Unmatched or multiline inline math delimiter')
            t = esc(part)
            t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
            result.append(t.replace('\n', '<br>'))
    joined=''.join(result)
    joined=joined.replace('</div><br>', '</div>').replace('<br><div class="math-block">', '<div class="math-block">')
    return joined

def source_span(s):
    return f'<span class="src">{esc(s)}</span>' if s else ''

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

def html_frame(title, body, style, language):
    lang = 'en' if language == 'en' else 'zh-CN'
    return f'''<!doctype html><html lang="{lang}"><head><meta charset="utf-8"/>
    <title>{esc(title)}</title><style>{style}</style></head><body>{body}</body></html>'''

def summary_style():
    return f'''
@page {{ size: A4; margin: 15mm 15mm 16mm; @bottom-center {{ content: counter(page); color:#777; font-size:8pt; }} }}
* {{ box-sizing:border-box; }}
body {{ font-family:{FONTS}; color:#20342f; font-size:10.15pt; line-height:1.56; }}
.cover {{ border-top:4px solid #1b8468; padding-top:3mm; margin-bottom:4mm; }}
h1 {{font-size:23pt; line-height:1.25; color:#174c40; margin:0 0 6mm; letter-spacing:.1px;overflow-wrap:anywhere;}}
.subtitle {{font-size:11pt;color:#566b63;margin:0 0 3mm;}}
.meta {{font-size:9pt;color:#61766f;}}
.overview {{background:#edf6f1;padding:3.5mm 4.3mm;border-radius:2mm;}}
.part {{font-size:15pt; padding-top:2mm;margin:3mm 0 5mm;border-bottom:1.3pt solid #228067; color:#145943;break-before:page;}}
.part.first {{break-before:auto; margin-top:5mm;}}
.lecture {{font-size:13pt; color:#185d4a; margin:7mm 0 3.5mm; border-bottom:.6pt solid #cddbd4; break-after:avoid;}}
.q {{font-weight:700; margin:2.4mm 0;}}
.step {{border-left:2pt solid #329077; background:#f5f9f7; padding:1.7mm 3mm; margin:1.5mm 0; break-inside:avoid;}}
.step .step-title {{font-weight:700;color:#165e4d;}}
.concept {{border-bottom:.45pt solid #d7e0db; padding:2mm 0 2.4mm; break-inside:avoid;}}
.term {{font-weight:700;color:#174a40; font-size:10.5pt;}}
.src {{display:inline;color:#6d7e76;font-size:7.7pt;overflow-wrap:anywhere;margin-left:2mm;font-weight:normal;}}
.piece {{margin:.9mm 0;}}
.piece strong {{color:#174c40;}}
.formula {{font-family:{FONTS};font-weight:650; background:#eff3f1; padding:2mm 2.4mm; margin:1.4mm 0; white-space:normal;}}
.tag {{font-size:7.7pt; padding:.3mm 1.2mm; border:1px solid #c6d7d0; border-radius:1mm; margin-left:1mm;}}
.link {{break-inside:avoid;line-height:1.4;padding:1mm 0;border-bottom:.4pt solid #dae2de;}}
table {{width:100%;border-collapse:collapse;font-size:9.1pt;margin:2mm 0;}}
th,td {{border-bottom:.5pt solid #d9e4dd;padding:1mm 2mm;text-align:left;vertical-align:top;}}
th {{background:#eaf3ee;color:#1e5a49;}}
p {{margin:1mm 0;}}
.math-block {{margin:1mm 0;break-inside:avoid;}}
.math-inline {{margin:0 .12em;}}
.self-heading {{break-before:page;}}
'''

def render_summary_html(d, lectures):
    m=d['meta']
    labels = LABELS[d['settings']['language']]
    parts=[f'''<div class="cover"><p class="meta">{esc(m.get('course',labels['course']))}</p><h1>{esc(m.get('title',labels['title']))}</h1><p class="subtitle">{esc(m.get('subtitle',labels['subtitle']))}</p><p class="overview">{esc(m.get('source_note',labels['source_note']))}</p></div>''']
    parts.append(f'<h2 class="part first">{labels["logic"]}</h2>')
    for l in lectures:
        if len(lectures)>1:
            parts.append(f'<h3 class="lecture">{esc(l["id"])} · {esc(l["title"])} {source_span(l["source_name"])}</h3>')
        if l.get('core_question'):parts.append(f'<p class="q">{labels["question"]}: {rich(l["core_question"])}</p>')
        if l.get('overview'):parts.append(f'<p>{rich(l["overview"])}</p>')
        for k,step in enumerate(l.get('logic_steps',[]),1):
            parts.append(f'''<div class="step"><div class="step-title">{k:02d} · {esc(step.get('heading',''))}{source_span(step.get('source_pages',''))}</div><div>{rich(step.get('detail',''))}</div></div>''')
    parts.append(f'<h2 class="part">{labels["ideas"]}</h2>')
    for l in lectures:
        parts.append(f'<h3 class="lecture">{esc(l["id"])} · {esc(l["title"])}</h3>')
        for e in l.get('concept_entries',[]):
            parts.append('<div class="concept">')
            parts.append(f'<div class="term">{esc(e.get("heading",""))}{source_span(e.get("source_pages",""))}'+(f'<span class="tag">{labels["priority"]} {esc(e["priority"])}</span>' if e.get('priority') else '')+'</div>')
            if e.get('details'):parts.append(f'<div class="piece">{rich(e["details"])}</div>')
            if e.get('keywords'):parts.append(f'<div class="piece"><strong>{labels["keywords"]}: </strong>{esc(" / ".join(e["keywords"]))}</div>')
            if e.get('formula'):parts.append(f'<div class="formula">{rich(e["formula"])}</div>')
            for field in ('example', 'caution'):
                if e.get(field): parts.append(f'<div class="piece"><strong>{labels[field]}: </strong>{rich(e[field])}</div>')
            parts.append('</div>')
        parts.extend(self_check_html(l.get('self_checks', []), labels))
    if d.get('cross_lecture_links'):
        parts.append(f'<h3 class="lecture">{labels["connections"]}</h3>')
        parts.extend(f'<div class="link">{rich(v)}</div>' for v in d['cross_lecture_links'])
    parts.extend(self_check_html(d.get('self_checks', []), labels))
    return html_frame(m.get('title',labels['title']),''.join(parts),summary_style(),d['settings']['language'])


def self_check_html(checks, labels):
    if not checks:
        return []
    parts = [f'<h3 class="lecture self-heading">{labels["self_checks"]}</h3>']
    for i, check in enumerate(checks, 1):
        parts.append(f'<div class="link"><b>{i}. {rich(check["question"])}</b><div>{rich(check["answer"])}</div></div>')
    return parts

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

def item_html(item):
    text=rich(item['text'])
    # Keep every formula on the exam sheet even if the author forgot to repeat it in cheat_text.
    if item['formula'] and item['formula'] not in item['text']:
        text += f'<div class="eq">{rich(item["formula"])}</div>'
    return f'''<section class="entry"><div class="eh">{esc(item['lecture'])} · {esc(item['topic'])}
    <span class="ref">{esc(item['pages'])}</span></div><div class="et">{text}</div></section>'''

def cheat_css(font_size, settings):
    orient=settings['orientation'];n=settings['columns']
    margin_mm=float(settings.get('margin_mm', DEFAULT_CHEAT_MARGIN_MM))
    if not 4.0 <= margin_mm <= 12.0:
        raise ValueError('A4 print margin must be between 4 and 12 mm; if printer requires more, ask user')
    return f'''
@page {{ size: A4 {orient}; margin:{margin_mm}mm; }}
* {{box-sizing:border-box;}}
html,body {{margin:0; padding:0;}}
body {{ font-family:{FONTS};font-size:{font_size:.2f}pt; line-height:1.15; color:#111; background:white; }}
.sheet {{ break-after:page; }}
.sheet:last-child {{break-after:auto;}}
.source-key {{margin-bottom:1.15mm;overflow-wrap:anywhere;}}
.chead {{ min-height:5.0mm; border-bottom:.4pt solid #222; margin-bottom:1.15mm; display:flex; justify-content:space-between; align-items:center; gap:2mm; font-size:{font_size+.35:.2f}pt; font-weight:700; }}
.chead span:first-child {{min-width:0;overflow-wrap:anywhere;}}
.chead span:last-child {{flex-shrink:0;}}
.columns {{ column-count:{n};column-gap:2.8mm; column-rule:.25pt solid #bbb; column-fill:balance; }}
.entry {{ break-inside:avoid; padding:0 0 1mm; margin:0 0 1.05mm; border-bottom:.22pt solid #aaa; }}
.eh {{font-size:{font_size+.25:.2f}pt; font-weight:700; margin:0 0 .45mm; break-after:avoid;}}
.ref {{font-weight:400;font-size:{font_size:.2f}pt;color:#555;display:block;overflow-wrap:anywhere;}}
.et {{line-height:1.15;overflow-wrap:anywhere;}}
strong {{font-weight:750;}}
.eq {{font-weight:700;margin-top:.35mm;overflow-wrap:anywhere;}}
p {{margin:0;}}
'''

def cheat_html(d, font_size):
    pages=split_two(cheat_items(d)) if d['settings']['sides']=='duplex' else [cheat_items(d)]
    pieces=[]
    labels = LABELS[d['settings']['language']]
    for i,items in enumerate(pages):
        tag=f'{labels["front" if i==0 else "back"]} · {i+1}/{len(pages)}'
        present_ids = {item['lecture'] for item in items}
        sources = '; '.join(f'{lecture["id"]} = {lecture["source_name"]}'
                            for lecture in d['lectures'] if lecture['id'] in present_ids)
        source_key = f'<div class="source-key">{labels["sources"]}: {esc(sources)}</div>'
        pieces.append(f'<div class="sheet"><div class="chead"><span>{esc(d["meta"].get("course",""))} · {esc(d["meta"].get("title",labels["cheat_title"]))}</span><span>A4 · {tag}</span></div>{source_key}<div class="columns">'+''.join(item_html(x) for x in items)+'</div></div>')
    return html_frame(d['meta'].get('title',labels['cheat_title']),''.join(pieces),cheat_css(font_size,d['settings']),d['settings']['language'])

def render_pdf(html_text):
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise RuntimeError('WeasyPrint is unavailable: check requirements.txt and the platform runtime instructions; --validate-only needs no renderer dependencies') from exc
    return HTML(string=html_text).write_pdf()


def inspect_rendered(pdf_bytes, **settings):
    from check_pdf import inspect_pdf
    return inspect_pdf(pdf_bytes, **settings)


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


def render_summary(d, output, *, overwrite=False, input_path=None):
    paths = output_paths(d, output)
    preflight_outputs(paths, input_path, overwrite)
    groups = [d['lectures']] if d['settings']['layout'] == 'combined' else [[lec] for lec in d['lectures']]
    pending = []
    for target, lectures in zip(paths, groups):
        content = render_pdf(render_summary_html(d, lectures))
        result = inspect_rendered(content, mode='summary', orientation='portrait', min_font=SUMMARY_MIN_FONT_PT)
        if result['errors']:
            raise RuntimeError(f'Structural PDF check failed for {target}: ' + '; '.join(result['errors']))
        pending.append((target, content))
    # All members of a separate summary pass before the first final PDF is written.
    preflight_outputs(paths, input_path, overwrite)
    for target, content in pending:
        save_pdf(target, content, overwrite=overwrite, input_path=input_path)
        print(f'CREATED: {target}; structural checks passed (source accuracy and print readability still need review)')


def font_candidates(low, high):
    font = high
    while font > low + 1e-8:
        yield round(font, 4)
        font = round(font - .2, 4)
    yield low


def render_cheat(d, output, *, overwrite=False, input_path=None):
    output=output_paths(d,output)[0]
    preflight_outputs([output], input_path, overwrite)
    setting=d['settings'];mi,ma=resolve_font_bounds(setting)
    wanted=1 if setting['sides']=='single' else 2
    # Probe sizes from largest to smallest, without violating user-approved minimum.
    attempts=[]
    for font in font_candidates(mi, ma):
        content=render_pdf(cheat_html(d,font))
        result=inspect_rendered(content, mode='cheat', sides=setting['sides'],
                                orientation=setting['orientation'], min_font=mi,
                                margin_mm=setting.get('margin_mm', DEFAULT_CHEAT_MARGIN_MM))
        attempts.append((round(font, 4), result['pages'], result['errors']))
        if not result['errors']:
            save_pdf(output, content, overwrite=overwrite, input_path=input_path)
            print(f'CREATED: {output}; {result["pages"]} A4 page(s), font {font:.2f}pt, profile {setting["font_profile"]}; structural checks passed (source accuracy and print readability still need review)')
            return
    raise RuntimeError(f'CHEAT SHEET FAILED FIT/STRUCTURAL CHECKS: expected exactly {wanted} page(s), '
                       f'font floor {mi}pt; attempts(font pt, pages, errors)={attempts}. '
                       'DO NOT silently delete topics/shrink below floor/increase pages. '
                       'Ask user to choose editorial compression, duplex, alternate orientation, columns or explicit ultra profile.')

def main(argv=None):
    a=argparse.ArgumentParser(description='Render source-authored lecture JSON, or validate it without PDF dependencies.')
    a.add_argument('--input',required=True,type=Path)
    a.add_argument('--output',type=Path)
    a.add_argument('--validate-only',action='store_true',help='Validate JSON/schema only; do not load PDF dependencies or write files')
    a.add_argument('--overwrite',action='store_true',help='Allow replacement of existing output PDFs, never the input file')
    args=a.parse_args(argv)
    if args.validate_only and (args.output is not None or args.overwrite):
        a.error('--validate-only cannot be combined with --output or --overwrite')
    if not args.validate_only and args.output is None:
        a.error('--output is required unless --validate-only is used')
    d=json.loads(args.input.read_text(encoding='utf-8-sig'))
    validate(d)
    if args.validate_only:
        print(f'VALID: {args.input}; schema only, not source accuracy or rendered layout')
        return
    if d['mode']=='summary': render_summary(d,args.output,overwrite=args.overwrite,input_path=args.input)
    else: render_cheat(d,args.output,overwrite=args.overwrite,input_path=args.input)

if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError) as ex:
        print('ERROR:',ex,file=sys.stderr);sys.exit(2)
