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
  self.assertEqual(r.output_paths(d,Path('outputs'))[0],Path('outputs/IERG4190_T01_StudyGuide.pdf'))
  d['mode']='cheat'
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190_T01_CheatSheet.pdf')
 def test_typeset_integral_is_embedded_vector_paths(self):
  html=r.rich(r'$$X(\omega)=\int_{-\infty}^{\infty}x(t)e^{-j\omega t}\,dt$$')
  svg=base64.b64decode(re.search('base64,([^" ]+)',html)[1]).decode()
  self.assertIn('<path',svg)
  self.assertNotIn('<text',svg)
  self.assertIn('em;',html)
 def test_broken_math_does_not_silently_render_plain_text(self):
  for text in ['$x', '$x\ny$',r'$\unknowncommand{x}$']:
   with self.subTest(text=text),self.assertRaises(ValueError):r.rich(text)
 def test_adjacent_display_equations_do_not_add_blank_lines(self):
  html=r.rich('$$x^2$$\n$$y_1$$')
  self.assertNotIn('<br>',html)
 def test_plaintext_formula_not_allowed(self):
  d=self.data();d['lectures'][0]['concept_entries'][0]['formula']='X_k=e^(jw)'
  with self.assertRaises(ValueError):r.validate(d)
if __name__=='__main__':unittest.main()
