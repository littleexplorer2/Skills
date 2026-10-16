"""Keep the printed source key aligned with the sources on each face."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_pdf


class PrintedSourcesTests(unittest.TestCase):
    def test_each_face_identifies_its_original_file_without_html_injection(self):
        data = json.loads((ROOT / 'samples' / 'demo_cheat.json').read_text(encoding='utf-8'))
        first = copy.deepcopy(data['lectures'][0])
        second = copy.deepcopy(first)
        first.update(id='A', source_name='alpha<source>.pdf')
        second.update(id='B', source_name='beta&source.pdf')
        first['concept_entries'] = [first['concept_entries'][0]]
        second['concept_entries'] = [second['concept_entries'][1]]
        first['concept_entries'][0]['page'] = 1
        second['concept_entries'][0]['page'] = 2
        data['lectures'] = [first, second]
        build_pdf.validate(data)
        faces = build_pdf.cheat_html(data, 8.2).split('<div class="sheet">')[1:]
        self.assertEqual(len(faces), 2)
        self.assertIn('A = alpha&lt;source&gt;.pdf', faces[0])
        self.assertNotIn('beta&amp;source.pdf', faces[0])
        self.assertIn('B = beta&amp;source.pdf', faces[1])
        self.assertNotIn('alpha&lt;source&gt;.pdf', faces[1])


if __name__ == '__main__':
    unittest.main()
