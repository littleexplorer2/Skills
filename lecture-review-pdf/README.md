# lecture-review-pdf

从课程资料制作 A4 复习 PDF 或单面/双面参考表。入口与工作规则见 [SKILL.md](SKILL.md)，数据格式见 [content_schema.md](references/content_schema.md)。

## 使用与能力

向 Codex 提供课件后，可以说：

- “使用 lecture-review-pdf，将这些课件合成中文复习 PDF，保留英文术语和原页码。”
- “制作一张 A4 双面参考表，竖版两栏，dense 字号，覆盖这些章节；删主题前先问我。”

模型负责阅读、核对来源和整理 JSON；Python 脚本只负责验证 JSON、排版和检查 PDF，不会直接解析 PPT/PDF 或自动判断考点。`summary` 支持合并或逐讲输出；`cheat` 支持单/双面、横/竖版、2/3 栏和三个字号范围。`en`、`zh`、`zh-en` 控制固定标签，正文必须预先用所选语言编写。

内置模板支持文本、换行、`**粗体**`、MathText 矢量公式。完整 LaTeX、插图、复杂表格及双语并排需要额外实现和验证。资料真实性、内容完整性、引用准确性、版面重叠和物理打印效果不能靠检查脚本单独证明。

## 环境

复用已配置的 Python 和 `requirements.txt` 中的依赖。Windows 使用 Python Launcher 时可将下列命令中的 `python` 替换为 `py -3.12`，或直接使用已确认的解释器绝对路径。安装依赖与运行脚本必须使用同一个解释器。

```bash
python scripts/check_environment.py --json
python -m pip install -r requirements.txt
```

仅在缺少依赖且允许安装时运行第二条命令，优先使用现有可用环境或专用虚拟环境。诊断脚本不安装软件、不改 PATH、不设置持久环境变量，也不生成 PDF。

Windows 上 WeasyPrint 的 Python 库还需要 Pango/GLib 等原生 DLL。按 [WeasyPrint 官方安装说明](https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows) 配置；MSYS2 安装方法以该文档为准。已安装并验证过的 DLL 可以通过 `WEASYPRINT_DLL_DIRECTORIES` 指定，通常例如 `C:\msys64\ucrt64\bin`，实际路径需先检查。

本机此前安装的便携运行库位于 `%USERPROFILE%\.codex\tools\weasyprint-v70.0\_internal`。这是本机安装位置，不是其他机器的默认值；该目录和 DLL 不包含在 skill ZIP 内。若继承的环境变量为空，可在确认用户级值与文件存在后为当前 PowerShell 进程加载：

```powershell
$env:WEASYPRINT_DLL_DIRECTORIES = [Environment]::GetEnvironmentVariable('WEASYPRINT_DLL_DIRECTORIES', 'User')
py -3.12 scripts/check_environment.py --json
```

中文需要系统字体，例如 Microsoft YaHei 或 Noto Sans CJK SC。字体探测只能给出线索，最终仍要看实际渲染的每一页。

## 生成与检查

以下命令从 skill 根目录执行，输出路径位于当前任务工作目录，不能指向原始课程文件。

```bash
python scripts/build_pdf.py --input data.json --validate-only
python scripts/build_pdf.py --input data.json --output /path/to/task/outputs
python scripts/check_pdf.py /path/to/task/outputs/IERG4190_T01_StudyGuide.pdf --input data.json --json
pdftoppm -r 150 -png /path/to/task/outputs/IERG4190_T01_StudyGuide.pdf /path/to/task/proof
```

`--validate-only` 不需要 WeasyPrint 或 PyMuPDF。所有模式 `--output` 均为根目录，文件按课程编码及 lecture ID 分类命名；对生成的每个 PDF 都运行检查。顶层跨讲联系/自测不能用于 `summary + separate`，请将自测移到所属 lecture，综合资料另行组织。

已有输出默认拒绝覆盖；确认是可替换的生成结果后加 `--overwrite`。PDF 输出与输入 JSON 相同的路径始终被拒绝。结构检查不通过的内容不会写成成功结果；失败时不要把旧输出误认为本次结果。

也可手动指定检查参数：

```bash
python scripts/check_pdf.py review.pdf --mode summary
python scripts/check_pdf.py sheet.pdf --mode cheat --sides duplex --orientation portrait --min-font 7.2 --margin-mm 4.8
```

cheat 手工检查必须指定面数、方向和字号下限，避免把默认 6.6 pt 当作用户的实际要求。使用 `--input` 时，与 JSON 冲突的显式参数会报错。检查器返回 0 表示自动结构检查通过，1 表示检查未通过或 PDF/依赖无法读取，2 表示命令参数或输入 JSON 有误；输出说明与错误优先于是否留下文件。

内置样例仅用于软件烟雾测试，没有提供课程原文用于核对事实。测试命令：

```bash
python -m unittest discover -s tests -v
python scripts/build_pdf.py --input samples/demo_summary.json --output /path/to/task/demo-summary
python scripts/build_pdf.py --input samples/demo_cheat.json --output /path/to/task/demo-cheat
```

## 安装与更新

将完整 `lecture-review-pdf` 目录放入 Codex 用户 skill 目录（本版本使用 `~/.agents/skills`；Windows 对应 `%USERPROFILE%\.agents\skills`）。更新前备份旧目录，只替换该 skill 的文件，保留系统工具与其他 skill。ZIP 是可分发的包；只有目录进入实际 skill 搜索路径才算安装。环境依赖另行配置，不打包解释器、DLL、用户课程资料或生成的复习文件。

更新后的调用行为从下一次加载此 skill 开始使用。更新文件不会自动把用户已有课程 JSON 翻译或迁移；新版本的字段错误应根据 schema 修正，不能为通过验证删除必要课程内容。


## Mac 与 Windows 统一版

版本：2026-10-16 unified。JSON 必须含 `meta.course_code`；所有模式 `--output` 为目录，例如 `outputs/IERG4190_T01_StudyGuide.pdf`。命名及数学契约见 `references/output_and_math.md`。

macOS 复用专用环境 `~/Library/Application Support/LectureReviewPDF/venv`，或设置 `LECTURE_REVIEW_PYTHON` 为已安装 requirements.txt 的解释器。运行 `bash scripts/build_pdf_mac.sh --input data.json --output outputs`。检查用 `bash scripts/check_pdf_mac.sh <实际生成的PDF> --input data.json --json`。原生 Pango/GLib 仍须在该设备配置；wrapper 查找 /opt/homebrew/lib 与 /usr/local/lib。

两端复制完整 skill 文件夹，不复制 venv、缓存或原生库。更新不会自动重制旧 PDF。不存在随包提供的 Install.command；依赖安装以本文件命令为准。Linux 可使用同一 Python 核心，但也需要系统原生库。运行环境及字体不同，分页可能略有区别；每台机器都需检查输出。
