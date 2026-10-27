#!/usr/bin/env python3
"""Compile validated lecture JSON with XeLaTeX. No HTML or SVG math backend."""
from __future__ import annotations
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from content_model import *

UNICODE_MATH = {
 'ω':r'\omega','Ω':r'\Omega','π':r'\pi','δ':r'\delta','τ':r'\tau',
 'α':r'\alpha','φ':r'\phi','θ':r'\theta','λ':r'\lambda','ρ':r'\rho',
 'ℓ':r'\ell','Σ':r'\Sigma','∑':r'\sum','∫':r'\int','∞':r'\infty',
 '→':r'\to','↔':r'\leftrightarrow','≤':r'\leq','≥':r'\geq','≠':r'\ne',
 '≈':r'\approx','×':r'\times','÷':r'\div','−':'-','½':r'\frac{1}{2}',
 '′':r'{}^{\prime}','⟨':r'\langle','⟩':r'\rangle',
}
ESCAPES={'\\':r'\textbackslash{}','{':r'\{','}':r'\}','%':r'\%','&':r'\&',
 '#':r'\#','_':r'\_','^':r'\textasciicircum{}','~':r'\textasciitilde{}','$':r'\$'}
MATH_RE = re.compile(r'(\$\$[\s\S]+?\$\$|\$[^$\n]+?\$)')
FORBIDDEN_MATH = re.compile(r'\\(?:input|include|write\w*|open\w*|read|catcode|csname|def|gdef|edef|let|usepackage|documentclass|special|directlua|immediate|endinput)\b')

def esc(value):
    result=[]
    for c in str(value or ''):
        if c in UNICODE_MATH:result.append(r'\ensuremath{'+UNICODE_MATH[c]+'}')
        elif '₀' <= c <= '₉':result.append(r'\ensuremath{_{'+str(ord(c)-ord('₀'))+'}}')
        elif c in '⁰¹²³⁴⁵⁶⁷⁸⁹':result.append(r'\ensuremath{^{'+str('⁰¹²³⁴⁵⁶⁷⁸⁹'.index(c))+'}}')
        else:result.append(ESCAPES.get(c,c))
    return ''.join(result)

def rich(value, *, compact=False):
    """Escape prose, preserve explicit LaTeX math, reject incomplete delimiters."""
    result=[]
    for part in MATH_RE.split(str(value or '')):
        if MATH_RE.fullmatch(part):
            display=part.startswith('$$');tex=part[2:-2] if display else part[1:-1]
            if FORBIDDEN_MATH.search(tex):raise ValueError('Only mathematical LaTeX is allowed in math fields')
            result.append(('\n\\[\n'+tex+'\n\\]\n') if display else r'\('+tex+r'\)')
        else:
            if '$' in part:raise ValueError('Unmatched or multiline inline math delimiter')
            bits=re.split(r'(\*\*.+?\*\*)',part,flags=re.S)
            text=''.join(r'\textbf{'+esc(x[2:-2])+'}' if x.startswith('**') and x.endswith('**') else esc(x) for x in bits)
            result.append(text.replace('\n', '\n\\par\n'))
    joined=''.join(result)
    # Consecutive display expressions share a gather environment and one spacing block.
    joined=re.sub(r'\\\]\s*(?:\\par\s*)?\\\[', lambda m:r'\\', joined)
    joined=joined.replace(r'\[',r'\begin{gather*}').replace(r'\]',r'\end{gather*}')
    if compact:
        # Authoring newlines around a display are layout boundaries, not empty
        # prose paragraphs. Retain normal paragraph breaks elsewhere.
        joined=re.sub(r'(?:\s*\\par\s*)?(\\begin\{gather\*\})', lambda m:'\n'+m[1], joined)
        joined=re.sub(r'(\\end\{gather\*\})(?:\s*\\par\s*)?', lambda m:m[1]+'\n', joined)
    return joined

def preamble(d,font=10.15):
    cheat=d['mode']=='cheat';s=d['settings'];margin=s.get('margin_mm',DEFAULT_CHEAT_MARGIN_MM) if cheat else 17
    landscape=',landscape' if cheat and s['orientation']=='landscape' else ''
    leading=font*(1.14 if cheat else 1.48)
    # Cheat subscripts retain the chosen floor instead of being silently reduced.
    mathsize=(rf'\DeclareMathSizes{{{font}}}{{{font}}}{{{font}}}{{{font}}}' if cheat else '')
    compact=(r'''
\xeCJKsetup{PunctStyle=plain}
\setlength{\parskip}{0.5pt}
\setlength{\abovedisplayskip}{1.5pt}
\setlength{\belowdisplayskip}{1.5pt}
\setlength{\abovedisplayshortskip}{0.5pt}
\setlength{\belowdisplayshortskip}{0.5pt}
\setlength{\jot}{1pt}
\setlength{\columnsep}{3mm}
\setlength{\columnseprule}{0.2pt}
\setlength{\multicolsep}{0pt}
\raggedcolumns
''' if cheat else '')
    return r'''\documentclass[UTF8,fontset=fandol,10pt,a4paper]{ctexart}
\usepackage{amsmath,amssymb,geometry,xcolor,needspace,enumitem,multicol,fancyhdr,hyperref}
\geometry{margin='''+str(margin)+'mm'+landscape+r'''}
\definecolor{accent}{HTML}{185D4A}
\hypersetup{hidelinks}
\setlength{\parindent}{0pt}
\setlength{\parskip}{'''+('1.1pt' if cheat else '3pt')+r'''}
\setlength{\emergencystretch}{2em}
\setlength{\abovedisplayskip}{5pt}
\setlength{\belowdisplayskip}{5pt}
\setlength{\abovedisplayshortskip}{3pt}
\setlength{\belowdisplayshortskip}{3pt}
\allowdisplaybreaks[1]
\raggedbottom
\setlength{\headheight}{14pt}
\pagestyle{'''+('empty' if cheat else 'fancy')+r'''}
\fancyhf{}
\fancyhead[L]{\fontsize{8}{10}\selectfont '''+esc(d['meta']['course_code'])+r'''}
\fancyhead[R]{\fontsize{8}{10}\selectfont '''+esc(d['meta'].get('title','Lecture Review'))+r'''}
\fancyfoot[C]{\fontsize{8}{10}\selectfont\thepage}
\renewcommand{\headrulewidth}{0.3pt}
\newcommand{\topic}[2]{\par\Needspace{5\baselineskip}\vspace{5pt}{\color{accent}\bfseries #1}\quad{\fontsize{8}{10}\selectfont\color{gray}#2}\par\nobreak\vspace{1pt}}
\newcommand{\parttitle}[1]{\par\Needspace{7\baselineskip}\vspace{8pt}{\Large\bfseries\color{accent}#1}\par\nobreak\vspace{3pt}\hrule\vspace{6pt}}
'''+mathsize+'\n'+r'\begin{document}'+'\n'+rf'\fontsize{{{font}}}{{{leading:.3f}}}\selectfont'+'\n'+compact

def checks_tex(checks,labels):
    if not checks:return ''
    parts=[r'\clearpage\begingroup\fontsize{10.15}{13.2}\selectfont',r'\parttitle{'+esc(labels['self_checks'])+'}',r'\begin{enumerate}[leftmargin=*,itemsep=3pt,parsep=0pt]']
    for item in checks:parts += [r'\item \textbf{'+rich(item['question'])+'}\n\n'+rich(item['answer'])+'\n']
    return '\n'.join(parts)+ '\n\\end{enumerate}\n\\endgroup\n'

def summary_tex(d,lectures):
    m=d['meta'];labels=LABELS[d['settings']['language']]
    p=[preamble(d),r'{\LARGE\bfseries\color{accent}'+esc(m.get('title',labels['title']))+r'}\par\vspace{4pt}',
       esc(m.get('subtitle',''))+'\n\n',r'{\small '+rich(m.get('source_note',''))+'}\n',r'\parttitle{'+esc(labels['logic'])+'}']
    for l in lectures:
        if len(lectures)>1:p.append(r'\topic{'+esc(l['id']+' · '+l['title'])+'}{'+esc(l['source_name'])+'}')
        if l.get('core_question'):p.append(r'\textbf{'+esc(labels['question'])+'}: '+rich(l['core_question'])+'\n\n')
        if l.get('overview'):p.append(rich(l['overview'])+'\n\n')
        for i,step in enumerate(l.get('logic_steps',[]),1):
            p.extend([r'\topic{'+esc(f'{i:02} · '+step['heading'])+'}{'+esc(step['source_pages'])+'}',rich(step['detail'])+'\n\n'])
    p += [r'\clearpage',r'\parttitle{'+esc(labels['ideas'])+'}']
    for l in lectures:
        if len(lectures)>1:p.append(r'\topic{'+esc(l['id']+' · '+l['title'])+'}{'+esc(l['source_name'])+'}')
        for e in l.get('concept_entries',[]):
            p.append(r'\par\noindent\begin{minipage}{\linewidth}')
            p.append(r'\topic{'+esc(e['heading'])+'}{'+esc(e['source_pages'])+'}')
            if e.get('details'):p.append(rich(e['details'])+'\n\n')
            if e.get('keywords'):p.append(r'{\small\textbf{'+esc(labels['keywords'])+':} '+esc(' / '.join(e['keywords']))+'}\n\n')
            if e.get('formula'):p.append(rich(e['formula'])+'\n\n')
            for field in ['example','caution']:
                if e.get(field):p.append(r'\textbf{'+esc(labels[field])+':} '+rich(e[field])+'\n\n')
            if e.get('priority'):p.append(r'{\small '+esc(labels['priority']+': '+e['priority'])+'}\n\n')
            p.append(r'\end{minipage}\par\vspace{6pt}')
        p.append(checks_tex(l.get('self_checks',[]),labels))
    if d.get('cross_lecture_links'):
        p.append(r'\parttitle{'+esc(labels['connections'])+'}')
        p.extend(rich(x)+'\n\n' for x in d['cross_lecture_links'])
    p.append(checks_tex(d.get('self_checks',[]),labels))
    return '\n'.join(p)+'\n\\end{document}\n'

def cheat_tex(d,font):
    items=cheat_items(d)
    faces=split_two(items) if d['settings']['sides']=='duplex' else [items]
    p=[preamble(d,font)]
    for i,face in enumerate(faces):
        if i:p.append(r'\clearpage')
        # Source mapping remains in the validated JSON, not on exam paper.
        p.append(r'\begin{multicols}{'+str(d['settings']['columns'])+'}')
        for x in face:
            p.append(r'\par\Needspace{3\baselineskip}\textbf{'+esc(x['topic'])+r'}\par\nobreak'+'\n')
            # Keep a display attached to its preceding paragraph: a blank
            # paragraph here adds a baseline of whitespace before the formula.
            body=rich(x['text'],compact=True).rstrip()
            if x['formula'] and x['formula'] not in x['text']:
                body+='\n'+rich(x['formula'],compact=True).lstrip()
            p.append(body)
        p.append(r'\end{multicols}')
    return '\n'.join(p)+'\n\\end{document}\n'

def find_engine(explicit=None):
    from runtime_paths import find_xelatex
    return find_xelatex(explicit)


def compile_tex(source,folder,engine=None):
    folder.mkdir(parents=True,exist_ok=True);tex=folder/'main.tex';tex.write_text(source,encoding='utf-8')
    exe=find_engine(engine)
    engine_env=os.environ.copy()
    engine_env['PATH']=str(Path(exe).parent)+os.pathsep+engine_env.get('PATH','')
    for run in range(2):
        proc=subprocess.run([exe,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error','-file-line-error','main.tex'],cwd=folder,capture_output=True,timeout=120,env=engine_env)
        (folder/f'compile-{run+1}.txt').write_bytes(proc.stdout+proc.stderr)
        if proc.returncode:raise RuntimeError(f'XeLaTeX failed; inspect {folder}/compile-{run+1}.txt')
    log=(folder/'main.log').read_text(errors='replace')
    overflow=[float(x) for x in re.findall(r'Overfull \\[hv]box \(([\d.]+)pt too (?:wide|high)\)',log)]
    if any(x>1 for x in overflow):raise RuntimeError(f'LaTeX overflow {max(overflow):.2f}pt; fix source/layout, see {folder}/main.log')
    if 'Missing character:' in log:raise RuntimeError(f'Missing LaTeX font glyph; see {folder}/main.log')
    return (folder/'main.pdf').read_bytes()

def inspect_rendered(content,**settings):
    from check_pdf import inspect_pdf
    return inspect_pdf(content,**settings)

def build(d,output,*,temp_root=None,engine=None,overwrite=False,input_path=None):
    paths=output_paths(d,output);preflight_outputs(paths,input_path,overwrite)
    scratch=Path(temp_root) if temp_root else output.parent/'.tmp'/'lecture-review-pdf'
    scratch.mkdir(parents=True,exist_ok=True)
    job=Path(tempfile.mkdtemp(prefix=d['meta']['course_code']+'-',dir=scratch))
    pending=[]
    if d['mode']=='summary':
        groups=[d['lectures']] if d['settings']['layout']=='combined' else [[x] for x in d['lectures']]
        for target,group in zip(paths,groups):
            content=compile_tex(summary_tex(d,group),job/target.stem,engine)
            report=inspect_rendered(content,mode='summary',orientation='portrait',min_font=SUMMARY_MIN_FONT_PT)
            if report['errors']:raise RuntimeError('PDF check failed: '+'; '.join(report['errors']))
            pending.append((target,content))
    else:
        low,high=resolve_font_bounds(d['settings']);attempts=[]
        for font in font_candidates(low,high):
            try:
                content=compile_tex(cheat_tex(d,font),job/f'font-{font:.3f}',engine)
                report=inspect_rendered(content,mode='cheat',sides=d['settings']['sides'],orientation=d['settings']['orientation'],min_font=low,margin_mm=d['settings'].get('margin_mm',DEFAULT_CHEAT_MARGIN_MM))
                if not report['errors']:pending.append((paths[0],content));break
                attempts.append((font,report['errors']))
            except RuntimeError as exc:
                if 'overflow' not in str(exc):raise
                attempts.append((font,str(exc)))
        if not pending:raise RuntimeError(f'Cheat cannot fit within approved constraints: {attempts}; ask user before reducing coverage, floor or changing sides.')
    preflight_outputs(paths,input_path,overwrite)
    for target,content in pending:save_pdf(target,content,overwrite=overwrite,input_path=input_path);print(f'CREATED: {target}')
    print(f'LATEX SOURCES AND LOGS: {job}')

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True,type=Path);p.add_argument('--output',type=Path)
    p.add_argument('--validate-only',action='store_true');p.add_argument('--overwrite',action='store_true')
    p.add_argument('--temp-root',type=Path);p.add_argument('--engine')
    a=p.parse_args(argv)
    if a.validate_only and (a.output or a.overwrite or a.temp_root or a.engine):p.error('--validate-only cannot be combined with generation options')
    if not a.validate_only and a.output is None:p.error('--output is required')
    d=json.loads(a.input.read_text(encoding='utf-8-sig'));validate(d)
    if a.validate_only:print('VALID: schema only');return
    build(d,a.output,temp_root=a.temp_root,engine=a.engine,overwrite=a.overwrite,input_path=a.input)
if __name__=='__main__':
    try:main()
    except (ValueError,RuntimeError,OSError,subprocess.TimeoutExpired) as exc:print('ERROR:',exc,file=sys.stderr);sys.exit(2)
