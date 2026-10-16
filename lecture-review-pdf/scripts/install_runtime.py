#!/usr/bin/env python3
"""Shared setup after the platform bootstrap installs Python and a TeX engine."""
import argparse,importlib.metadata,json,os,shutil,subprocess,sys,tempfile,venv
from pathlib import Path
from runtime_paths import runtime_dir,runtime_python,find_xelatex

SKILL=Path(__file__).resolve().parents[1]
RESOURCES={
 'ctexart.cls':'ctex','xeCJK.sty':'xecjk','fontspec.sty':'fontspec',
 'amsmath.sty':'amsmath','amssymb.sty':'amsfonts','geometry.sty':'geometry',
 'xcolor.sty':'xcolor','needspace.sty':'needspace','enumitem.sty':'enumitem',
 'multicol.sty':'tools','fancyhdr.sty':'fancyhdr','hyperref.sty':'hyperref',
 'FandolSong-Regular.otf':'fandol','FandolHei-Regular.otf':'fandol',
}

def run(args,**kwargs):
 print('Running: '+' '.join(map(str,args)),flush=True)
 return subprocess.run(list(map(str,args)),check=True,**kwargs)

def sibling(engine,name):
 for suffix in (['.exe','.bat',''] if sys.platform=='win32' else ['']):
  p=Path(engine).parent/(name+suffix)
  if p.is_file():return str(p)
 return shutil.which(name)

def missing_tex(engine):
 kpse=sibling(engine,'kpsewhich')
 if not kpse:raise RuntimeError('kpsewhich not found beside XeLaTeX; repair the TeX distribution.')
 missing=[]
 for name in RESOURCES:
  p=subprocess.run([kpse,name],capture_output=True,text=True,timeout=20)
  if p.returncode or not p.stdout.strip():missing.append(name)
 return missing

def manager_command(engine,missing):
 version=subprocess.run([engine,'--version'],capture_output=True,text=True,timeout=20)
 if 'miktex' in (version.stdout+version.stderr).lower():
  manager=sibling(engine,'miktex')
  if not manager:raise RuntimeError('MiKTeX package manager missing.')
  return 'miktex',manager,sorted(set(RESOURCES[x] for x in missing))
 manager=sibling(engine,'tlmgr')
 if not manager:raise RuntimeError('tlmgr missing; cannot install missing TeX resources.')
 packages=sorted(set(RESOURCES[x] for x in missing))
 return 'texlive',manager,packages

def install_tex(engine):
 missing=missing_tex(engine)
 if not missing:return
 print('Missing TeX resources: '+', '.join(missing),flush=True)
 kind,manager,packages=manager_command(engine,missing)
 if kind=='miktex':
  run([manager,'packages','update-package-database'],timeout=1800)
  run([manager,'packages','install',*packages],timeout=1800)
  initex=sibling(engine,'initexmf')
  if initex:run([initex,'--set-config-value=[MPM]AutoInstall=yes'],timeout=60)
 else:
  prefix=[]
  if sys.platform=='darwin':
   p=subprocess.run([sibling(engine,'kpsewhich'),'-var-value=TEXMFROOT'],capture_output=True,text=True,check=True)
   if not os.access(p.stdout.strip(),os.W_OK):prefix=['sudo']
  # Dependencies are resolved by tlmgr; do not upgrade the whole distribution.
  run([*prefix,manager,'install',*packages],timeout=1800)
 remaining=missing_tex(engine)
 if remaining:raise RuntimeError('TeX resources still missing: '+', '.join(remaining))

def ensure_python_packages():
 try:
  import pymupdf
  version=tuple(int(x) for x in importlib.metadata.version('PyMuPDF').split('.')[:2])
  if version>=(1,24):return
 except (ImportError,ValueError,importlib.metadata.PackageNotFoundError):pass
 run([sys.executable,'-m','pip','install','-r',SKILL/'requirements.txt'],timeout=1800)

def smoke_test(engine,folder):
 from build_pdf import compile_tex,summary_tex,validate
 from check_pdf import inspect_pdf
 d={'mode':'summary','meta':{'course_code':'SETUP101','title':'安装验证 / Setup check'},'settings':{'layout':'combined','language':'zh-en'},'lectures':[{'id':'T01','title':'Smoke','source_name':'synthetic setup fixture','logic_steps':[{'heading':'中文与 English','detail':'仅验证字体、数学和编译环境，不是课程内容。','source_pages':'synthetic'}],'concept_entries':[{'heading':'原生公式验证','source_pages':'synthetic','details':r'行内公式 $f_s=1/T_s$。','formula':r'$$X(\omega)=\int_{-\infty}^{\infty}x(t)e^{-j\omega t}\,dt$$'+'\n'+r'$$x[n]=\frac{1}{N}\sum_{k=0}^{N-1}X[k]e^{j2\pi kn/N}$$'}]}]}
 validate(d);pdf=compile_tex(summary_tex(d,d['lectures']),folder,engine)
 report=inspect_pdf(pdf,mode='summary',orientation='portrait',min_font=5)
 if report['errors']:raise RuntimeError('Setup PDF failed: '+'; '.join(report['errors']))
 import pymupdf
 with pymupdf.open(stream=pdf,filetype='pdf') as document:
  text=''.join(page.get_text() for page in document)
  if '安装验证' not in text or '原生公式验证' not in text:
   raise RuntimeError('Setup PDF did not preserve expected Chinese text.')
 return report

def install_skill(source=SKILL,destination=None):
 destination=destination or Path.home()/'.agents/skills/lecture-review-pdf'
 if source.resolve()==destination.resolve():return destination
 shutil.copytree(source,destination,dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.DS_Store','.venv'))
 return destination

def main(argv=None):
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--inside',action='store_true',help=argparse.SUPPRESS);p.add_argument('--check-only',action='store_true');p.add_argument('--no-install-skill',action='store_true');a=p.parse_args(argv)
 if sys.version_info<(3,10):raise RuntimeError('Python 3.10 or newer is required.')
 python=runtime_python()
 if not a.inside:
  if a.check_only:
   if not python.is_file():raise RuntimeError('Skill Python environment is not installed.')
   return subprocess.call([str(python),str(Path(__file__).resolve()),'--inside','--check-only'])
  if not python.is_file():
   print('Creating isolated Python environment: '+str(python.parent),flush=True)
   venv.EnvBuilder(with_pip=True).create(runtime_dir()/'venv')
  opts=['--inside']+(['--no-install-skill'] if a.no_install_skill else [])
  return subprocess.call([str(python),str(Path(__file__).resolve()),*opts])
 if a.check_only:
  from check_environment import inspect_environment
  report=inspect_environment();print(json.dumps(report,ensure_ascii=False,indent=2));return 0 if report['ok'] else 1
 ensure_python_packages();engine=find_xelatex();install_tex(engine)
 repo=SKILL.parent if (SKILL.parent/'AGENTS.md').is_file() else None
 logs=(repo/'.tmp/lecture-review-pdf/setup') if repo else runtime_dir()/'setup-logs'
 logs.mkdir(parents=True,exist_ok=True);job=Path(tempfile.mkdtemp(prefix='verify-',dir=logs))
 report=smoke_test(engine,job)
 # Machine-specific absolute paths never enter the Git repository.
 cfg={'python':str(python),'xelatex':engine,'repo_root':str(repo) if repo else None,'smoke_test':str(job),'pdf_check':report}
 runtime_dir().mkdir(parents=True,exist_ok=True)
 (runtime_dir()/'runtime.json').write_text(json.dumps(cfg,ensure_ascii=False,indent=2),encoding='utf-8')
 if not a.no_install_skill:print('Skill installed: '+str(install_skill()),flush=True)
 print('READY: Chinese and native LaTeX math compiled successfully.\nLogs: '+str(job),flush=True)
 return 0
if __name__=='__main__':
 try:raise SystemExit(main())
 except (RuntimeError,OSError,subprocess.SubprocessError) as e:print('SETUP FAILED: '+str(e),file=sys.stderr);raise SystemExit(1)
