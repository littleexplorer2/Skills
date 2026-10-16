"""Native LaTeX output isolation and failure protection."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import build_pdf as r
class PipelineTests(unittest.TestCase):
 def data(self):
  return json.loads((Path(__file__).resolve().parents[1]/'samples/demo_summary.json').read_text())
 def test_separate_source_and_checks_are_isolated(self):
  d=self.data();first=copy.deepcopy(d['lectures'][0]);second=copy.deepcopy(first);second['id']='OTHER';second['title']='Other'
  first['self_checks']=[{'question':'FIRSTONLY','answer':'Answer'}];second['self_checks']=[{'question':'SECONDONLY','answer':'Answer'}]
  d['lectures']=[first,second];tex=r.summary_tex(d,[first]);self.assertIn('FIRSTONLY',tex);self.assertNotIn('SECONDONLY',tex)
 def test_body_text_is_escaped_and_math_is_native(self):
  self.assertEqual(r.rich('**A&B**'),r'\textbf{A\&B}')
  self.assertIn(r'\frac{a}{b}',r.rich(r'$$\frac{a}{b}$$'))
  self.assertNotIn('svg',r.rich(r'$x_1$'))
 def test_compile_failure_preserves_previous_final(self):
  d=self.data()
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)/'output';target=r.output_paths(d,root)[0];target.parent.mkdir(parents=True);target.write_bytes(b'previous')
   with patch.object(r,'compile_tex',side_effect=RuntimeError('compile failed')),self.assertRaises(RuntimeError):
    r.build(d,root,overwrite=True)
   self.assertEqual(target.read_bytes(),b'previous')
 def test_group_failure_does_not_publish_partial_outputs(self):
  d=self.data();d['settings']['layout']='separate';d.pop('self_checks',None);d.pop('cross_lecture_links',None)
  first=d['lectures'][0];second=copy.deepcopy(first);second['id']='L99';d['lectures']=[first,second]
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)/'output'
   with patch.object(r,'compile_tex',side_effect=[b'pdf',RuntimeError('second failed')]),patch.object(r,'inspect_rendered',return_value={'errors':[]}),self.assertRaises(RuntimeError):r.build(d,root)
   self.assertTrue(all(not p.exists() for p in r.output_paths(d,root)))
 def test_nonsilent_math_and_equation_grouping(self):
  with self.assertRaises(ValueError):r.rich('$x\ny$')
  tex=r.rich('$$x=1$$\n$$y=2$$')
  self.assertEqual(tex.count(r'\begin{gather*}'),1)
  self.assertIn(r'\\',tex)
if __name__=='__main__':unittest.main()
