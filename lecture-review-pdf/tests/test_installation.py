"""Installer behavior without downloading software or modifying the host."""
import json,os,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch,Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import runtime_paths as paths
import install_runtime as setup
class InstallerTests(unittest.TestCase):
 def test_engine_symlink_is_preserved_for_latex_format(self):
  with tempfile.TemporaryDirectory() as folder:
   binary=Path(folder)/'xetex';binary.touch();entry=Path(folder)/'xelatex'
   try:entry.symlink_to(binary)
   except OSError:self.skipTest('symlink creation unavailable')
   self.assertEqual(paths.find_xelatex(str(entry)),str(entry))
 def test_bad_explicit_engine_does_not_silently_select_other_engine(self):
  with self.assertRaises(RuntimeError):paths.find_xelatex('/nonexistent/configured/xelatex')
 def test_complete_tex_install_skips_package_changes(self):
  with patch.object(setup,'missing_tex',return_value=[]),patch.object(setup,'run') as run:
   setup.install_tex('xelatex');run.assert_not_called()
 def test_miktex_installs_only_missing_packages_and_rechecks(self):
  with patch.object(setup,'missing_tex',side_effect=[['ctexart.cls','FandolSong-Regular.otf'],[]]),patch.object(setup,'manager_command',return_value=('miktex','miktex.exe',['ctex','fandol'])),patch.object(setup,'sibling',return_value=None),patch.object(setup,'run') as run:
   setup.install_tex('xelatex.exe')
   self.assertEqual(run.call_args_list[1].args[0],['miktex.exe','packages','install','ctex','fandol'])
 def test_unfixed_resources_fail_instead_of_claiming_ready(self):
  with patch.object(setup,'missing_tex',return_value=['ctexart.cls']),patch.object(setup,'manager_command',return_value=('miktex','miktex.exe',['ctex'])),patch.object(setup,'sibling',return_value=None),patch.object(setup,'run'),self.assertRaises(RuntimeError):setup.install_tex('xelatex.exe')
 def test_check_only_never_creates_environment(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch.object(setup,'runtime_python',return_value=Path(folder)/'missing'),patch.object(setup.venv,'EnvBuilder') as create,self.assertRaises(RuntimeError):setup.main(['--check-only'])
   create.assert_not_called()
 def test_skill_install_excludes_caches_and_handles_spaces(self):
  with tempfile.TemporaryDirectory() as folder:
   src=Path(folder)/'source skill';dst=Path(folder)/'installed skill';src.mkdir();(src/'SKILL.md').write_text('test');(src/'__pycache__').mkdir();(src/'__pycache__/test.pyc').touch()
   setup.install_skill(src,dst)
   self.assertEqual((dst/'SKILL.md').read_text(),'test');self.assertFalse((dst/'__pycache__').exists())
 def test_failed_smoke_test_never_saves_ready_config_or_installs_skill(self):
  with tempfile.TemporaryDirectory() as folder:
   with patch.object(setup,'runtime_dir',return_value=Path(folder)/'runtime'),patch.object(setup,'runtime_python',return_value=Path(folder)/'python'),patch.object(setup,'ensure_python_packages'),patch.object(setup,'find_xelatex',return_value='xelatex'),patch.object(setup,'install_tex'),patch.object(setup,'smoke_test',side_effect=RuntimeError('bad PDF')),patch.object(setup,'install_skill') as install,self.assertRaises(RuntimeError):setup.main(['--inside'])
   self.assertFalse((Path(folder)/'runtime/runtime.json').exists());install.assert_not_called()
 def test_resources_cover_color_chinese_math_and_fonts(self):
  self.assertEqual(setup.RESOURCES['multicol.sty'],'tools')
  self.assertEqual(setup.RESOURCES['xcolor.sty'],'xcolor')
  self.assertIn('FandolHei-Regular.otf',setup.RESOURCES)
if __name__=='__main__':unittest.main()
