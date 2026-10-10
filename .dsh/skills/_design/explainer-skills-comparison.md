# Agent Skills 选型对比：用文档 / 图 / 动画 / 视频讲清一个技术点

> 调研日期：2026-10-10。调研范围：skills.sh 生态（20+ 关键词查询：explainer / animation / video / manim / teaching / visual explainer / diagram as code 等）、17 个候选仓库 GitHub 元数据、14 个候选仓库源码通读（SSH 克隆后逐个 `git ls-tree` 定位 SKILL.md 并读原文）。
> 用途：为「把一个技术点 / 一个算法 / 一个知识点 / 一个事件讲给人听」选择参考 skill，覆盖**文档、图片、动画、视频**四种媒介。
> 姊妹文档：同目录 [agent-skills-comparison.md](./agent-skills-comparison.md)（语言编码规范 & Markdown 规范选型）。

## TL;DR

| 媒介需求 | 推荐 | 备选 | 不要选 |
|----------|------|------|--------|
| 四种媒介一个入口（含 MP4） | `nicobailon/visual-explainer@visual-explainer`（610） | 无 | — |
| 长期学透一个知识点（文档讲义） | `mattpocock/skills@teach`（784.8K） | `sanyuan0704/sanyuan-skills@book-study`（3.3K） | — |
| 成品视频（含 BGM / 素材 / 配音） | `heygen-com/hyperframes@faceless-explainer`（403.2K） | `remotion-dev/skills@remotion-render`（143.4K） | HyperFrames 的各类 fork |
| 数据图表 | `anthropics/knowledge-work-plugins@create-viz`（5.1K） | `antvis/chart-visualization-skills`（6.3K，依赖外部 API） | — |
| 架构 / 流程 / 时序图 | `tt-a1i/archify@archify`（144.3K） | `Agents365-ai/drawio-skill`（4.9K，要可编辑文件时） | — |
| 视频脚本（不渲染） | `samber/developer-relations-skills@technical-video-script`（3.8K） | — | — |
| 网页 UI 动效 | **与本需求无关** | — | `emilkowalski/skills` 全系 |
| 数学动画（manim 风） | **生态空白，建议自建** | — | — |

**组合策略**：`visual-explainer` 做媒介底座（文字 → 图 → 动画 → MP4 一条链），`teach` 做长期学习结构（要不要跨会话学透），`create-viz` 补数据图，`technical-video-script` 在进渲染前把脚本定死。四者职责不重叠，可叠加。

**判断口径提醒**：skills.sh 的 `installs` 只统计经它 CLI 安装的次数。像 `visual-explainer` 这种 10.3K stars 但没走 skills.sh 分发的项目会被严重低报，因此本报告的成熟度结论一律**以 stars + 安全审计 + 最近推送 + 是否被上游依赖**四项合看，不单看 installs。

---

## 第一梯队：直接推荐

### 1. `nicobailon/visual-explainer@visual-explainer` — 四种媒介一个入口 ⭐首选

| 项 | 内容 |
|----|------|
| 体量 | 34 个文件 / 416 KB：`SKILL.md` + `commands/`（generate-video、generate-slides、plan-review、diff-review、fact-check、generate-web-diagram、project-recap）+ `references/`（diagrams、slides、video、themes、style-guide、plans）+ `templates/`（page.html、plan.html、slide-deck.html）+ `video/` + `pptx/` + `mcp/` |
| 版本 | 0.12.0（npm 发布时间 2026-10-02），MIT |
| 成熟度 | 10.3K stars / **三家安全审计全 Pass** / 2026-10-06 推送 |
| 产出 | ① 自包含 HTML 讲解页 ② 手绘 SVG 图（架构 / 流程 / 对比表）③ slide deck ④ **PPTX 导出** ⑤ animated explainer ⑥ **1920×1080 MP4**（有 speech API key 才配音，否则静音 + 自动字幕） |
| 上游背书 | `plannotator`（9.3K stars）把它的"通用讲解"路径作为自身 fallback 委托给它 — 属被依赖方 |
| 依赖 | 看 HTML 要浏览器（必有）；渲染 MP4 要 `playwright-core` + ffmpeg；AI 配图可选 surf-cli |
| 适用 | 一个技术点 / 算法 / 事件，从讲透（网页）到发出去（视频）一次走完 |
| 不适用 | 要含 BGM、素材库、成片包装的营销级视频产线（→ hyperframes） |

**优势**：唯一一个把四种媒介收在一个 skill 里的候选；产出的 HTML 是纯文本、可 diff、可进版本库；视频走"虚拟时钟逐帧"渲染，动效不会抖。
**局限**：skill 自述的 `npx … visual-explainer-video` 命令目前**不可用**（见「环境与安装」）；无 API key 时没有配音；`installs` 只有 610，属于"GitHub 上成熟、skills.sh 上冷门"。

### 2. `mattpocock/skills@teach` — 文档讲义路线的成熟度冠军

| 项 | 内容 |
|----|------|
| 体量 | 单 skill，零外部依赖，纯 HTML + Markdown |
| 成熟度 | **784.8K installs / 282.5K stars** / MIT / 三家审计全 Pass / 2026-10-09 推送 |
| 产出 | 有状态教学工作区：`MISSION.md`（为什么学，所有教学据此落地）→ `lessons/*.html`（单点课程，一次讲一个紧密范围的东西）→ `reference/*.html`（可打印速查卡）→ `learning-records/*.md`（学习记录，据此算最近发展区）→ `RESOURCES.md` → `NOTES.md` |
| 适用 | 一个知识点要跨多次会话学透；内容按你的水平推进而非从头讲 |
| 不适用 | 视频、动画 — 明确不含 |

**优势**：安装量与审计证据在本报告里最好；结构是"状态化的"，不是一次性输出。
**与本仓库关系（已核对，非"原样拷贝"）**：仓库已有的 `grill-with-docs`、`domain-modeling`、`grilling` 与 `teach` 同出一源，但本地版是**改版**且**落后上游**：`domain-modeling` 把上游的 `GLOSSARY.md` 改成了本地 `CONTEXT.md`；`grilling` 少一句上游新增的 "Word each question so \"yes\" accepts your recommended answer"。所以"同源"成立，"体例一致"成立，但**本地版与上游已分叉**——装 `teach` 不会冲突，将来若要同步上游改动需逐条比对。

### 3. `heygen-com/hyperframes@faceless-explainer` — 要成品视频就上它

| 项 | 内容 |
|----|------|
| 体量 | **仓库约 660 MB 中的一部分**；依赖 `npx hyperframes` CLI 工具链 |
| 成熟度 | faceless-explainer 403.2K installs（核心 `hyperframes` 861.9K、`hyperframes-cli` 903.2K、`hyperframes-animation` 754.7K）/ 59.7K stars / **Apache-2.0** / 三家审计全 Pass / 2026-10-10 推送 |
| 产出 | 一段文字 → 选设计系统 → 教学故事板 `STORYBOARD.md` + `SCRIPT.md` → 音频元数据 → 逐帧 HTML composition（`compositions/frames/NN-*.html`）→ **`renders/video.mp4`**；配套 `/media-use` 从 HeyGen 目录取 BGM / SFX / 图片与官方 logo |
| 分帧机制 | Step 5 每帧派一个 sub-agent 做，设计规则与动效规则不写在主 skill 里 |
| 适用 | 目的就是一段能发出去的讲解视频（topic explainer / concept breakdown / how-to / listicle） |
| 不适用 | 只想写文档和图 — 属杀鸡用牛刀 |

**优势**：端到端流程最完整（brief → 设计系统 → 故事板 → 配音 → 帧 → 渲染），并自带素材渠道。
**局限**：仓库体积与工具链最重；素材 / BGM 走 HeyGen 目录，可能涉及账号或额度；skill 自带"保持新鲜度"的 update 流程，属于需要维护的依赖。

---

## 第二梯队：补某个特定媒介

### 4. `remotion-dev/skills` — 用 React 代码逐帧写视频

| 项 | 内容 |
|----|------|
| 成熟度 | `remotion-create` 142.7K / `remotion-render` 143.4K / `remotion-captions` 140.4K / `remotion-markup` 137K installs；仓库 5.0K stars；三家审计全 Pass；2026-10-07 推送 |
| 许可 | **仓库未检出 LICENSE 文件**；Remotion 本体对公司使用收费 — 商用前必须自行确认授权 |
| 适用 | 已经决定用 React 写动画、需要对帧级精细控制 |
| vs hyperframes | Remotion 是"引擎"，不给设计系统与教学故事板；hyperframes 是"流水线" |

### 5. `anthropics/knowledge-work-plugins@create-viz` — 数据图表最稳的一件

| 项 | 内容 |
|----|------|
| 成熟度 | 5.1K installs / **27.8K stars** / Apache-2.0 / 三家审计全 Pass / 2026-10-09 推送 |
| 出品 | Anthropic 官方 |
| 产出 | Python 出版级图表：按数据选图型、报告或演示用静态图、需要 hover/zoom 的交互图 |
| 边界 | 只做图；不管讲解结构，也不产动画 |

### 6. `tt-a1i/archify@archify` — 架构 / 流程 / 时序 / 状态图 → 可探索 HTML

| 项 | 内容 |
|----|------|
| 成熟度 | **144.3K installs / 81.2K stars** / MIT / 三家审计全 Pass / 2026-10-10 推送 |
| 产出 | 内联 SVG 的独立 HTML（明暗主题、可选 trace 动效），导出 PNG / JPEG / WebP / SVG / **WebM**；可吃纯语言描述，也可吃粘贴进来的 Mermaid flowchart / sequenceDiagram / stateDiagram 并美化 |
| 适用 | 系统架构、基础设施、云与安全拓扑、数据管线、状态机，以及"有步骤 / 有角色 / 有来回"的日常事 |
| 不适用 | 数值图表与仪表盘 |
| 代价 | 仓库约 660 MB |

### 7. `samber/developer-relations-skills@technical-video-script` — 只产脚本，不渲染

| 项 | 内容 |
|----|------|
| 成熟度 | 3.8K installs / **仓库仅 2 stars** / MIT / 三家审计全 Pass / 2026-09-28 推送 |
| 产出 | 双栏"可开拍"脚本：视觉 / 旁白 beat sheet、30 秒钩子、代码上屏节奏、章节、时长预算、无障碍旁白、cut list、带单一 CTA 的 YouTube 描述；也给 2–5 分钟动效讲解做 storyboard |
| 可溯源 | 引用的数字（如 Guo / Kim / Rubin 2014 的 6.9M 观看会话研究）在 `references/published-findings.md` 中可查，并明确标出哪些阈值是自己定的 |
| 适用 | 在花渲染成本之前，先把"讲什么、按什么顺序、每一拍画面变什么"定死 |
| 优势 | 纯文本产物、零渲染依赖，返工成本最低 — 值得作为任何视频任务的第一步 |

---

## 第三梯队：低验证或有硬伤（能用，但先看再用）

| Skill | 数据 | 硬伤 / 风险 |
|-------|------|-------------|
| `iart-ai/data-animation-skills`（`animated-infographic` 约 790、`presentation-video` 769、`chart-animation`） | MIT / 三家审计全 Pass / **仓库仅 7 stars** / 2026-06-22 推送 | 装量三位数、无社区验证；做信息图序列动画、幻灯片转视频、bar chart race |
| `MiniMax-AI/MiniMax-H3@papercraft-stop-motion-explainer` | 3.1K installs / 9.7K stars / 三家审计全 Pass | frontmatter 明写 **"Requires the MiniMax Hub agent; not portable to generic agent harnesses"** — 本机跑不了，只能当 prompt / storyboard 模板参考；许可未检出 |
| `backnotprop/plannotator@plannotator-visual-explainer` | 10.8K installs / 9.3K stars / Apache-2.0 | **三家审计全 Warn**；且强制经 Plannotator 批注 UI 交付（"Do NOT use `open` / `xdg-open`"）— 要讲解能力直接用它的上游 `visual-explainer`，不必装宿主 |
| `Agents365-ai/drawio-skill@drawio-skill` | 4.9K installs / 10.0K stars / MIT / **Snyk Warn** | 产出可编辑 `.drawio`（架构 / UML / ERD / 时序 / BPMN / 网络 / 泳道）；核心 IR 与 XML 只要 Python 3，原生导出要 draw.io 桌面版。要"能改的图"选它，要"好看的讲解页"选 archify |
| `coldteadotai/pr-lens@eli5` | 约 610 installs / 1.9K stars / MIT / **Snyk Warn** | 把代码库 / 文件夹 / PR 讲给完全不懂的人，产物是 PR Lens canvas，需宿主应用 |
| `antvis/chart-visualization-skills@chart-visualization` | 6.3K installs / 506 stars / MIT / 三家审计全 Pass | 中文描述，柱 / 折 / 饼 / 散点 / 雷达 / 桑基 / 思维导图 / 流程图；**通过 curl 调 AntV 外部 API 生成图片** — 离线或内网不可用 |
| `sanyuan0704/sanyuan-skills@book-study` | 3.3K installs / 3.9K stars / MIT / 三家审计全 Pass | 读书教练（ingest / query / review / compare / status，含知识编译、掌握度测试、间隔重复）；**2026-05-11 后未再推送**；适合知识体系，不适合单点 |

---

## 明确排除

### 名字最像、实际无关：`emilkowalski/skills`

`animation-vocabulary`（199K）、`apple-design`（198.1K）、`improve-animations`（182.4K）、`find-animation-opportunities`（168.4K）、`animate`（129.8K）全部是**网页 UI 动效**，不是"把知识讲给人听"。安装量很高，最容易误买。

### 复制分发：HyperFrames 系列 fork

`101-skills/superpowers@ai-video-generation`（715.8K）、`qu-skills`（399.6K）、`magentosh`（388.2K）、`skills-shell`（255.1K）、`its-a-skill-issue`（248.3K）、`bankai-skills`（233.8K）等是同一个 skill 的多份复制，origin 不明、与上游 `heygen-com/hyperframes` 无背书关系。装就装上游。

### 生态空白：manim / 3Blue1Brown 类数学动画

按 `manim`、`math animation` 查询，返回的全是 UI 动效与通用视频渲染，**没有成熟的数学动画讲解 skill**。仅检索到一个 PyPI 上的第三方包（未验证，不建议直接用）。需要这类产物时，用 `visual-explainer` 的手绘 SVG + 逐帧渲染自建，或按 `skill-creator` 自建 skill。

---

## 对比维度总结

### 按媒介覆盖面

| 覆盖 | Skill |
|------|-------|
| 文档 + 图 + 动画 + 视频 | `visual-explainer` |
| 文档 + 图（Mermaid / ASCII） | 本仓库 `mindspring-lab`（限 `algorithms/`）、`tenetlang-notes`（限 `languages/studies/`） |
| 文档（HTML 讲义） | `teach`、`book-study` |
| 视频（成片） | `hyperframes`、`remotion-dev/skills` |
| 视频（仅脚本） | `technical-video-script` |
| 仅图 | `create-viz`（数据）、`archify`（架构）、`drawio-skill`（可编辑） |

### 按成熟度证据强度

| 证据强度 | Skill |
|----------|-------|
| 高安装量 + 高 stars + 审计全 Pass | `teach`（784.8K / 282.5K）、`hyperframes`（403.2K / 59.7K）、`archify`（144.3K / 81.2K）、`remotion-dev/skills`（142.7K / 5.0K） |
| 官方出品 | `create-viz`（Anthropic，27.8K stars） |
| stars 高但生态分发少 | `visual-explainer`（10.3K stars / 610 installs） |
| 低验证 | `data-animation-skills`（7 stars）、`technical-video-script`（2 stars） |
| 审计有 Warn | `plannotator-visual-explainer`（3 Warn）、`drawio-skill`（1 Warn）、`pr-lens`（1 Warn） |

### 按产物形态（决定它进不进仓库）

| 形态 | Skill | 影响 |
|------|-------|------|
| 纯文本、可 diff、可入库 | `visual-explainer` 的 HTML/图、`teach` 的讲义、`mindspring-lab` 的素材脚本 | 适合本仓库"文档即产物"的习惯 |
| 二进制成品 | MP4 / PPTX / PNG（`visual-explainer`、`hyperframes`、`remotion`） | 需决定是否入库、是否加 `.gitignore` |
| 需宿主应用 | `plannotator-visual-explainer`、`pr-lens`、`MiniMax-H3` | 本机不可用或需额外安装 |

### 与本仓库（Mosaic）的适配

- **继续写 `algorithms/` 的实验讲解**：不要换 skill。`mindspring-lab` 已是该目录的唯一权威规范（两篇式 README + 脚本生成概念图 / 对比图 + Mermaid 流程图 + 过程 GIF + 与代码对账 + 校验脚本），换任何外部 skill 都会破坏现有体例。
- **要对外成品（网页 / 幻灯片 / 视频）**：`visual-explainer` + `create-viz`。
- **要跨会话学透一个算法族**：`teach`（结构）+ `mindspring-lab`（算法侧对账）。
- **要真视频产线（BGM / 素材 / 配音 / 成片）**：`hyperframes`，并接受工具链与素材依赖。
- **无论哪条**：先用 `technical-video-script` 把脚本定死再进渲染。

---

## 环境与安装（本机实测，2026-10-10）

### 三个必须知道的环境事实

1. **`npx skills add` 在本机必定失败。** 它走 HTTPS 克隆，而本机 `github.com:443` 与 `raw.githubusercontent.com` 全部超时（`curl` 返回 `000`）；实测装 `teach` 直接停在 `Failed to clone repository`。
2. **但 SSH 通道可用。** `git@github.com:` 可正常 `clone`（本报告 14 个候选仓库即由此获得），`codeload.github.com` 也可达（HTTP 200）。
3. **`~/.npm` 含 root 属主文件**，导致 `npx` / `npm` 报 `EPERM`。临时绕过：设 `npm_config_cache=/tmp/npmcache-dsh`；根治：`sudo chown -R 501:20 ~/.npm`。

### 本机已具备的视频工具链

| 组件 | 状态 |
|------|------|
| Node.js | v25.6.0 |
| pnpm | 11.17.0 |
| ffmpeg | `/opt/homebrew/bin/ffmpeg` |
| Playwright 浏览器 | 缓存已有 `chromium-1208` / `chromium-1234` / `chromium_headless_shell-*` |
| Google Chrome | 已安装（`/Applications/Google Chrome.app`） |
| npm registry | `registry.npmjs.org` 可达（HTTP 200） |
| Python 绘图 | matplotlib + Pillow 可用（GIF 路径） |

### 可用安装路径（替代 `npx skills add`）

```bash
# 1. SSH 浅克隆（含 blob 过滤，减速）
git clone --depth 1 --filter=blob:none git@github.com:<owner>/<repo>.git /tmp/<repo>

# 2. 把 skill 目录复制进仓库 skill 目录
cp -R /tmp/<repo>/<skill 路径>/. .dsh/skills/<skill-name>/

# 3. 校验：frontmatter 有 name / description，即会被本会话自动识别（无需重启）
sed -n '1,10p' .dsh/skills/<skill-name>/SKILL.md
```

### visual-explainer 的两个坑

1. **`visual-explainer-video` 这个 bin 尚未发版。** npm 上发布的 0.12.0 只含两个 bin：`visual-explainer-mcp` 与 `visual-explainer-pptx`；而仓库 HEAD 的 `package.json`（`version` 同样写 0.12.0）已包含 `visual-explainer-video`（`./plugins/visual-explainer/video/render.mjs`）并把 `playwright-core` 声明为 peer —— 即**发布包落后于仓库**。因此 skill 自述的 `npx -y -p visual-explainer -p playwright-core visual-explainer-video <deck.html>` **当前会失败**。可用替代（已实测）：

   ```bash
   node .dsh/skills/visual-explainer/video/render.mjs <deck.html> <out.mp4>
   ```

2. **配音需要 speech API key**，本机未配置 → 视频为静音 + 自动字幕。要旁白需先接 TTS。另外 `playwright-core` 需落在 skill 目录的任一上级 `node_modules` 中（本仓库放在 `.dsh/node_modules/`）。

---

## 当前落地状态

2026-10-10 分两步落地：**先一次装齐 21 个目录，同日卸载 17 个，最终保留 5 个**。卸载不是能力判断改变，而是运行时前置过重的成本判断（见下）。

| 推荐项 | 目录（文件数） | 能否立即使用 | 剩余前置 / 说明 |
|--------|----------------|--------------|------------------|
| `visual-explainer` | `visual-explainer`（34） | ✅ 已实测出 1080p MP4 | 配音需 speech API key；`visual-explainer-video` bin 未发版，走 `node …/video/render.mjs` |
| `teach` | `teach`（6） | ✅ 纯文本 | 不在会话 skill 目录中：frontmatter 声明 `disable-model-invocation: true`，只能由人显式调用（`/teach <主题>`） |
| `archify` | `archify`（315） | ✅ 自带 `bin/archify.mjs` | 无运行时依赖（`devDependencies` 仅上游生成用，不必安装） |
| `create-viz` | `create-viz`（1） | ✅ | 仅需 Python + matplotlib / pandas（本机已有） |
| `technical-video-script` | `technical-video-script`（6） | ✅ 纯文本 | 只产脚本、不渲染，故无前置 |

合计 **5 个目录 / 363 文件 / 12 MB**。

### 评估后卸载（17 个目录）

| 被卸载 | 件数 | 卸载原因 |
|--------|------|----------|
| `hyperframes` 家族：`faceless-explainer` + `hyperframes` + `hyperframes-animation` + `hyperframes-creative` + `media-use` | 5 | 出片依赖 `npx hyperframes` CLI（SKILL.md 中出现 24 次 `media-use`、13 次 `transcribe`、11 次 `auth`、9 次 `tts`）与 HeyGen 登录；不接受这两个前置时，这 5 件只是文档 |
| `remotion` 整包：best-practices / captions / create / docs / interactivity / maps / markup / multimedia / render / saas / studio / upgrade | 12 | 只是知识文档；要渲染需自建 Remotion 工程并装 Remotion 包；且其仓库**未检出 LICENSE**，商用需自查授权 |

**能力判断不变**（梯队表照旧），这里记录的是"装进来值不值"的结论：两者的前置成本都超出当前需求；需要时按下面的闭包关系整装。

### 一次装齐时的闭包关系（留档，重装按此装）

7 个推荐项对应 21 个目录，因为其中两项是"套件"而非单件：

| 推荐项 | 完整闭包 | 为什么必须整套 |
|--------|----------|----------------|
| `faceless-explainer` | 5 件（自身 + `hyperframes` + `hyperframes-animation` + `hyperframes-creative` + `media-use`） | 它的 SKILL.md 有 20+ 条 `../<兄弟>/...` 引用（brief-contract、frame-worker-core、storyboard-format、`hyperframes-animation/rules/`、`hyperframes-creative/references/`、`media-use/audio/references/tts.md`），单装自己全是断链 |
| `remotion-dev/skills` | 12 件 | 该仓库本身就是 12 件套件（best-practices 自称 "Router for all Remotion skills"），各件用 `../remotion-<x>/REFERENCE.md` 交叉引用 |
| 其余 5 项 | 各 1 件 | 无外部引用 |

### 装机校验结果（卸载前对 21 个目录做的）

| 检查 | 结果 |
|------|------|
| 悬空相对引用 | **21 个全部 0 条**（脚本逐个解析 Markdown 相对链接并验证目标存在；上游基准同为 0） |
| 搬迁后为何不断链 | 上游布局 `<repo>/skills/<name>/` 与本仓库 `<repo>/.dsh/skills/<name>/` **同在仓库根下第一层**，因此 `../兄弟/`、`../../../REFERENCE.md` 这类相对写法原样成立。这是选 `.dsh/skills/` 作为安装位置的额外收益 |
| frontmatter | 21 个全部具备 `name` + `description` |
| 被会话识别 | 立即生效（无需重启）；`teach` 因上述 `disable-model-invocation` 是唯一不进目录的 |

### 两个副作用（其中一个随卸载消失）

- **触发词重叠（已随卸载消失）**：装齐时 `hyperframes`（自称 "Mandatory entry point … any request to make, create, edit, animate, or render a video"）、`remotion-best-practices` 与 `visual-explainer` 都会抢"做个视频"这类请求。卸载 17 件后，做视频只剩 `visual-explainer` 一家，`archify` 只管图、`technical-video-script` 只写脚本，冲突不再存在。
- **补入的 1 个外部文件（保留）**：`.dsh/CONNECTORS.md`（1 KB）—— `create-viz` 的 SKILL.md 引用 `../../CONNECTORS.md`，从 `.dsh/skills/create-viz/` 出发正好解析到该位置。其内容讲的是 `~~category` 工具占位符，提到的 `.mcp.json` 在本次安装中并不存在。

### 目录与忽略规则

- `.dsh/skills/` 是**被 git 跟踪的**（原有 60 个文件；本次净增 5 个目录、卸载后复归此数）。
- `visual-explainer` 的视频依赖 `playwright-core`（1.64.0 / 13 MB）装在 `.dsh/node_modules/`，由新建的 `.dsh/.gitignore`（`node_modules/`）排除，不入库；顶层 `.gitignore` 的所属清单同步登记了该文件。

### 冒烟测试记录（验证"真能出 MP4"）

> 演示文件（deck.html / out.mp4 / 抽帧）已按清理要求删除，此处仅留档数据。

```text
输入：3 幕 A* 演示 deck（/tmp/ve-demo/deck.html，1280×720 CSS）
命令：node .dsh/skills/visual-explainer/video/render.mjs /tmp/ve-demo/deck.html /tmp/ve-demo/out.mp4
耗时：25 s（渲染进度 10% → 100%）
产物：h264 / 1920×1080 / 30 fps / 657 帧 / 21.9 s / 355 KB
表现：静音 + 自动字幕（`.ve-caption`），抽帧检查版式与字幕正常
```

---

## 安装命令汇总

本机 HTTPS 通道不通（见上），因此全部走 SSH 克隆 + 目录复制。以下为**实际执行过的命令**（`$S` 为各仓库的克隆根）。

```bash
S=/tmp/skillscan   # 各候选仓库的 SSH 浅克隆（--depth 1 [--filter=blob:none]）

# visual-explainer（单件）
cp -R $S/nicobailon_visual-explainer/plugins/visual-explainer/. .dsh/skills/visual-explainer/

# teach（单件）
cp -R $S/mattpocock_skills/skills/productivity/teach/. .dsh/skills/teach/

# faceless-explainer 及其依赖闭包（5 件，必须同层相邻）—— 2026-10-10 已卸载
for s in faceless-explainer hyperframes hyperframes-animation hyperframes-creative media-use; do
  cp -R $S/heygen-com_hyperframes/skills/$s/. .dsh/skills/$s/
done

# remotion 整包（12 件）—— 2026-10-10 已卸载
for s in $S/remotion-dev_skills/skills/*/; do
  cp -R "$s". .dsh/skills/"$(basename "$s")"/
done

# create-viz / archify / technical-video-script（各单件）
cp -R $S/anthropics_knowledge-work-plugins/data/skills/create-viz/. .dsh/skills/create-viz/
cp -R $S/tt-a1i_archify/archify/.                                    .dsh/skills/archify/
cp -R $S/samber_developer-relations-skills/skills/technical-video-script/. \
                                                                     .dsh/skills/technical-video-script/

# create-viz 的跨目录引用补齐（否则 SKILL.md 里 ../../CONNECTORS.md 悬空）
cp $S/anthropics_knowledge-work-plugins/data/CONNECTORS.md .dsh/CONNECTORS.md
```

```bash
# 若网络放行 HTTPS（本机不可用，供其他机器参考）
npx skills add https://github.com/nicobailon/visual-explainer --skill visual-explainer
npx skills add https://github.com/mattpocock/skills --skill teach
npx skills add https://github.com/heygen-com/hyperframes --skill faceless-explainer
```

## 参考链接

- [visual-explainer](https://skills.sh/nicobailon/visual-explainer/visual-explainer)
- [teach](https://skills.sh/mattpocock/skills/teach)
- [faceless-explainer](https://skills.sh/heygen-com/hyperframes/faceless-explainer)
- [remotion-render](https://skills.sh/remotion-dev/skills/remotion-render)
- [create-viz](https://skills.sh/anthropics/knowledge-work-plugins/create-viz)
- [archify](https://skills.sh/tt-a1i/archify/archify)
- [technical-video-script](https://skills.sh/samber/developer-relations-skills/technical-video-script)
- [plannotator-visual-explainer](https://skills.sh/backnotprop/plannotator/plannotator-visual-explainer)
- [drawio-skill](https://skills.sh/Agents365-ai/drawio-skill/drawio-skill)
- [chart-visualization](https://skills.sh/antvis/chart-visualization-skills/chart-visualization)
- [data-animation-skills](https://skills.sh/iart-ai/data-animation-skills/animated-infographic)
- [papercraft-stop-motion-explainer](https://skills.sh/MiniMax-AI/MiniMax-H3/papercraft-stop-motion-explainer)
- [pr-lens / eli5](https://skills.sh/coldteadotai/pr-lens/eli5)
- [book-study](https://skills.sh/sanyuan0704/sanyuan-skills/book-study)
