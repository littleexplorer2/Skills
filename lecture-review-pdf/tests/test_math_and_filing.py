"""Regression checks for unified math output and cross-platform course paths."""
import base64
import copy
import json
from pathlib import Path
import re
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_pdf as r
class UnifiedTests(unittest.TestCase):
 def data(self):
  return json.loads((Path(__file__).resolve().parents[1]/'samples/demo_summary.json').read_text())
 def test_confirmed_course_required(self):
  for code in ['', '../oops', 'A/B', '中文', 'CON', 'COM1']:
   d=self.data();d['meta']['course_code']=code
   with self.assertRaises(ValueError):r.validate(d)
 def test_naming_across_modes(self):
  d=self.data();d['meta']['course_code']='IERG4190';d['lectures']=d['lectures'][:1];d['lectures'][0]['id']='T01'
  self.assertEqual(r.output_paths(d,Path('outputs'))[0],Path('outputs/lecture-review-pdf/IERG4190/IERG4190_T01_StudyGuide.pdf'))
  d['mode']='cheat'
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190_T01_CheatSheet.pdf')
 def test_math_stays_native_latex(self):
  result=r.rich(r'$$X(\omega)=\int_{-\infty}^{\infty}x(t)e^{-j\omega t}\,dt$$')
  self.assertIn(r'\begin{gather*}',result)
  self.assertIn(r'\int_{-\infty}^{\infty}',result)
  self.assertNotIn('svg',result)
 def test_broken_math_delimiters_fail(self):
  for text in ['$x', '$x\ny$']:
   with self.subTest(text=text),self.assertRaises(ValueError):r.rich(text)
 def test_text_cannot_inject_latex_commands(self):
  self.assertEqual(r.esc(r'\input{secret}'),r'\textbackslash{}input\{secret\}')
  with self.assertRaises(ValueError):r.rich(r'$\input{secret}$')
 def test_plaintext_formula_not_allowed(self):
  d=self.data();d['lectures'][0]['concept_entries'][0]['formula']='X_k=e^(jw)'
  with self.assertRaises(ValueError):r.validate(d)
if __name__=='__main__':unittest.main()
