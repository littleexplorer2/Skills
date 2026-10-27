"""Synthetic PDF regression tests; these do not establish source/print fidelity."""
from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import check_pdf
import pymupdf


def fixture_pdf(font=7.2, size=(595.2756, 841.8898), pages=1, extra=None):
    with pymupdf.open() as document:
        for _ in range(pages):
            page = document.new_page(width=size[0], height=size[1])
            page.insert_text((30, 50), 'Synthetic fixture with sufficient extractable test text.', fontsize=font)
            if extra:
                extra(page)
        return document.tobytes()


def input_data():
    return {
        'mode': 'cheat', 'meta': {'title': 'Synthetic checker fixture', 'course_code': 'TEST101'},
        'settings': {'sides': 'single', 'orientation': 'portrait', 'columns': 2,
                     'font_profile': 'dense', 'language': 'en'},
        'lectures': [{'id': 'L1', 'title': 'Fixture', 'source_name': 'synthetic.pdf',
                      'concept_entries': [{'heading': 'Fixture', 'source_pages': 'p. 1',
                                           'cheat_text': 'Synthetic content for the checker test.'}]}],
    }


class InspectTests(unittest.TestCase):
    def check_cheat(self, source, **options):
        settings = dict(mode='cheat', sides='single', min_font=7.2)
        settings.update(options)
        return check_pdf.inspect_pdf(source, **settings)

    def test_exact_floor_passes_and_reports_range(self):
        report = self.check_cheat(fixture_pdf())
        self.assertEqual(report['errors'], [])
        self.assertEqual(report['pages'], 1)
        self.assertEqual((report['font_min'], report['font_max']), (7.2, 7.2))

    def test_below_approved_floor_is_failure(self):
        report = self.check_cheat(fixture_pdf(font=7.0))
        self.assertTrue(any('small font' in error for error in report['errors']))

    def test_only_rounding_tolerance_is_allowed(self):
        self.assertFalse(self.check_cheat(fixture_pdf(font=7.19))['errors'])
        self.assertTrue(self.check_cheat(fixture_pdf(font=7.17))['errors'])

    def test_nonfinite_and_boolean_options_are_rejected(self):
        for key in ('min_font', 'margin_mm'):
            for value in (float('nan'), float('inf'), -float('inf'), True, '7.2', 10 ** 400):
                with self.subTest(key=key, value=value):
                    self.assertTrue(self.check_cheat(fixture_pdf(), **{key: value})['errors'])

    def test_cheat_constraints_are_explicit(self):
        for settings in ({'sides': None}, {'min_font': None}, {'min_font': 6.5}, {'margin_mm': 105}):
            with self.subTest(settings=settings):
                self.assertTrue(self.check_cheat(fixture_pdf(), **settings)['errors'])

    def test_page_count_and_paper_size(self):
        self.assertTrue(self.check_cheat(fixture_pdf(pages=2))['errors'])
        self.assertTrue(self.check_cheat(fixture_pdf(size=(612, 792)))['errors'])
        self.assertFalse(self.check_cheat(fixture_pdf(pages=2), sides='duplex')['errors'])

    def test_landscape_and_rotated_pages(self):
        landscape = fixture_pdf(size=(841.8898, 595.2756))
        self.assertFalse(self.check_cheat(landscape, orientation='landscape')['errors'])
        with pymupdf.open(stream=fixture_pdf(), filetype='pdf') as document:
            document[0].set_rotation(90)
            rotated = document.tobytes()
        self.assertFalse(self.check_cheat(rotated, orientation='landscape')['errors'])

    def test_off_page_text_is_not_hidden_by_clipped_extraction(self):
        data = fixture_pdf(extra=lambda page: page.insert_text((-80, 100), 'Entire off-page text', fontsize=7.2))
        self.assertTrue(any('outside page bounds' in error for error in self.check_cheat(data)['errors']))

    def test_optional_printable_margin(self):
        data = fixture_pdf(extra=lambda page: page.insert_text((3, 100), 'Inside page but outside margin', fontsize=7.2))
        self.assertFalse(self.check_cheat(data)['errors'])
        self.assertTrue(any('printable margin' in error for error in self.check_cheat(data, margin_mm=4.8)['errors']))

    def test_missing_glyph_is_reported(self):
        def unsupported_text(page):
            page.insert_font(fontname='fixture', fontbuffer=pymupdf.Font('helv').buffer)
            page.insert_text((30, 100), '\u4e2d', fontname='fixture', fontsize=7.2)

        report = self.check_cheat(fixture_pdf(extra=unsupported_text))
        self.assertTrue(any('missing glyph' in error or 'replacement' in error for error in report['errors']), report)

    def test_blank_corrupt_missing_and_encrypted_inputs(self):
        with pymupdf.open() as document:
            document.new_page(width=595.2756, height=841.8898)
            blank = document.tobytes()
        self.assertTrue(any('little/no' in error for error in self.check_cheat(blank)['errors']))
        self.assertTrue(self.check_cheat(b'not a PDF')['errors'])
        self.assertTrue(self.check_cheat(Path('missing-checker-fixture.pdf'))['errors'])
        with pymupdf.open(stream=fixture_pdf(), filetype='pdf') as document:
            encrypted = document.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, owner_pw='owner', user_pw='user')
        self.assertTrue(any('password' in error for error in self.check_cheat(encrypted)['errors']))

    def test_summary_rejects_ignored_orientation_and_sides(self):
        self.assertTrue(check_pdf.inspect_pdf(fixture_pdf(), 'summary', orientation='landscape')['errors'])
        self.assertTrue(check_pdf.inspect_pdf(fixture_pdf(), 'summary', sides='single')['errors'])
        self.assertTrue(check_pdf.inspect_pdf(fixture_pdf(), 'summary', min_font=8)['errors'])


class CommandTests(unittest.TestCase):
    def test_help_does_not_require_site_packages(self):
        result = subprocess.run([sys.executable, '-S', str(Path(check_pdf.__file__)), '--help'],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_required_options(self):
        for options in ([], ['--mode', 'cheat'], ['--mode', 'cheat', '--sides', 'single'],
                        ['--mode', 'cheat', '--sides', 'single', '--orientation', 'portrait']):
            with self.subTest(options=options), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as failure:
                    check_pdf._arguments(['fixture.pdf', *options])
                self.assertEqual(failure.exception.code, 2)

    def test_json_input_settings_shared_with_renderer(self):
        data = input_data()
        expected = check_pdf.expected_settings(data)
        self.assertEqual(expected['min_font'], 7.2)
        self.assertEqual(expected['margin_mm'], 3.0)
        data['settings']['min_font_pt'] = 7.5
        data['settings']['margin_mm'] = 5.0
        expected = check_pdf.expected_settings(data)
        self.assertEqual(expected['min_font'], 7.5)
        self.assertEqual(expected['margin_mm'], 5.0)

    def test_conflicting_cli_and_json_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.json'
            source.write_text(json.dumps(input_data()), encoding='utf-8-sig')
            base = ['fixture.pdf', '--input', str(source)]
            _args, expected = check_pdf._arguments(base)
            self.assertEqual(expected['mode'], 'cheat')
            for option, value in (('--mode', 'summary'), ('--sides', 'duplex'), ('--orientation', 'landscape'),
                                  ('--min-font', '6.6'), ('--margin-mm', '5.0')):
                with self.subTest(option=option), redirect_stderr(io.StringIO()):
                    with self.assertRaises(SystemExit) as failure:
                        check_pdf._arguments([*base, option, value])
                    self.assertEqual(failure.exception.code, 2)

    def test_json_report_has_stable_fields_and_failure_status(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / 'input.pdf'
            source.write_bytes(fixture_pdf(font=7.0))
            args = [str(source), '--mode', 'cheat', '--sides', 'single', '--orientation', 'portrait',
                    '--min-font', '7.2', '--json']
            first, second = io.StringIO(), io.StringIO()
            with redirect_stdout(first):
                self.assertEqual(check_pdf.main(args), 1)
            with redirect_stdout(second):
                self.assertEqual(check_pdf.main(args), 1)
            self.assertEqual(first.getvalue(), second.getvalue())
            report = json.loads(first.getvalue())
            self.assertEqual(set(report), {'errors', 'pages', 'font_min', 'font_max'})
            self.assertTrue(report['errors'])


if __name__ == '__main__':
    unittest.main()
