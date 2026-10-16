# Course filing and formula contract

## Storage
- Course code comes from explicit user input or an unambiguous source label; never infer it from a vague filename. If missing, ask while continuing independent inspection.
- Read the Skills repository root `AGENTS.md` for the shared output root. Use `<Skills-repository>/output/lecture-review-pdf/<course_code>/<course_code>_<scope>_<kind>.pdf`.
- Example: `output/lecture-review-pdf/IERG4190/IERG4190_T01_StudyGuide.pdf`; combined `IERG4190_T01-T02_StudyGuide.pdf`; cheat `IERG4190_T01-T02_CheatSheet.pdf`.
- Use zero-padded scope IDs such as T01, L02. Preserve the confirmed official course code. Kind is StudyGuide or CheatSheet. Do not add generic final/latest or timestamps by default.
- Keep course-specific drafts, JSON, extracted text and page previews in `output/lecture-review-pdf/<course_code>/work/`, or use task scratch space during execution. Never move the user's source files without instruction.
- On revision, explicitly archive the previous PDF under `archive/` with a revision suffix, then rebuild the stable filename; if the user explicitly requests deleting previous generated files, delete those identified old outputs after the replacement passes QA. Never silently overwrite. Do not use two same-name skills as parallel active implementations.
- `--output` receives the shared `<Skills-repository>/output/` directory for every mode. The renderer adds `lecture-review-pdf/<course_code>/`, retains the course code in every PDF filename, and refuses missing/unsafe codes and name collisions. Resolve the repository location from the root AGENTS.md or the user; ask if unknown. Do not assume the installed skill directory is the repository.

## Formula authoring
- Put inline math inside `$...$` and display math inside `$$...$$` in details, formula, examples, cautions, logic and self-check fields. JSON backslashes must be escaped.
- The renderer rejects unmatched delimiters and unsupported commands rather than printing source. Display fractions use a larger fraction style; formula sizes follow surrounding text in em units, including cheat mode. The renderer uses Matplotlib MathText and embeds SVG font outlines into the PDF. This works without browser JavaScript or a full TeX installation; install the skill requirements on each device.
- Use supported MathText syntax, not arbitrary full LaTeX environments. For example `$$X(\omega)=\int_{-\infty}^{\infty}x(t)e^{-j\omega t}\,dt$$` and `$f_s$`.
- Use `\frac{a}{b}`, `x_{n}`, `e^{-j\omega n}`, `\sum_{n=-\infty}^{\infty}`; each multiline equation is a separate display expression. Keep Chinese prose outside the math delimiters.
- The author must transcribe formulas against the original source; do not regex-convert ambiguous plain text or guess summation/integration limits. Invalid or unsupported formulas must fail visibly rather than falling back to raw TeX. For unsupported constructs use a validated full TeX/SVG pipeline and recheck the PDF.
- SVG math is vector graphics and may not be searchable/copyable as formula text. Preserve the source math in working JSON; normal prose remains searchable.

## QA
- Render every output page and inspect formulas at 150–250 dpi: stacked fractions, superscripts/subscripts, signs, brackets, limits, Greek letters, baseline and overflow. Verify the equations against the cited original pages.
- Font checks cannot validate mathematics. A pass from check_pdf.py is necessary but insufficient. Check missing-glyph fonts as well as page size, margins and font size.
- Never claim that a PDF viewer caused errors until comparing the saved PDF through an independent renderer. Literal `^` and `_` in a generated PDF usually indicate untypeset source text, not viewer failure.
