"""Machine-local runtime discovery. Nothing in this module installs software."""
import json,os,shutil,sys
from pathlib import Path

def runtime_dir():
 if sys.platform=='win32':return Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))/'LectureReviewPDF'
 if sys.platform=='darwin':return Path.home()/'Library/Application Support/LectureReviewPDF'
 return Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local/share'))/'LectureReviewPDF'

def runtime_python():
 return runtime_dir()/'venv'/('Scripts/python.exe' if sys.platform=='win32' else 'bin/python')

def read_config():
 try:return json.loads((runtime_dir()/'runtime.json').read_text(encoding='utf-8'))
 except (OSError,ValueError):return {}

def find_xelatex(explicit=None):
 selected=explicit or os.environ.get('LECTURE_REVIEW_XELATEX')
 if selected:
  resolved=shutil.which(selected) or selected
  if Path(resolved).is_file():return str(Path(resolved).absolute())
  raise RuntimeError('Configured XeLaTeX does not exist: '+selected)
 configured=read_config().get('xelatex')
 candidates=[configured,shutil.which('xelatex')]
 if sys.platform=='darwin':candidates += ['/Library/TeX/texbin/xelatex']
 if sys.platform=='win32':
  for root in [os.environ.get('LOCALAPPDATA',''),os.environ.get('ProgramFiles','')]:
   if root:
    candidates += [str(Path(root)/'Programs/MiKTeX/miktex/bin/x64/xelatex.exe'),str(Path(root)/'MiKTeX/miktex/bin/x64/xelatex.exe')]
  drive=os.environ.get('SystemDrive','C:')
  candidates += [str(p) for p in sorted(Path(drive+'/texlive').glob('*/bin/windows/xelatex.exe'),reverse=True)]
 for p in candidates:
  if p and Path(p).is_file():return str(Path(p).absolute())
 raise RuntimeError('XeLaTeX missing. Run Install.command on macOS or Install-Windows.cmd on Windows.')
