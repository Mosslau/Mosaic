# Agent Skills 选型对比：语言编码规范 & Markdown 规范

> 调研日期：2026-08-30。调研范围：Vercel skills 市场（skills.sh）、SkillHub、ClawHub，共审查 12 个候选 skill（全部通读原文）。
> 用途：为 TenetLang 项目（languages/ 学习笔记 + 代码示例）选择各语言编码规范与 Markdown 写作规范的参考 skill。

## TL;DR

| 领域 | 推荐 | 备选 |
|------|------|------|
| C++ 规范 | `affaan-m/ecc@cpp-coding-standards`（9.5K） | jeffallan@cpp-pro |
| Rust 规范 | `apollographql/skills@rust-best-practices`（16.7K） | ecc@rust-patterns |
| Go 规范 | `affaan-m/ecc@golang-patterns` | samber@golang-code-style（39.4K，生态最细） |
| Python 规范 | `affaan-m/ecc@python-patterns` | wshobson@python-code-style（13.9K） |
| Java 规范 | `affaan-m/ecc@java-coding-standards`（9.9K） | github@java-springboot（偏 Spring 框架） |
| C 规范 | **市场空白，建议自建** | han@c-systems-programming（系统编程教程，非规范） |
| Markdown 规范 | `josiahsiegel/claude-plugin-marketplace@markdown-style`（110） | kepano@obsidian-markdown（Obsidian 方言专用） |

**组合策略**：ECC 系列（第一组）统一体例、单文件全集，适合做参考目录基底；Rust 用 Apollo 官方版（权威背书最强）；Markdown 用 markdown-style（双层架构最严谨）。

---

## 第一组：规范文档型（推荐做参考目录）

### 1. `affaan-m/ecc@cpp-coding-standards` — C++ 规范 ⭐推荐

| 项 | 内容 |
|----|------|
| 体量 | 单文件 725 行，全部内联于 SKILL.md |
| 权威来源 | 基于 **C++ Core Guidelines**（isocpp 官方），每条规则锚定官方编号（P.1 / F.16 / C.20 / R.11…） |
| 结构 | 按 Core Guidelines 章节组织：哲学与接口 / 函数 / 类层次 / 资源管理 / 表达式语句 / 错误处理 / 常量 / 并发 / 模板 / 标准库 / 枚举 / 命名 / 性能 |
| 写法 | 每章 = 规则速查表 + DO/DON'T 代码对照 + Anti-Patterns 清单 |
| 亮点 | 末尾 19 条 Quick Reference Checklist（提交前自查表） |
| 版本覆盖 | C++17/20/23 |

**优势**：规则可溯源（编号直达 isocpp 原文），笔记引用时可直接写规则号。
**局限**：不覆盖构建系统深入配置（CMake 只有顺带提及）。

### 2. `affaan-m/ecc@rust-patterns` — Rust 规范

| 项 | 内容 |
|----|------|
| 体量 | 单文件 500 行 |
| 权威来源 | 无官方编号体系，社区惯用法总结 |
| 结构 | 所有权与借用 / 错误处理（thiserror vs anyhow）/ 枚举与模式匹配 / trait 与泛型 / 并发（Arc\<Mutex\<T\>\>、channel、async）/ crate 结构 |
| 写法 | 与 ECC 全系列一致：原则 + Good/Bad 代码对照 |

**优势**：与 ECC 其他语言体例统一。
**局限**：无官方规则编号；深度不如 Apollo 版（后者有 9 章 references 支撑）。

### 3. `affaan-m/ecc@golang-patterns` — Go 规范 ⭐推荐

| 项 | 内容 |
|----|------|
| 体量 | 单文件 676 行 |
| 权威来源 | Go 社区惯用法（Go Proverbs、Effective Go 精神） |
| 结构 | 核心原则（零值可用 / 接受接口返回 struct）/ 错误处理（wrapping、sentinel、errors.Is/As）/ 并发模式（worker pool、context、graceful shutdown、errgroup、防 goroutine 泄漏）/ 接口设计 / 包组织 / struct 设计（functional options、embedding）/ 性能 / 工具链 |
| 亮点 | 附 `.golangci.yml` 推荐配置；标准项目布局图；8 条 Go 谚语速查表 + 反模式清单 |

**优势**：Go 核心坑全覆盖（goroutine 泄漏、context 不放 struct、裸返回、panic 控制流），每个模式 Good/Bad 对照完整。
**局限**：不覆盖泛型（Go 1.18+ 类型参数）——这块 golang-pro 反而有。

### 4. `affaan-m/ecc@python-patterns` — Python 规范 ⭐推荐

| 项 | 内容 |
|----|------|
| 体量 | 单文件 751 行 |
| 权威来源 | PEP 8 + Python 之禅（"Explicit is better than implicit"） |
| 结构 | 核心原则 / 类型提示 / 错误处理 / 上下文管理器 / 推导式与生成器 / dataclass 与 namedtuple / 装饰器 |
| 写法 | Good/Bad 对照，强调"Readability Counts" |

**优势**：ECC 系列中体量最大，Pythonic 惯用法覆盖全面。
**局限**：工具链配置（ruff/mypy）深度不如 wshobson 版。

### 5. `affaan-m/ecc@java-coding-standards` — Java 规范 ⭐推荐

| 项 | 内容 |
|----|------|
| 体量 | 单文件 384 行 |
| 权威来源 | Spring Boot / Quarkus 官方约定 |
| 结构 | 命名 / 不可变性 / Optional 用法 / Stream 最佳实践 / 依赖注入 / 响应式模式 [QUARKUS] / 异常 / 泛型 / 项目布局 |
| 特色机制 | **框架自动检测**：读 build 文件含 `quarkus` → 应用 [QUARKUS] 约定；含 `spring-boot` → 应用 [SPRING] 约定；都没有 → 只用共享约定 |

**优势**：Java 17+ 现代特性（record、sealed class、模式匹配）全覆盖；框架检测机制是 12 个 skill 里独有的。
**局限**：深度绑定 Spring/Quarkus 生态，纯 Java SE 场景有部分内容用不上。

### 6. `josiahsiegel/claude-plugin-marketplace@markdown-style` — Markdown 规范 ⭐推荐

| 项 | 内容 |
|----|------|
| 体量 | SKILL.md 154 行 + references 2 文件（syntax-canon 8KB + style-overlay 10.7KB） |
| 权威来源 | **双层架构**：语法层基于 Markdown Guide 官方语法；风格层提炼自 **Google 开发者文档 Markdown 风格指南**（Apache 2.0） |
| 规则编号 | 每条规则有 ID（如 `style/headings/atx-only`），审查时按编号引用 |
| 审查流程 | 两遍制：Pass 1 语法（must-fix）→ Pass 2 风格（should-fix），逐条发现、逐条批准，不批量改写 |
| 边界声明 | 只管 Markdown 形式；prose 层术语归 Vale；不管 AsciiDoc/MDX/拼写 |
| 关键规则 | 单一 H1 作标题、ATX 禁 setext、标题前后空行、列表缩进 4 空格、链接文本不用"here"、小节名不重复（"Foo summary" 而非多个 "Summary"）、长文档加 TOC |

**优势**：设计理念与 TenetLang 笔记规范高度同构（规则编号、项目本地约定优先、should-fix vs must-fix 分层）。
**与本仓库关系**：tenetlang-notes 的「Markdown 排版规范」= 项目层约定（phXX 引用、blockquote 四用途等仓库特有规则）；markdown-style = 通用基础层。两者可叠加，冲突时按 markdown-style 自己的声明"服从项目约定"。

---

## 第二组：人设/专题型（各有长板）

### 7. `jeffallan/claude-skills@cpp-pro` — C++ 工程师人设

| 项 | 内容 |
|----|------|
| 体量 | SKILL.md 124 行骨架 + 5 个 references（~44KB） |
| 定位 | "资深 C++20/23 工程师"人设：分析架构 → concepts 设计 → 零成本实现 → sanitizer 验证 → benchmark |
| 结构 | references 分 5 主题：modern-cpp / templates / memory-performance / concurrency / build-tooling |
| 亮点 | MUST DO / MUST NOT DO 清单；build-tooling.md 的现代 CMake 写法、concurrency.md 的内存序示例质量不错 |

**适用**：让 agent 以工程师角色干活（写代码+跑工具链），不适合做规范速查。
**vs cpp-coding-standards**：无规则出处、规范密度低，但工具链实操更强。

### 8. `apollographql/skills@rust-best-practices` — Rust 规范 ⭐推荐

| 项 | 内容 |
|----|------|
| 体量 | SKILL.md 95 行速查表 + 9 章 references（共 ~96KB） |
| 权威来源 | **Apollo GraphQL 官方**《Rust Best Practices Handbook》（生产级 Rust 用户） |
| 版本 | 1.1.1，MIT，Rust 1.70+ |
| 结构 | 9 章：编码风格与惯用法（25KB，最大）/ Clippy 配置 / 性能心智 / 错误处理 / 自动化测试 / 泛型与分发 / Type State 模式 / 注释 vs 文档 / 指针类型（Send/Sync） |
| 速查表 | 借用 vs clone（≤24 字节 Copy 类型按值传）、禁生产环境 unwrap、thiserror 库 / anyhow 二进制、`#[expect]` 优于 `#[allow]` 且需理由注释 |
| 特色 | frontmatter 声明 `allowed-tools`（cargo/rustc/rustfmt/clippy），预期 agent 实际跑命令验证 |

**vs ecc@rust-patterns**：Apollo 版权威背书更强、内容深 10 倍（96KB vs 单文件）；ECC 版胜在与系列体例统一。Rust 建议用 Apollo。

### 9. `samber/cc-skills-golang@golang-code-style` — Go 风格（最细粒度）

| 项 | 内容 |
|----|------|
| 体量 | SKILL.md 241 行 + references/details.md 75 行 |
| 安装量 | **39.4K（本报告 12 个 skill 中最高）** |
| 定位 | 只管教判型风格：行长与断行（~120 字符、4+ 参数必须一行一个）、变量声明（`:=` vs `var` 的意图信号）、slice/map 必须显式初始化禁 nil、控制流清晰度、注释时机 |
| 特色 | **生态分工最细**：命名归 `golang-naming`、lint 配置归 `golang-lint`、文档注释归 `golang-documentation`、模式归 `golang-design-patterns`——本 skill 声明不做别人的事 |
| 机制 | 支持多 agent 并行风格审查（大代码库 fan-out）；声明"公司自定义 skill 可覆盖本 skill" |

**vs ecc@golang-patterns**：samber 版在"风格"这一垂直面更深（断行规则、nil slice 的 JSON 序列化陷阱这类细节 ECC 没有），但覆盖面窄（不管并发模式、错误处理）。**两者可叠加**：ECC 管广度和模式，samber 管风格细节。

### 10. `wshobson/agents@python-code-style` — Python 风格与工具链

| 项 | 内容 |
|----|------|
| 体量 | 单文件 360 行 |
| 安装量 | 13.9K |
| 定位 | 风格 + **工具链配置**：ruff/mypy/pyright 的 pyproject.toml 配置、docstring 规范、命名约定 |
| 来源 | wshobson/agents 大仓库的 python-development 插件（同插件还有 performance-optimization 32K、testing-patterns 31K） |

**vs ecc@python-patterns**：wshobson 版工具链配置开箱即用（`[tool.ruff]` 配置直接抄）；ECC 版语言惯用法覆盖更广。两者可叠加。

### 11. `github/awesome-copilot@java-springboot` — Spring Boot 最佳实践

| 项 | 内容 |
|----|------|
| 体量 | 单文件 65 行（12 个 skill 中最小） |
| 安装量 | 19.6K |
| 来源 | **GitHub 官方** awesome-copilot 仓库 |
| 定位 | 纯 Spring Boot 框架实践：构造器注入、`@ConfigurationProperties` 类型安全配置、DTO 不暴露 JPA 实体、`@ControllerAdvice` 全局异常、`@Transactional` 粒度、SLF4J 参数化日志、测试切片（@WebMvcTest/@DataJpaTest）+ Testcontainers |

**适用**：写 Spring Boot 服务时的框架层 checklist。
**注意**：**不是 Java 语言规范**——学 Java 语言本身用 ecc@java-coding-standards，写 Spring 服务时叠加这个。

### 12. `kepano/obsidian-skills@obsidian-markdown` — Obsidian 方言

| 项 | 内容 |
|----|------|
| 体量 | SKILL.md 196 行 + references（PROPERTIES/EMBEDS/CALLOUTS 等） |
| 作者 | kepano（**Obsidian 官方 CEO**） |
| 定位 | **Obsidian Flavored Markdown 方言**：wikilinks（`[[Note#Heading^block]]`）、embeds（`![[...]]`）、callouts（`> [!warning]+`）、frontmatter properties |
| 明确边界 | "标准 Markdown 是既有知识，本 skill 只覆盖 Obsidian 扩展语法" |

**适用**：写 Obsidian 笔记库时必备。
**对本仓库**：TenetLang 笔记是通用 Markdown（GitHub/终端可读），**Obsidian 方言不适用**——wikilinks 和 callouts 在 GitHub 上渲染不了。仅在个人 Obsidian 库场景使用。

---

## 三组对比维度总结

### 按定位分

| 定位 | Skill | 特征 |
|------|-------|------|
| 规范文档型 | ecc 全家桶、Apollo rust、markdown-style | 规则条目化、Good/Bad 对照、适合引用 |
| 人设干活型 | cpp-pro、golang-pro | 工程师角色 + 工作流 + allowed-tools |
| 垂直切片型 | samber golang-code-style、obsidian-markdown | 只做一个窄面，但做最深 |
| 框架专题型 | java-springboot | 不管语言管框架 |

### 按权威性分

| 权威背书 | Skill |
|---------|-------|
| 官方/大厂 | apollographql（Apollo）、github/awesome-copilot（GitHub）、kepano（Obsidian CEO） |
| 官方规范编号溯源 | ecc@cpp-coding-standards（C++ Core Guidelines 编号）、markdown-style（Google 风格指南 + 规则 ID） |
| 社区高安装量验证 | samber（39.4K）、wshobson（13.9K） |
| 个人经验总结 | jeffallan 系列（质量不错但无外部溯源） |

### 与本仓库（TenetLang）的适配

- **写 languages/ 笔记时参考**：ecc 系列 + Apollo rust + markdown-style（规范密度高、可逐条引用）
- **跑代码验证时**：Apollo rust（allowed-tools 声明 cargo/clippy）、samber golang（go/golangci-lint）
- **不要用**：obsidian-markdown（方言不兼容 GitHub 渲染）
- **空白待补**：C 语言规范（建议按 ECC 体例自建 `c-coding-standards`，基于 CERT C + Linux kernel style）

## 安装命令汇总

```bash
# 推荐组合（参考目录基底）
npx skills add https://github.com/affaan-m/ecc --skill cpp-coding-standards
npx skills add https://github.com/affaan-m/ecc --skill golang-patterns
npx skills add https://github.com/affaan-m/ecc --skill python-patterns
npx skills add https://github.com/affaan-m/ecc --skill java-coding-standards
npx skills add https://github.com/apollographql/skills --skill rust-best-practices
npx skills add https://github.com/josiahsiegel/claude-plugin-marketplace --skill markdown-style

# 可选叠加（垂直深化）
npx skills add https://github.com/samber/cc-skills-golang --skill golang-code-style   # Go 风格细节
npx skills add https://github.com/wshobson/agents --skill python-code-style            # Python 工具链配置
npx skills add https://github.com/github/awesome-copilot --skill java-springboot       # Spring 场景才装
npx skills add https://github.com/jeffallan/claude-skills --skill cpp-pro              # 需要工程师人设干活才装
npx skills add https://github.com/kepano/obsidian-skills --skill obsidian-markdown     # 仅 Obsidian 个人库
```
