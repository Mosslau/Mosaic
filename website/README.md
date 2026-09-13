# TenetLang 文档站

把仓库里 `languages/`、`analysis/`、`tenet/` 三个目录族的 Markdown 构建成卡片式的
[VitePress](https://vitepress.dev) 站点：六门语言 → 设计分析 → Tenet 语言与编译器。

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

`docs/` 不进版本库（`git add website/` 只会带上 24 个源文件），所以你永远不会面对
「改了原文还要不要改副本」的问题——那份副本在构建意义上不存在。

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

同步是**增量**的：只有内容真的变了才落盘（脚本末尾会打印「写入变更 N 个文件」），
源文档被删除或改名留下的残留页会被自动清理。这样监听模式下改一篇文档只影响那一页，
不会触发整站 HMR。

想加一门语言，只需在 `scripts/sync-docs.mjs` 的 `LANGUAGES` 里补一项，
并在 `theme/styles/tokens.css` 里给它一个身份色——导航、侧边栏、卡片网格会自动跟上。
（新增/删除阶段会改变 `curriculum.json`，侧边栏依赖它；这种情况 VitePress 会自行重启
dev server 或需你手动重启一次，改内容则完全即时。）

## 视觉系统

设计隐喻是**工程图纸 / 蓝图**：知识库是图纸，六门语言各占一条线，Tenet 是它们汇成的那个点。

- `theme/styles/tokens.css` — 纸面/墨色、六种语言的身份色、尺度与动效曲线。
  浅色是纸面，深色是蓝图（cyanotype）。语言色是**语义色**，在导轨、卡片骨架、字标处始终指向同一门语言。
- `theme/styles/card.css` — 共享的「图纸格」版式（`.section` + `.lattice`），
  卡片之间共用 1px 分隔线，不用阴影堆叠。
- `theme/components/` — 首页的汇流台（`ConvergenceHero`）、三条主线、语言卡片网格、
  分析卡片网格、编译器卡片网格，以及每门语言的阶段卡片页（`LanguageBoard`）。

## 两个容易踩的坑（已在管线里处理）

- **Vue 插值**：正文里的 `{{ … }}`（Go 模板、C 初始化列表、CI 的 `${{ }}`）会被 Vue 当成插值。
  所有行内 `<code>` 都加了 `v-pre`。
- **泛型尖括号**：`Stack<T>`、`Arc<Mutex<T>>` 会被 markdown-it 当成原始 HTML 标签，
  既会让构建因「标签未闭合」失败，也会在浏览器里被吞掉。管线里把它们降级为转义文本。

## 全文搜索

用 VitePress 内置的本地搜索（MiniSearch），无需外部服务。MiniSearch 默认按空白与标点切词，
中文长句会变成一个整词导致搜不到，因此 `config.mts` 里注入了 `Intl.Segmenter` 词级分词器——
它同时作用于构建期的索引和浏览器端的查询。注意该函数会被序列化进页面（`new Function` 还原），
必须自包含，不能引用模块作用域变量。

## 侧边导航栏（折叠 / 调宽）

VitePress 默认主题在桌面端**没有**整栏折叠，也没有运行时调宽（汉堡按钮在 `@media (min-width: 768px)`
里就是 `display: none`，只有 <960px 的抽屉）。这两项由 `theme/components/SidebarResizer.vue` 补上：

| 操作 | 方式 |
|---|---|
| 折叠整栏 | 悬停侧边栏右缘的细线，点出现的箭头；收起后箭头常驻视口左缘，点它展开 |
| 拖拽调宽 | 拖动右缘细线，范围 200–440px，**双击复位**到 276px |
| 键盘 | Tab 聚焦细线后用 ←/→ 调 8px，`Shift` + ←/→ 调 32px |
| 记忆 | 折叠状态与宽度存在 `localStorage`（`tenetlang:sidebar-collapsed` / `tenetlang:sidebar-width`） |

折叠按钮整体落在侧边栏**内侧**、右缘距分割线 16px，与侧边栏分组折叠箭头同一个内缩位置——
两者对齐而不是骑在线上。按钮与拖拽线是两个各自定位的元素，位置由 JS 实测侧边栏右缘后写入
`--line-x` / `--btn-x`。

两个实现要点：

- **把手位置实测而非复刻公式**：侧边栏在 ≥1440px 断点的宽度是
  `calc((100% - (max - 64)) / 2 + var(--vp-sidebar-width) - 32px)`，自己算容易算漏；
  改用 `getBoundingClientRect()` 实测右缘，任何断点/主题改动都自动跟随。
  折叠时不做测量（此刻侧边栏正在 `translateX(-100%)` 过渡中，会量到旧位置），直接钉在视口左缘。
- **折叠态不依赖过渡**：`visibility: hidden` + `pointer-events: none` 独立保证不可见不可交互，
  `transform` / `opacity` 只负责滑出动画——过渡被中断或降级也不影响功能。

折叠状态由 `config.mts` 注入的内联脚本在**首次绘制前**恢复，避免「先展开再收起」的闪动；
该脚本与组件共用同一组 localStorage 键，改键名需同步两处。

> 注意：≥1440px 视口下 VitePress 会让侧边栏随屏幕变宽（1920 视口下约 516px）。若希望大屏上也固定
> 276px，需要额外覆盖 `@media (min-width: 1440px)` 下 `.VPSidebar` / `.VPContent.has-sidebar` /
> `.VPNavBar.has-sidebar .content` 三处的 `calc()` 公式，属于本仓库尚未采用的设计选择。

## 链接校验

`npm run sync` 会逐条校验所有相对链接，并分三类处理：

- **站内页面** —— 正常解析；
- **未收录的源码资产**（`.py`/`.rs`/`.yml`/只有源码的目录等，共约 240 条）—— 登记进
  `ignoreDeadLinks`，链接保留，在站点上点开会 404，与 GitHub 上的行为一致；
- **失效链接**（目标路径根本不存在）—— 会在同步输出里以 ⚠️ 列出。

当前 570 篇文档共 1309 条相对链接，失效 **0** 条。

顺带修掉了仓库里原有的两处死链（`languages/java/ph15-spring-family/` 下少写了一层 `../`）：

- `exercises/README.md` → `../../ph13-database/exercises/README.md`
- `project/README.md` → `../../ph14-web-backend/project/README.md`

这两条修复后已从 `ignoreDeadLinks` 白名单中移除，因此现在由 VitePress 的死链检查真正把关。
