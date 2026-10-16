@echo off
setlocal
set "RUNTIME_PY=%LOCALAPPDATA%\LectureReviewPDF\venv\Scripts\python.exe"
if defined LECTURE_REVIEW_PYTHON set "RUNTIME_PY=%LECTURE_REVIEW_PYTHON%"
if not exist "%RUNTIME_PY%" (
  echo Missing skill runtime. Run Install-Windows.cmd first. 1>&2
  exit /b 1
)
"%RUNTIME_PY%" "%~dp0build_pdf.py" %*
exit /b %errorlevel%
