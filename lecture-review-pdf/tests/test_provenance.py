"""Keep source evidence in authoring data and exam content on printed pages."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_pdf


class ExamPageTests(unittest.TestCase):
    def data(self):
        data = json.loads((ROOT / 'samples' / 'demo_cheat.json').read_text(encoding='utf-8'))
        data['settings'].update(font_profile='comfortable', orientation='landscape', columns=3)
        data['lectures'] = [{
            'id': 'INTERNALID', 'title': 'Authoring topic', 'source_name': 'SOURCE_ONLY.pdf',
            'concept_entries': [
                {'heading': 'Sampling', 'source_pages': 'SOURCE_PAGE_12', 'page': 1,
                 'cheat_text': 'Periods and frequency. BEFORE',
                 'formula': r'$$\text{(F1)}\ T_s=1/f_s,\quad\text{(F2)}\ f_N=f_s/2$$' + '\nAFTER. ' + 'Use F1 to recover the sampling interval. ' * 60},
                {'heading': 'Reconstruction', 'source_pages': 'SOURCE_PAGE_13', 'page': 2,
                 'cheat_text': 'Use consistent units and preserve the sampling condition.',
                 'formula': r'$$x[n]=x(nT_s),\quad f_s>2B$$'}]}]
        return data

    def test_source_evidence_is_required_but_not_printed(self):
        data = self.data()
        before = copy.deepcopy(data)
        build_pdf.validate(data)
        tex = build_pdf.cheat_tex(data, 8.4)
        self.assertEqual(data, before)
        for source in ('SOURCE_ONLY', 'SOURCE_PAGE', 'INTERNALID'):
            self.assertNotIn(source, tex)
        del data['lectures'][0]['concept_entries'][0]['source_pages']
        with self.assertRaises(ValueError):
            build_pdf.validate(data)

    def test_compiled_exam_pages_keep_formulas_compact_and_readable(self):
        try:
            engine = build_pdf.find_engine(None)
        except (RuntimeError, FileNotFoundError):
            self.skipTest('XeLaTeX is not installed')
        import pymupdf
        with tempfile.TemporaryDirectory() as folder:
            pdf = build_pdf.compile_tex(build_pdf.cheat_tex(self.data(), 8.4), Path(folder), engine)
        report = build_pdf.inspect_rendered(pdf, mode='cheat', sides='duplex',
                                           orientation='landscape', min_font=8.2, margin_mm=3)
        self.assertEqual(report['errors'], [])
        with pymupdf.open(stream=pdf, filetype='pdf') as document:
            text = ''.join(page.get_text() for page in document)
            for source in ('SOURCE_ONLY', 'SOURCE_PAGE', 'INTERNALID', 'Demo'):
                self.assertNotIn(source, text)
            first = document[0]
            f1, f2 = first.search_for('(F1)')[0], first.search_for('(F2)')[0]
            self.assertAlmostEqual(f1.y0, f2.y0, delta=0.5)
            self.assertGreater(f2.x0, f1.x1)
            before, after = first.search_for('BEFORE')[0], first.search_for('AFTER')[0]
            self.assertGreater(f1.y0, before.y0)
            self.assertLess(f1.y0 - before.y1, 12)
            self.assertGreater(after.y0, f1.y0)
            self.assertLess(after.y0 - f1.y1, 12)


if __name__ == '__main__':
    unittest.main()
