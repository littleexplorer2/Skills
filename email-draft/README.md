# Email Draft · 中英双语邮件

同一份 skill 用于 Windows 与 macOS。核心为 UTF-8 文本指令，无 Python、Node、邮件客户端或 API key 依赖。具体交互由运行 skill 的客户端提供；不支持选择工具的客户端以编号问题代替弹框。

## 安装

将完整的 `email-draft` 文件夹复制到当前用户的 `.agents/skills/` 下。根据 [OpenAI 官方技能文档](https://learn.chatgpt.com/docs/build-skills)，这是用户级发现目录；技能通常自动发现，未出现时重启客户端。不要同时在多个发现目录安装同名副本。

以下命令从包含 `email-draft` 文件夹的目录运行（本仓库根目录或安装包解压目录）。已有同名目标时停止，先自行备份再决定是否升级，不覆盖已有修改。

Windows PowerShell：

```powershell
$emailSkillSource = (Resolve-Path -LiteralPath './email-draft').Path
$emailSkillParent = Join-Path $env:USERPROFILE '.agents/skills'
$emailSkillTarget = Join-Path $emailSkillParent 'email-draft'
if (Test-Path -LiteralPath $emailSkillTarget) { throw '目标已存在，请先检查并备份；本命令不会覆盖。' }
New-Item -ItemType Directory -Path $emailSkillParent -Force | Out-Null
Copy-Item -LiteralPath $emailSkillSource -Destination $emailSkillTarget -Recurse -ErrorAction Stop
Test-Path -LiteralPath (Join-Path $emailSkillTarget 'SKILL.md')
```

macOS Terminal（zsh / bash）：

```sh
(
  set -eu
  email_skill_source="$(pwd)/email-draft"
  email_skill_parent="$HOME/.agents/skills"
  email_skill_target="$email_skill_parent/email-draft"
  test -f "$email_skill_source/SKILL.md" || { echo '请先进入包含 email-draft 的目录'; exit 1; }
  if test -e "$email_skill_target" || test -L "$email_skill_target"; then
    echo '目标已存在，请先检查并备份；本命令不会覆盖。'
    exit 1
  fi
  mkdir -p "$email_skill_parent"
  cp -R "$email_skill_source" "$email_skill_target"
  test -f "$email_skill_target/SKILL.md" && echo '文件复制完成；请在客户端确认技能可见。'
)
```

也可通过 Finder/文件资源管理器执行同样的文件夹复制。不要把 `SKILL.md` 单独复制出去；保持目录结构。安装不会配置邮箱，也不会自动发送邮件。

## 使用

在支持 `$` 技能调用的输入框中输入 `$email-draft`，或在客户端的技能选择器中选择“邮件撰写 · 中英双语”。也可明确指定 `SKILL.md` 文件让 agent 读取试用。

示例：

> 使用 $email-draft，中文，第 1 种风格。向项目负责人询问会议是否可以改到周四下午。落款：陈宁。

> 使用 $email-draft，English，第 2 种风格。向供应商索取更新后的报价单，保持原订单数量，不承诺下单。落款：Alex Chen。

> 使用 $email-draft，中文，第 3 种风格。回复同事，确认已收到文件。落款：陈宁。

示例中的姓名为虚构，显式指定时覆盖个人配置。三种风格的唯一定义在 [SKILL.md](SKILL.md)；语言、风格和已配置的学号选项缺失时会先询问，不自动套用默认值。选择框的预选项不代表提交。

写作结构为先说明联系的主题与目的，再自然过渡到请求或具体事项。礼貌问句本身不等于来意说明；不同风格调整开场的详细程度，而不是删除这层信息。通知或确认邮件不强行写成求助邮件；完整规则及复核要求见 `SKILL.md`。

新邮件的主题同时概括沟通意图和具体事项，例如询问、申请、请求或确认，不只列出内容关键词；具体措辞规则见 `SKILL.md`，回复邮件通常沿用原线程主题。

同一封邮件只需启动一次：看到草稿后可直接提出修改意见，无需重复调用技能或重新选择已确认选项；会逐轮修订，直到你表示满意或停止。针对当前场景的修改意见仅用于本封邮件，不写入 skill、配置或本地文件；只有明确要求修改技能或长期默认值才持久更新。每轮交付后等待你的反馈，不在后台自行循环改写，定稿也不会自动发送。

## 个人落款配置

`profile.json` 是个人信息的唯一来源，`names.zh` 和 `names.en` 分别设置中文、英文默认姓名；`student_ids` 数组保存学校标签和号码候选。它不设置默认学号：每封新邮件独立选择学校号码或“不附学号”。同一封邮件从中文切换为英文，只更换默认姓名和邮件语言，保留已选学号。

此文件已被本仓库 `.gitignore` 排除。你本人的跨设备安装包可以携带它，分享给别人前应移除个人配置；没有此文件时 skill 会询问必要身份信息，不影响通用写作。修改默认姓名或候选学号时只修改此文件，不复制维护到其他文档。复制到两台设备后，两份配置不会自动同步。

## 输出与限制

- 邮件只在聊天中交付主题、正文和落款供复制，不保存为本地文件；试用、验证、缓存、日志及备份也不能另存邮件内容。无需提供邮件保存目录。
- 两个及以上独立问题或诉求按 `1. `、`2. `、`3. ` 连续编号、分段排列，三种风格均适用；不为凑数拆分同一问题或添加新诉求。
- 正文以普通聊天段落呈现，不用代码块、预格式文本或固定宽度容器；不带字体颜色、背景色、HTML 或其他富文本格式。收件人和主题单独提供。
- 称呼、致谢、结语和落款按用户选定布局分段；中英文用语与语境规则的唯一来源在 `SKILL.md`。中文默认祝颂语为“顺颂，时祺”，不默认“此致敬礼”；第 2 种风格保留正式称呼及带敬辞的署名，并按对象与目的判断是否适合。姓名与已选学号同一行，不另列 `Student ID:`。
- 段落之间使用真正的空行，编号项之间使用真正的换行；不靠空格、制表符或截图宽度拼接布局。长句随窗口宽度自动折行，不人为限定每行字符数。编辑普通空格引起的视觉重排与删除段落分隔符是不同情况。
- 目标排版为 Times New Roman、12 磅（用户原称 New Times Roman）。纯文字本身不能携带字体、字号；在 Outlook 中以“仅保留文本 / Keep Text Only”方式粘贴后，在编辑器设置字体字号，字色使用自动/默认。中文可由系统回退字体显示；真正的纯文本邮件不能限定收件人的字体。
- 聊天的显示字体和换行不等于 Outlook 的字体、剪贴板编码或段落标记；应使用目标客户端的纯文本粘贴，再设置 Times New Roman、12 磅和自动字色。未经实测，不保证字体、段落转换及深浅色主题在所有版本下一致。粘贴选项及纯文本能力参见 [Microsoft 粘贴说明](https://support.microsoft.com/en-us/outlook/outlook-advanced-editing-options) 和 [邮件格式说明](https://support.microsoft.com/en-gb/outlook/change-the-message-format-to-html-rich-text-format-or-plain-text-in-outlook)。本 skill 不主动修改 Outlook 设置。
- 本地保留的 skill 规则、安装包和个人落款配置不属于生成的邮件；维护时的验证报告只记录结论，不收录实际邮件内容。此规则不控制客户端自身的聊天历史存储。
- 未配置/未确认的姓名、地址或事实不会从历史邮件补全。包含占位符的草稿仍需补全。
- 这不是 Outlook、Gmail 或 Apple Mail 插件；与具体邮箱独立。在线创建草稿、添加附件及发送需另行明确授权和可用工具。
- Windows / macOS 共用内容，不表示两端均已实机验收；当次实测记录另存验证报告。
