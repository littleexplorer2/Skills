#!/usr/bin/env python3
"""Read-only XeLaTeX and PDF-checker diagnostics; installs nothing."""
import argparse, importlib.metadata, json, shutil, subprocess, sys
from pathlib import Path
from build_pdf import find_engine

def inspect_environment():
 errors=[];packages={};engine=None
 try:engine=find_engine()
 except RuntimeError as e:errors.append(str(e))
 try:packages['PyMuPDF']=importlib.metadata.version('PyMuPDF')
 except importlib.metadata.PackageNotFoundError:errors.append('Missing PyMuPDF; install requirements.txt with this Python interpreter')
 latex_packages={}
 if engine:
  kpse=Path(engine).parent/('kpsewhich.exe' if sys.platform=='win32' else 'kpsewhich')
  candidate=str(kpse) if kpse.is_file() else shutil.which('kpsewhich')
  if candidate:
   from install_runtime import RESOURCES
   for name in RESOURCES:
    p=subprocess.run([candidate,name],capture_output=True,text=True,timeout=10);latex_packages[name]=bool(p.stdout.strip())
    if not latex_packages[name]:errors.append('Missing TeX resource: '+name)
  else:errors.append('kpsewhich missing; cannot verify TeX packages')
 return {'ok':not errors,'python':sys.executable,'xelatex':engine,'packages':packages,'tex_resources':latex_packages,'errors':errors}

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--json',action='store_true');a=p.parse_args();r=inspect_environment()
 print(json.dumps(r,indent=2) if a.json else ('PASS' if r['ok'] else 'FAIL')+'\n'+'\n'.join(r['errors']));return 0 if r['ok'] else 1
if __name__=='__main__':raise SystemExit(main())
