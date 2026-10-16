"""Schema, content isolation, fitting and output-protection regressions (stdlib only)."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_pdf', ROOT / 'scripts' / 'build_pdf.py')
renderer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(renderer)


def document(mode='summary'):
    return {
        'mode': mode,
        'meta': {'course_code': 'TEST101'},
        'settings': {'layout': 'combined', 'language': 'en'} if mode == 'summary' else {
            'sides': 'single', 'orientation': 'portrait', 'columns': 2,
            'font_profile': 'comfortable', 'language': 'en',
        },
        'lectures': [{
            'id': 'L1', 'title': 'Topic', 'source_name': 'source.pdf',
            'logic_steps': [{'heading': 'Reason', 'detail': 'Because', 'source_pages': 'P1'}],
            'concept_entries': [{'heading': 'Concept', 'details': 'Explanation',
                                 'cheat_text': 'Compact explanation', 'source_pages': 'P2'}],
        }],
    }


class SchemaTests(unittest.TestCase):
    def test_bundled_examples_validate(self):
        for path in (ROOT / 'samples').glob('*.json'):
            with self.subTest(path=path.name):
                renderer.validate(json.loads(path.read_text(encoding='utf-8-sig')))

    def test_root_and_nested_types_report_paths(self):
        with self.assertRaisesRegex(ValueError, r'\$: expected object'):
            renderer.validate([])
        for field, value in [('keywords', 'not-a-list'), ('formula', 3), ('cheat_text', 4)]:
            data = document()
            data['lectures'][0]['concept_entries'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, rf'concept_entries\[0\].{field}'):
                renderer.validate(data)

    def test_invalid_nested_objects_and_lists(self):
        for key, value in [('logic_steps', {}), ('concept_entries', ['wrong']), ('self_checks', [None])]:
            data = document()
            data['lectures'][0][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                renderer.validate(data)

    def test_ids_are_nonempty_and_unique(self):
        for duplicate in ('L1', ' L1 '):
            data = document()
            lecture = copy.deepcopy(data['lectures'][0])
            lecture['id'] = duplicate
            data['lectures'].append(lecture)
            with self.assertRaisesRegex(ValueError, 'duplicate lecture ID'):
                renderer.validate(data)
        data = document()
        data['lectures'][0]['id'] = ' '
        with self.assertRaisesRegex(ValueError, 'must not be empty'):
            renderer.validate(data)

    def test_each_source_bearing_entry_needs_source_pages(self):
        for key in ('logic_steps', 'concept_entries'):
            data = document()
            del data['lectures'][0][key][0]['source_pages']
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'source_pages'):
                renderer.validate(data)

    def test_schema_rejects_unknown_keys_and_missing_language(self):
        data = document()
        data['settings']['langauge'] = 'en'
        with self.assertRaisesRegex(ValueError, 'unknown field'):
            renderer.validate(data)
        del data['settings']['langauge']
        del data['settings']['language']
        with self.assertRaisesRegex(ValueError, 'language'):
            renderer.validate(data)

    def test_numeric_choices_reject_bool_nan_and_out_of_range(self):
        for key, value in [('columns', True), ('margin_mm', float('nan')),
                           ('margin_mm', 0), ('margin_mm', 10**400),
                           ('min_font_pt', 8.0), ('min_font_pt', 9.1)]:
            data = document('cheat')
            data['settings'][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                renderer.validate(data)

    def test_cheat_cannot_silently_omit_a_lecture_without_concepts(self):
        data = document('cheat')
        second = copy.deepcopy(data['lectures'][0])
        second['id'] = 'L2'
        second['concept_entries'] = []
        data['lectures'].append(second)
        with self.assertRaisesRegex(ValueError, 'each cheat lecture requires'):
            renderer.validate(data)

    def test_single_face_refuses_page_two(self):
        data = document('cheat')
        data['lectures'][0]['concept_entries'][0]['page'] = 2
        with self.assertRaisesRegex(ValueError, 'incompatible'):
            renderer.validate(data)

    def test_separate_refuses_global_review_fields(self):
        for key, value in [('cross_lecture_links', ['L1 to L2']),
                           ('self_checks', [{'question': 'Question?', 'answer': 'Answer'}])]:
            data = document()
            data['settings']['layout'] = 'separate'
            data[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'summary/separate'):
                renderer.validate(data)

    def test_unsupported_summary_settings_fail(self):
        data = document()
        data['settings']['orientation'] = 'landscape'
        with self.assertRaisesRegex(ValueError, 'unsupported in summary'):
            renderer.validate(data)

    def test_validation_cli_loads_no_renderer_dependencies(self):
        result = subprocess.run([sys.executable, '-S', str(ROOT / 'scripts' / 'build_pdf.py'),
                                 '--input', str(ROOT / 'samples' / 'demo_summary.json'), '--validate-only'],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('schema only', result.stdout)


class ContentTests(unittest.TestCase):
    def test_labels_match_language_and_author_text_is_preserved(self):
        for language, tag, fixed_label in [('en', 'en', 'Core question'),
                                            ('zh', 'zh-CN', '核心问题'),
                                            ('zh-en', 'zh-CN', '核心问题 / Core question')]:
            data = document()
            data['settings']['language'] = language
            data['lectures'][0]['core_question'] = 'Untranslated author content'
            html = renderer.render_summary_html(data, data['lectures'])
            self.assertIn(f'lang="{tag}"', html)
            self.assertIn(fixed_label, html)
            self.assertIn('Untranslated author content', html)
            if language == 'en':
                self.assertFalse(any('\u3400' <= ch <= '\u9fff' for ch in html))

    def test_separate_summary_only_includes_own_self_checks(self):
        data = document()
        second = copy.deepcopy(data['lectures'][0])
        second['id'] = 'L2'
        data['lectures'].append(second)
        data['settings']['layout'] = 'separate'
        for index, lecture in enumerate(data['lectures']):
            lecture['self_checks'] = [{'question': f'Question{index}', 'answer': f'Answer{index}'}]
        renderer.validate(data)
        html = renderer.render_summary_html(data, [data['lectures'][0]])
        self.assertIn('Question0', html)
        self.assertNotIn('Question1', html)

    def test_assigned_duplex_faces_preserve_source_order(self):
        items = [{'lecture': 'L1', 'topic': name, 'text': 'Text', 'formula': '', 'page': page}
                 for name, page in [('early', None), ('later', 1), ('other', 2)]]
        pages = renderer.split_two(items)
        self.assertEqual([x['topic'] for x in pages[0]], ['early', 'later'])
        self.assertEqual([x['topic'] for x in pages[1]], ['other'])

    def test_empty_assigned_duplex_face_fails(self):
        data = document('cheat')
        data['settings']['sides'] = 'duplex'
        entry = data['lectures'][0]['concept_entries'][0]
        entry['page'] = 1
        data['lectures'][0]['concept_entries'].append(copy.deepcopy(entry))
        with self.assertRaisesRegex(ValueError, 'both faces'):
            renderer.validate(data)

    def test_font_candidates_include_nonstep_endpoint(self):
        self.assertEqual(list(renderer.font_candidates(8.35, 9.0)), [9.0, 8.8, 8.6, 8.4, 8.35])
        self.assertEqual(list(renderer.font_candidates(8.2, 9.0))[-1], 8.2)
        self.assertEqual(list(renderer.font_candidates(9.0, 9.0)), [9.0])

    def test_plain_text_is_escaped_before_basic_emphasis(self):
        self.assertEqual(renderer.rich('<script>bad()</script> **safe**'),
                         '&lt;script&gt;bad()&lt;/script&gt; <strong>safe</strong>')


class OutputTests(unittest.TestCase):
    def test_separate_sanitized_names_cannot_collide(self):
        data = document()
        data['settings']['layout'] = 'separate'
        data['lectures'][0]['id'] = 'A?B'
        second = copy.deepcopy(data['lectures'][0])
        second['id'] = 'A!B'
        data['lectures'].append(second)
        with self.assertRaisesRegex(ValueError, 'colliding'):
            renderer.output_paths(data, Path('output'))

    def test_existing_outputs_require_overwrite_and_input_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'existing.pdf'
            path.write_bytes(b'original')
            with self.assertRaisesRegex(ValueError, 'already exists'):
                renderer.save_pdf(path, b'changed')
            with self.assertRaisesRegex(ValueError, 'aliases input'):
                renderer.save_pdf(path, b'changed', overwrite=True, input_path=path)
            self.assertEqual(path.read_bytes(), b'original')
            renderer.save_pdf(path, b'changed', overwrite=True)
            self.assertEqual(path.read_bytes(), b'changed')

    def test_separate_preflight_happens_before_render_and_all_outputs(self):
        data = document()
        data['settings']['layout'] = 'separate'
        second = copy.deepcopy(data['lectures'][0])
        second['id'] = 'L2'
        data['lectures'].append(second)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            paths = renderer.output_paths(data, output)
            paths[1].parent.mkdir(parents=True, exist_ok=True)
            paths[1].write_bytes(b'existing')
            with patch.object(renderer, 'render_pdf') as render, self.assertRaises(ValueError):
                renderer.render_summary(data, output)
            render.assert_not_called()
            self.assertFalse(paths[0].exists())
            self.assertEqual(paths[1].read_bytes(), b'existing')

    def test_failed_structural_qa_writes_no_summary(self):
        data = document()
        data['settings']['layout'] = 'separate'
        second = copy.deepcopy(data['lectures'][0])
        second['id'] = 'L2'
        data['lectures'].append(second)
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'pdfs'
            reports = [{'errors': [], 'pages': 2}, {'errors': ['outside page'], 'pages': 2}]
            with patch.object(renderer, 'render_pdf', return_value=b'pdf'), \
                 patch.object(renderer, 'inspect_rendered', side_effect=reports), \
                 self.assertRaisesRegex(RuntimeError, 'Structural PDF check failed'):
                renderer.render_summary(data, output)
            self.assertFalse(output.exists())

    def test_cheat_probes_custom_floor_and_never_writes_failed_attempts(self):
        data = document('cheat')
        data['settings']['min_font_pt'] = 8.35
        reports = [{'errors': ['overflow'], 'pages': 2}] * 4 + [{'errors': [], 'pages': 1}]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'cheat'
            with patch.object(renderer, 'render_pdf', return_value=b'accepted'), \
                 patch.object(renderer, 'cheat_html', return_value='html') as html, \
                 patch.object(renderer, 'inspect_rendered', side_effect=reports):
                renderer.render_cheat(data, output)
            self.assertEqual(html.call_args.args[1], 8.35)
            self.assertEqual(renderer.output_paths(data, output)[0].read_bytes(), b'accepted')


if __name__ == '__main__':
    unittest.main()
