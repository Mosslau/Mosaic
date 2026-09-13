# TenetLang 文档站

把仓库里 `languages/`、`analysis/`、`tenet/` 三个目录族的 Markdown 构建成卡片式的
[VitePress](https://vitepress.dev) 站点：六门语言 → 设计分析 → Tenet 语言与编译器。

## 本文档的边界

本文档只讲站点工程：内容如何被转换成页面、主题与导航怎么组织、如何构建与预览。
它不规定内容本身怎么写。笔记的阶段结构、四层交付物与排版规范在
`.dsh/skills/tenetlang-notes/SKILL.md`。两者冲突时，内容格式以那份为准，站点如何呈现以本文档为准。

## 快速开始

```bash
cd website
npm install
npm run dev        # 启动开发服务器（内置文档监听）
```

打开终端里输出的地址（默认 <http://localhost:5173>）。

**你只需要改仓库里的 Markdown。** `npm run dev` 会监听 `languages/`、`analysis/`、`tenet/`、
站点 `content/` 与仓库根 `README.md`；原文一保存就自动重跑同步，VitePress 的 HMR 随即刷新页面。
不需要手工执行 `npm run sync`，更不需要去动 `docs/` 里的任何文件。

```bash
npm run sync       # 手工做一次同步与结构解析（也会报告失效链接）
npm run dev:once   # 不监听，启动时同步一次
npm run build      # 同步 + 生产构建，产物在 .vitepress/dist
npm run preview    # 预览生产构建
```

## 内容从哪来

**仓库里的 Markdown 是唯一真源，`docs/` 是纯产物目录。**

数据是单向流动的，不存在「两份需要同步维护的文档」：

```
languages/ analysis/ tenet/  +  根 README.md          ← 唯一真源（你只改这里）
        │
        │  scripts/sync-docs.mjs
        ▼
website/docs/                                          ← 生成物：已被 .gitignore 忽略
        │                                                可随时删除，下次同步/构建重建
        ▼
http://localhost:5173                                  ← 站点
```

`docs/` 不进版本库（`git add website/` 只带源文件，不含任何产物），所以你永远不会面对
「改了原文还要不要改副本」的问题：那份副本在构建意义上不存在。

需要重新生成时，删掉整个目录也可以：`rm -rf docs && npm run sync`。

```
website/
├── content/              ← 手写页面（首页、各栏总览、logo/favicon），会被复制进 docs/
├── scripts/sync-docs.mjs ← 同步 + 结构解析
├── scripts/dev.mjs       ← 开发服务器：监听原文变化并自动重同步
├── docs/                 ← 生成物，已被 .gitignore 忽略，可随时删除重建
│   ├── languages/…       ← 从 repo 的 languages/ 复制
│   ├── analysis/…        ← 从 repo 的 analysis/ 复制
│   ├── tenet/…           ← 从 repo 的 tenet/ 复制
│   └── about.md          ← 从 repo 根 README.md 复制
└── .vitepress/
    ├── config.mts        ← 站点配置（导航、侧边栏、搜索、Markdown 管线）
    ├── data/curriculum.json  ← 生成物：课程结构，供导航与卡片组件消费
    └── theme/            ← 自定义主题
```

同步脚本做四件事：

1. **复制**三个内容族与根 README 的全部 Markdown，并把 `README.md` 映射为 `index.md`，
   使 `/analysis/py/` 这类目录链接能正确落到页面上；
2. **改写链接**：`](…/README.md)` → `](…/index.md)`；指向未收录源码（`.py`/`.rs`/`.yml`/源码目录）
   的链接登记进 `ignoreDeadLinks` 白名单，同时报告真正失效的链接；
3. **解析结构**：从每门语言的 Roadmap 里抽出阶段编号、标题、目标、正文链接、阅读时长和
   代码层入口（示例 / 练习 / 项目），产出 `curriculum.json`；
4. **生成**每种语言的卡片总览页。

结构数据写成 JSON 而不是 `.mjs` 是有意的：`config.mts` 要在 Node 侧同步读取它来生成导航与侧边栏，
而主题组件通过 Vite 的 JSON 导入消费同一份，两边读的是同一个文件。

同步是**增量**的：只有内容真的变了才落盘（脚本末尾会打印「写入变更 N 个文件」），
源文档被删除或改名留下的残留页会被自动清理。这样监听模式下改一篇文档只影响那一页，
不会触发整站 HMR。

## 改内容时要动什么

`npm run dev` 下改文档不需要手动做任何事（监听 + 增量同步）；**生产构建不区分内容与代码，
任何内容变化都要重新 `npm run build`**。区别在于是否要碰代码，以及 dev 下是否即时：

| 操作 | 改代码 | dev 下 |
|---|---|---|
| 修改文档正文 | 否 | 即时 |
| 新增文档 | 否 | 即时（新路由与 `docs/` 产物都会生成） |
| 新增阶段 | 否¹ | **阶段卡片即时**；导航/侧边栏要**手动重启 dev server** |
| 新增分析笔记 | 否² | 同上 |
| 新增一门语言 | **是，见下** | 同上 |

¹ 阶段要在 roadmap（`languages/<语言>/<语言>.md`）里补一个 `## N. <名>阶段` 段，并写上
`> 📖 详细展开版见 [phNN-主题/NN-主题.md](./phNN-主题/NN-主题.md)`，解析器读的就是这两处约定。

² 分析笔记要在 `analysis/<语言>/README.md` 的表格里补一行；分析卡片与侧边栏都读那张表。

**为什么结构性变更要重启 dev server**：导航与侧边栏由 `config.mts` 在启动时从
`curriculum.json` 生成，而 VitePress 只在 `config.mts` 本身（或它被 esbuild 记录为依赖的文件）
变化时重启：JSON 是被内联进 config bundle 的，不在它的依赖清单里，所以改了不会自动重启。
卡片网格走的是另一条路（组件 `import` 该 JSON，由 Vite HMR 更新），因此即时。

新增一门语言要动三处代码：

1. `scripts/sync-docs.mjs` 的 `LANGUAGES` 数组加一项 `{ id, name, token }`；
2. `theme/styles/tokens.css` 里给 `--t-<token>` 在 `:root` **和** `html.dark` 各加一行
   （两处都要，否则深色模式下该色未定义）；
3. 若要为它建分析台，还要把它加进 `scripts/sync-docs.mjs` 的
   `const analysis = [...]` 数组，并在 `parseAnalysis` 的显示名映射里补一项。

其余（导航、侧边栏、卡片网格、首页汇流台）全部按数据自动生成。

## 视觉系统

设计隐喻是**工程图纸 / 蓝图**：知识库是图纸，六门语言各占一条线，Tenet 是它们汇成的那个点。

- `theme/styles/tokens.css` — 纸面/墨色、六种语言的身份色、尺度与动效曲线。
  浅色是纸面，深色是蓝图（cyanotype）。语言色是**语义色**，在导轨、卡片骨架、字标处始终指向同一门语言。
- `theme/styles/base.css` — 站点外壳（导航、侧边栏、正文排印），以及把设计令牌接到 VitePress 主题变量上。
- `theme/styles/card.css` — 共享的「图纸格」版式（`.section` + `.lattice`），
  卡片之间共用 1px 分隔线，不用阴影堆叠。
- `theme/styles/landing.css` — 落地页（`layout: page`）的版心与节奏。
- `theme/components/` — 首页的汇流台（`ConvergenceHero`）、三条主线、语言卡片网格、
  分析卡片网格、编译器卡片网格，以及每门语言的阶段卡片页（`LanguageBoard`）。

## 两个容易踩的坑

- **Vue 插值**：正文里的 `{{ … }}`（Go 模板、C 初始化列表、CI 的 `${{ }}`）会被 Vue 当成插值。
  所有行内 `<code>` 都加了 `v-pre`。
- **泛型尖括号**：`Stack<T>`、`Arc<Mutex<T>>` 会被 markdown-it 当成原始 HTML 标签，
  既会让构建因「标签未闭合」失败，也会在浏览器里被吞掉。管线里把它们降级为转义文本。

## 全文搜索

用 VitePress 内置的本地搜索（MiniSearch），无需外部服务。MiniSearch 默认按空白与标点切词，
中文长句会变成一个整词导致搜不到，因此 `config.mts` 注入了 `Intl.Segmenter` 词级分词器，
构建期索引与浏览器端查询共用同一套切分。该分词的写法受 VitePress 的函数序列化机制约束，
详见 `config.mts` 内的注释。

## 侧边导航栏（折叠 / 调宽）

VitePress 默认主题在桌面端没有整栏折叠，也没有运行时调宽（汉堡按钮在 `@media (min-width: 768px)`
里就是 `display: none`，只有 <960px 的抽屉）。这两项由 `theme/components/SidebarResizer.vue` 提供：
折叠状态与宽度记在 `localStorage`，由 `config.mts` 注入的内联脚本在首次绘制前恢复，避免闪动。
把手的位置计算、以及折叠态为什么不依赖过渡动画，都写在那个组件的注释里。

一个尚未采纳的设计选择：≥1440px 视口下 VitePress 会让侧边栏随屏幕变宽（1920 视口下约 516px）。
若要在大屏上也固定 276px，需要覆盖 `@media (min-width: 1440px)` 下 `.VPSidebar` /
`.VPContent.has-sidebar` / `.VPNavBar.has-sidebar .content` 三处的 `calc()` 公式。本仓库没有这样做，
因为那会改变 VitePress 让整页在大屏上居中的布局。

## 链接校验

`npm run sync` 逐条校验所有相对链接，并分三类处理：

- **站内页面**：正常解析；
- **未收录的源码资产**（`.py`/`.rs`/`.yml`/只有源码的目录等）：登记进 `ignoreDeadLinks`，链接保留，
  在站点上点开会 404，与 GitHub 上的行为一致；
- **失效链接**（目标路径根本不存在）：在同步输出里以 ⚠️ 列出，生产构建也会因死链直接失败。

各分类的条数以 `npm run sync` 的输出为准，本文档不复述具体数字。

## 改完怎么验证

1. `npm run build` 必须零警告结束。死链、Vue 模板错误都在这一步暴露；
2. `npm run sync` 的输出里不应出现 ⚠️ 行，那是失效链接清单；
3. 结构性改动（新增语言、新增阶段）之后，确认导航与侧边栏已跟上。它们由配置生成，不随 HMR 更新，
   需要重启 `npm run dev`；
4. 想确认产物确实可丢弃：`rm -rf docs && npm run sync`，再构建一次应得到相同结果。
