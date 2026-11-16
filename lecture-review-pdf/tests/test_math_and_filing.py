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
  self.assertEqual(r.output_paths(d,Path('outputs'))[0],Path('outputs/lecture-review-pdf/IERG4190/IERG4190__01__StudyGuide.pdf'))
  d['mode']='cheat'
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190__01__CheatSheet.pdf')
 def test_combined_scope_distinguishes_ranges_from_lists(self):
  d=self.data();d['meta']['course_code']='IERG4190';d['lectures']=d['lectures'][:1]
  first=d['lectures'][0]
  d['lectures']=[{**first,'id':f'S03_{number:02d}'} for number in (1,2,3,4)]
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190__03.01-03.04__StudyGuide.pdf')
  d['lectures']=[{**first,'id':f'L{number:02d}'} for number in (1,3)]
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190__01+03__StudyGuide.pdf')
  d['lectures']=[{**first,'id':identity} for identity in ('T01','S03_01')]
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190__01+03.01__StudyGuide.pdf')
  d['lectures']=[{**first,'id':identity} for identity in ('3.99','4.00')]
  self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,'IERG4190__03.99+04.00__StudyGuide.pdf')
 def test_numeric_scope_aliases_and_padding_preserve_source_ids(self):
  d=self.data();d['lectures']=d['lectures'][:1]
  for identity,scope in [('L1','01'),('T01','01'),('Chapter 001','01'),('S3_1','03.01'),('Section 03.01','03.01'),('3.1','03.01'),('100','100')]:
   with self.subTest(identity=identity):
    d['lectures'][0]['id']=identity;before=copy.deepcopy(d)
    self.assertEqual(r.output_paths(d,Path('outputs'))[0].name,f'DEMO101__{scope}__StudyGuide.pdf')
    self.assertEqual(d,before)
 def test_unconfirmed_or_malformed_scope_is_rejected(self):
  for identity in ('ExamScope','S03__01','01-04','01+03','../01','1.','1..2'):
   with self.subTest(identity=identity):
    d=self.data();d['lectures']=d['lectures'][:1];d['lectures'][0]['id']=identity
    with self.assertRaisesRegex(ValueError,'numeric'):r.validate(d)
    with self.assertRaisesRegex(ValueError,'numeric'):r.output_paths(d,Path('outputs'))
 def test_numeric_aliases_cannot_collide(self):
  for layout in ('combined','separate'):
   with self.subTest(layout=layout):
    d=self.data();d['settings']['layout']=layout;d.pop('self_checks',None);d.pop('cross_lecture_links',None)
    first=d['lectures'][0];d['lectures']=[{**first,'id':identity} for identity in ('T1','L01')]
    with self.assertRaisesRegex(ValueError,'colliding'):r.validate(d)
    with self.assertRaisesRegex(ValueError,'colliding'):r.output_paths(d,Path('outputs'))
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
