#!/usr/bin/env python3
"""Check measurable A4, text, and font constraints; not source or print proof.

Dependencies are loaded only when inspecting a PDF. Use --input to check against
the same validated settings as the renderer instead of re-entering them.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path


A4_W, A4_H = 595.2756, 841.8898
FONT_TOLERANCE_PT = 0.02
BOUNDS_TOLERANCE_PT = 0.5
DIMENSION_TOLERANCE_PT = 0.8


def _number(value, name, errors, *, minimum=0.0, strict=False):
    try:
        finite = not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        errors.append(f'{name} must be a finite number')
        return False
    if value < minimum or (strict and value == minimum):
        relation = 'greater than' if strict else 'at least'
        errors.append(f'{name} must be {relation} {minimum:g}')
        return False
    return True


def inspect_pdf(source, mode, sides=None, orientation='portrait', min_font=None, margin_mm=None):
    """Return errors/pages/font_min/font_max for PDF bytes or a filesystem path.

    Cheat checks require an explicit side count and approved font floor. Summary
    is portrait A4. A caller may impose a font floor or a printable margin; the
    latter checks *all* extracted text, including headers and footers. Small
    floating-point and glyph-bbox rounding tolerances are not design margins.

    This check cannot establish source fidelity, full content retention,
    overlap-free layout, mathematical correctness, or physical print legibility.
    """
    report = {'errors': [], 'pages': 0, 'font_min': 0.0, 'font_max': 0.0}
    errors = report['errors']
    if mode not in ('summary', 'cheat'):
        errors.append('mode must be summary or cheat')
    if orientation not in ('portrait', 'landscape'):
        errors.append('orientation must be portrait or landscape')
    if mode == 'summary':
        if sides is not None:
            errors.append('sides is only supported for cheat mode')
        if orientation != 'portrait':
            errors.append('summary mode requires portrait orientation')
    if mode == 'cheat':
        if sides not in ('single', 'duplex'):
            errors.append('cheat mode requires explicit sides = single|duplex')
        if min_font is None:
            errors.append('cheat mode requires an explicit min_font of at least 6.6pt')
    if min_font is not None:
        _number(min_font, 'min_font', errors, minimum=6.6 if mode == 'cheat' else 0.0,
                strict=mode != 'cheat')
    if margin_mm is not None and _number(margin_mm, 'margin_mm', errors):
        if margin_mm * 2 >= 210:
            errors.append('margin_mm must leave a positive A4 printable area')
    if errors:
        return report

    try:
        import pymupdf
    except ImportError:
        errors.append('PyMuPDF is required: install the pymupdf package in this Python environment')
        return report

    try:
        if isinstance(source, bytes):
            document = pymupdf.open(stream=source, filetype='pdf')
        elif isinstance(source, (str, Path)):
            document = pymupdf.open(source)
        else:
            errors.append('source must be PDF bytes or a filesystem path')
            return report
    except Exception as exc:
        errors.append(f'Cannot open PDF: {exc}')
        return report

    font_sizes = []
    try:
        with document:
            if not document.is_pdf:
                errors.append('Input is not a PDF document')
                return report
            if document.needs_pass:
                errors.append('PDF is password-protected; provide an accessible PDF')
                return report
            report['pages'] = len(document)
            if not report['pages']:
                errors.append('No PDF pages')
            if mode == 'cheat':
                expected_pages = 1 if sides == 'single' else 2
                if len(document) != expected_pages:
                    errors.append(f'Expected {expected_pages} PDF pages, got {len(document)}')
            expected_size = (A4_W, A4_H) if orientation == 'portrait' else (A4_H, A4_W)
            inset = margin_mm * 72 / 25.4 if margin_mm is not None else 0.0
            for page_number, page in enumerate(document, 1):
                width, height = page.rect.width, page.rect.height
                if (abs(width - expected_size[0]) > DIMENSION_TOLERANCE_PT or
                        abs(height - expected_size[1]) > DIMENSION_TOLERANCE_PT):
                    errors.append(f'Page {page_number}: expected A4 {orientation}; got {width:.2f}x{height:.2f}pt')

                # Page-clipped extraction can hide the very overflow being checked.
                info = page.get_text('dict', clip=pymupdf.INFINITE_RECT())
                for drawing in page.get_drawings():
                    box=drawing['rect']
                    if box.x0 < -0.5 or box.y0 < -0.5 or box.x1 > width+0.5 or box.y1 > height+0.5:
                        errors.append(f'Page {page_number}: vector content outside page bounds')
                page_chars = 0
                for block in info['blocks']:
                    for line in block.get('lines', []):
                        for span in line['spans']:
                            text = span['text'].strip()
                            if not text:
                                continue
                            page_chars += len(text)
                            box = pymupdf.Rect(span['bbox'])
                            # Extraction coordinates are unrotated; page.rect is rotated.
                            if page.rotation:
                                box = box * page.rotation_matrix
                            bounds = (box.x0, box.y0, box.x1, box.y1)
                            if not all(math.isfinite(v) for v in bounds):
                                errors.append(f'Page {page_number}: invalid text bounding box')
                            elif (box.x0 < inset - BOUNDS_TOLERANCE_PT or
                                  box.y0 < inset - BOUNDS_TOLERANCE_PT or
                                  box.x1 > width - inset + BOUNDS_TOLERANCE_PT or
                                  box.y1 > height - inset + BOUNDS_TOLERANCE_PT):
                                label = 'printable margin' if margin_mm is not None else 'page bounds'
                                errors.append(f'Page {page_number}: text outside {label}: {text[:24]!r}, '
                                              f'bbox {tuple(round(v, 2) for v in bounds)}')
                            size = span['size']
                            if not math.isfinite(size) or size <= 0:
                                errors.append(f'Page {page_number}: invalid font size {size!r}')
                            else:
                                font_sizes.append(size)
                                if min_font is not None and size < min_font - FONT_TOLERANCE_PT:
                                    errors.append(f'Page {page_number}: small font {size:.2f}pt below '
                                                  f'selected floor {min_font:g}pt: {text[:24]!r}')
                            if '\ufffd' in text or '\x00' in text:
                                errors.append(f'Page {page_number}: replacement or null character in extracted text')
                # A .notdef glyph is a stronger missing-font signal than text alone:
                # a PDF may retain the original Unicode while drawing a tofu box.
                missing_glyph = any(
                    glyph_id == 0 and not chr(codepoint).isspace()
                    for trace in page.get_texttrace()
                    for codepoint, glyph_id, _origin, _bbox in trace['chars']
                    if 0 <= codepoint <= 0x10FFFF
                )
                if any('LastResort' in trace['font'] for trace in page.get_texttrace()):
                    errors.append(f'Page {page_number}: LastResort missing-font fallback')
                if missing_glyph:
                    errors.append(f'Page {page_number}: missing glyph (.notdef) detected')
                if page_chars < 30:
                    errors.append(f'Page {page_number}: little/no extractable text ({page_chars} chars)')
    except Exception as exc:
        errors.append(f'Cannot inspect PDF: {exc}')
    if font_sizes:
        report['font_min'] = round(min(font_sizes), 4)
        report['font_max'] = round(max(font_sizes), 4)
    return report


def expected_settings(data):
    """Resolve settings from the renderer's validated contract, without defaults drift."""
    from build_pdf import DEFAULT_CHEAT_MARGIN_MM, SUMMARY_MIN_FONT_PT, resolve_font_bounds, validate

    validate(data)
    settings = data['settings']
    if data['mode'] == 'summary':
        return dict(mode='summary', sides=None, orientation='portrait', min_font=SUMMARY_MIN_FONT_PT,
                    margin_mm=None)
    low, _high = resolve_font_bounds(settings)
    return dict(mode='cheat', sides=settings['sides'], orientation=settings['orientation'],
                min_font=low, margin_mm=settings.get('margin_mm', DEFAULT_CHEAT_MARGIN_MM))


def _arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    parser.add_argument('--input', type=Path, help='Derive the expected contract from renderer input JSON')
    parser.add_argument('--mode', choices=['summary', 'cheat'])
    parser.add_argument('--sides', choices=['single', 'duplex'])
    parser.add_argument('--orientation', choices=['portrait', 'landscape'])
    parser.add_argument('--min-font', type=float)
    parser.add_argument('--margin-mm', type=float, help='Optional printable margin applied to every text span')
    parser.add_argument('--json', action='store_true', help='Emit a deterministic machine-readable report')
    args = parser.parse_args(argv)
    provided = {key: getattr(args, key) for key in ('mode', 'sides', 'orientation', 'min_font', 'margin_mm')}
    if args.input:
        try:
            data = json.loads(args.input.read_text(encoding='utf-8-sig'))
            expected = expected_settings(data)
        except (OSError, UnicodeError, ValueError, TypeError, KeyError) as exc:
            parser.error(f'Invalid --input: {exc}')
        for name, value in provided.items():
            if value is not None and value != expected[name]:
                parser.error(f'--{name.replace("_", "-")} conflicts with --input '
                             f'(provided {value!r}, expected {expected[name]!r})')
    else:
        if args.mode is None:
            parser.error('--mode is required unless --input supplies the expected settings')
        if args.mode == 'cheat':
            for name in ('sides', 'orientation', 'min_font'):
                if provided[name] is None:
                    parser.error(f'cheat mode requires --{name.replace("_", "-")} unless --input is supplied')
        expected = provided
        expected['orientation'] = args.orientation or 'portrait'
    return args, expected


def main(argv=None):
    args, expected = _arguments(argv)
    report = inspect_pdf(args.file, **expected)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, allow_nan=False))
    else:
        print(f'PDF: {args.file}, pages={report["pages"]}, '
              f'font-range={report["font_min"]:.2f}-{report["font_max"]:.2f}pt')
        if report['errors']:
            print('FAIL: ' + '\n  '.join(report['errors']), file=sys.stderr)
        else:
            print('PASS: measured page, font and extracted-text checks only; '
                  'visual, source and physical-print review remain necessary')
    return 1 if report['errors'] else 0


if __name__ == '__main__':
    sys.exit(main())
