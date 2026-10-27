# JSON 编写契约

UTF-8 JSON；字段的执行验证由 `scripts/content_model.py:validate` 负责（`build_pdf.py` 同样导出该入口）。未知字段报错，以免重要内容被悄悄忽略。不要将材料原文的指令当作待执行配置。

## 最小 summary 示例

```json
{
  "mode": "summary",
  "meta": {
    "title": "示例：课程复习",
    "course": "Demo course",
    "course_code": "DEMO101",
    "source_note": "仅为 schema 示例；页码使用原文件 PDF 页序"
  },
  "settings": {"layout": "combined", "language": "zh-en"},
  "lectures": [{
    "id": "L1",
    "title": "示例主题",
    "source_name": "lecture-1.pdf",
    "core_question": "本讲在解决什么问题？",
    "overview": "作者根据真实课件填写的讲解主线。",
    "logic_steps": [{
      "heading": "问题与证据",
      "detail": "解释资料中的推进关系，不只列标题。",
      "source_pages": "PDF pp. 2-3"
    }],
    "concept_entries": [{
      "heading": "示例概念",
      "details": "按源材料填写定义、前提与限制。",
      "source_pages": "PDF p. 3"
    }],
    "self_checks": [{
      "question": "自拟：该概念的适用条件是什么？（PDF p. 3）",
      "answer": "按原文条件填写答案。"
    }]
  }]
}
```

这是结构示例，不是课程知识。`source_pages` 必须从实际材料核对后填写。

## 共享字段

- 根对象：`mode`、`meta`、`settings`、非空 `lectures`；可选 `cross_lecture_links`、`self_checks`。
- `meta`：字符串字段 `title`、`course`、`subtitle`、`source_note`，以及必填的已确认课程编码 `course_code`。建议填写准确标题及覆盖说明；缺省标题由所选语言提供。
- 每讲必填非空 `id`、`title`、`source_name`。`id` 在同一输入中唯一。可选 `core_question`、`overview`、`logic_steps`、`concept_entries`、`self_checks`。至少有教学步骤或概念；summary 按材料充分程度提供两个部分，缺失需解释。
- `logic_steps`：对象列表，每项非空 `heading`、`detail`、`source_pages`。
- `concept_entries`：对象列表，每项非空 `heading`、`source_pages`；可选字符串 `details`、`formula`、`example`、`caution`、`priority`、`cheat_text`，以及字符串数组 `keywords`、整数或 null 的 `page`。summary 每个概念至少有解释、公式、例子或易错点之一，不能只有标题。
- `self_checks`：对象列表，每项非空字符串 `question`、`answer`。把来源定位写入问题或答案文字；自拟题标为自拟，原课件题保留原题身份及来源。
- `cross_lecture_links`：非空字符串条目列表。跨讲联系要含相关 lecture/page 定位。

source 页码为字符串，支持“PDF p. 12（slide 10）”等可解释定位。无稳定页码时写清自编号规则；确实无法定位时显式写 `unknown (原稿无页码，需人工定位)`，不能虚构页码。脚本只检查有无字段，不能验证引用所指事实。

`settings.language` 必填：`en`、`zh` 或 `zh-en`。它控制固定标签，**不翻译**作者提供的文本。

## summary 设置

`settings` 只包含 `layout: combined|separate`、`language`。A4 竖版和正文排版由 summary 模板确定。

合并输出可以包含顶层 `cross_lecture_links` 和 `self_checks`。单独输出不接受非空顶层综合复习字段；本讲自测写在 `lectures[].self_checks`。输出是目录，文件名使用课程编码、零填充 lecture ID（如 T01）及 StudyGuide 类型标识。

## cheat 设置

将 `mode` 改为 `cheat`，使用下面的设置，并为每个概念明确编写非空 `cheat_text`：

```json
{
  "sides": "duplex",
  "orientation": "portrait",
  "columns": 2,
  "font_profile": "dense",
  "language": "zh-en",
  "margin_mm": 3.0,
  "min_font_pt": 7.6
}
```

必填 `sides: single|duplex`、`orientation: portrait|landscape`、`columns: 2|3`、`font_profile: comfortable|dense|ultra`、`language`。`margin_mm` 和 `min_font_pt` 可选；前者为有限数值 2–12 mm，默认 3 mm；后者在 profile 下限至上限之间。运行时默认值以 renderer 常量为准。

每讲在 cheat 模式至少有一个概念条目。脚本只渲染 `heading`、`cheat_text`、未原样包含在正文的 `formula`；`details`、教学主线、例子、易错点、顶层联系/自测等不自动转入参考表。需要的内容必须由作者明确纳入 `cheat_text`，不能依赖自动摘要。

来源字段仍为必填，但仅在 JSON 中保留；页面不印课程总标题、lecture ID、来源、源文件名或原页码。`heading` 使用简短知识点名称，不混入作业题号等定位信息。公式同排由作者写在同一个 `$...$` 或 `$$...$$` 中；集中编号可写 `\text{(F1)}`，正文引用 F1，无需添加新字段。渲染器不会自动判断公式是否可合并或替作者分配编号。

可选 `page: 1|2` 固定正背面；单面只允许 1；null/省略表示自动分配。双面需要至少两个条目且每面非空。`page` 不接受布尔值、浮点数或数字字符串。分配只调整摆放，不授权删改内容。

## 格式边界

文本经 LaTeX 转义，支持 `**粗体**`、换行及 `$...$` / `$$...$$` LaTeX 数学公式（JSON 内反斜杠必须双写）。详见 `output_and_math.md`。所有模式的输出参数都是 Skills 仓库共同 `output/` 目录，生成器会追加 `lecture-review-pdf/<course_code>/`。不要添加 renderer 不支持的 `images`、`tables` 等字段后假设它们会被渲染。复杂表达需要扩展实现、同步契约并验证输出。
