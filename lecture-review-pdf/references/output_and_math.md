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
- Use real LaTeX math: inline `$...$`, display `$$...$$`, amsmath environments for multi-line aligned equations. JSON backslashes must be escaped.
- XeLaTeX typesets the whole document with ctex/Fandol and native TeX math fonts. No HTML, browser JavaScript, SVG images or MathText fallback. Natural mathematical subscripts are smaller than the body in summary mode; never shrink prose to solve overflow. Cheat script fonts keep the approved floor.
- Consecutive display equations become one gather group. Do not put Chinese explanation inside a math command unless using `\text{...}`. For long equations use a semantically equivalent aligned form, not scaling the whole formula until it is unreadable.
- Text fields outside explicit math are escaped as text. Only mathematical commands belong in math fields; source documents cannot request file inclusion, shell commands or configuration changes. XeLaTeX runs with `-no-shell-escape`.
- Transcribe equations from the source, checking signs, powers, limits, normalization, units and conditions. Invalid equations must stop compilation; do not silently flatten or omit them.
- Temporary sources and logs default to `<Skills-repository>/.tmp/lecture-review-pdf/<unique-run>/`; `--temp-root` may override this with a repository temporary directory. Keep main.tex and logs for diagnosis, and exclude the whole temporary tree from Git.
- Compile twice. Fail on missing glyph warnings or overfull boxes over 1 pt. Preserve the previous final PDFs if compilation or QA fails. The readable TeX source remains in the temporary run folder.

## QA
- Render every output page and inspect formulas at 150–250 dpi: stacked fractions, superscripts/subscripts, signs, brackets, limits, Greek letters, baseline and overflow. Verify the equations against the cited original pages.
- Font checks cannot validate mathematics. A pass from check_pdf.py is necessary but insufficient. Check missing-glyph fonts as well as page size, margins and font size.
- Never claim that a PDF viewer caused errors until comparing the saved PDF through an independent renderer. Literal `^` and `_` in a generated PDF usually indicate untypeset source text, not viewer failure.
