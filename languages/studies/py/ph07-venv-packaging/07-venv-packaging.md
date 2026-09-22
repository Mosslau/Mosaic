# Python 虚拟环境与包管理阶段

> 面向自动化、数据分析、Web 服务方向，本阶段学会用 venv 隔离项目环境、用 pip 管理依赖、用 requirements.txt 与 pyproject.toml 描述与复现项目，让每个 Python 项目"环境独立、依赖可复现"。

## 1. 概述

Python 虚拟环境与包管理阶段的目标是：**能为每个项目创建独立虚拟环境，用 `pip` 安装与管理依赖，用 `requirements.txt` 锁定版本实现可复现安装，用 `pyproject.toml` 定义现代项目元数据与依赖分组，并把命令行小工具打包成可安装包**。这一阶段把 ph06 的"脚本工程能力"升级为"项目级能力"——**环境隔离与依赖管理是所有后续阶段（数据分析、Web 开发、测试、部署）的地基**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 环境隔离 | `venv` 创建与激活、每项目独立环境、`.venv` 不入库 |
| 依赖安装 | `pip install` / `uninstall` / `show` / `freeze` |
| 依赖清单 | `requirements.txt`、版本约束（`==`、`>=`、`~=`） |
| 项目描述 | `pyproject.toml`（PEP 621 元数据、依赖声明） |
| 依赖分组 | 运行依赖与开发依赖（`optional-dependencies`） |
| 现代工具 | poetry、uv（依赖解析与锁定） |
| 打包安装 | 构建 wheel、`pip install -e` 可编辑安装、`console_scripts` 入口点 |

**范围边界**：本阶段承接 ph06 标准库阶段，聚焦"环境 + 依赖"本身。不涉及第三方库生态选型（ph08）、发布到 PyPI 的完整流程（账号、`twine upload` 等在本阶段只做到本地 build 为止）、CI/CD 中的依赖管理（ph16）；数据分析（ph09）、Web 框架（ph10）依赖的库在本阶段只作为安装示例出现。

## 2. 来源与演变

早期 Python 只有一个"全局环境"：`pip install` 的所有包都装进系统 Python，不同项目版本冲突只能靠"最后装的赢"。2007 年 **virtualenv** 打破僵局——复制/软链出一个独立解释器环境，环境隔离从此成为 Python 工程标配；virtualenv 长期是事实标准，但需要单独安装、依赖系统环境。

标准库随后开始收编社区实践：Python 3.3 把 `venv` 模块纳入标准库（PEP 405），3.4 起 `pip` 随解释器捆绑（`ensurepip`）。工程化重心也从"环境"转向"项目"：2016 年的 PEP 517/518 定义了 `pyproject.toml` 与构建后端（build backend）机制，2020 年的 PEP 621 把项目元数据正式收进 `pyproject.toml` 的 `[project]` 表，现代项目从此有了统一入口。

工具侧同样在演进：2018 年 **poetry** 用 `pyproject.toml` 统一"依赖声明 + 锁定 + 打包"，引入 `poetry.lock` 精确锁定；2024 年 **uv**（Rust 编写）以极速和自带 Python 版本管理成为新宠，一条命令完成建环境、装依赖、加锁。依赖解析也从早期 pip 的"贪心装最新版"演变为 2020 年 pip 引入的 **resolver（依赖解析器）**——冲突主动报错，而不是悄悄装坏。

本文示例以 **Python 3.10+** 为基线（`pyproject.toml` PEP 621 自 3.11 起、`src` 布局推荐、`uv` 可选），验证解释器 3.13.12。

| 时间 | 里程碑 |
|------|-------|
| 2007 | virtualenv 诞生——环境隔离的先行者 |
| Python 3.3 | `venv` 进入标准库（PEP 405） |
| Python 3.4 | `pip` 随解释器捆绑（`ensurepip`） |
| 2016 | PEP 517/518：`pyproject.toml` + 构建后端 + build isolation |
| 2018 | poetry 发布——依赖锁定文件成为标配 |
| 2020 | PEP 621 元数据入 `pyproject.toml`；pip 新 resolver 上线 |
| 2024 | uv 发布——Rust 极速包管理 + 自带 Python 管理 |

## 3. 语法与参数

### 3.1 venv 虚拟环境创建与激活

```bash
python3 -m venv .venv            # 创建名为 .venv 的虚拟环境（当前目录下）
source .venv/bin/activate        # POSIX（macOS/Linux）激活
# Windows cmd:      .venv\Scripts\activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
which python                     # 激活后应指向 .venv/bin/python
python -m pip --version          # 确认 pip 属于该虚拟环境
deactivate                       # 退出虚拟环境
```

要点：

- **每个项目应有独立环境**（roadmap 必会概念）：不同项目需要的包和版本互不干扰，系统 Python 保持干净。
- **坑（激活失效）**：`activate` 只对**当前 shell 会话**生效，新开终端必须重新激活；切换目录不失效但重启终端会失效——脚本里直接用 `.venv/bin/python` 更可靠，无需激活。
| 平台 / Shell | 激活命令 |
|--------------|---------|
| macOS / Linux（bash、zsh） | `source .venv/bin/activate` |
| Windows cmd | `.venv\Scripts\activate` |
| Windows PowerShell | `.venv\Scripts\Activate.ps1` |
| 任何环境（免激活） | `.venv/bin/python`、`.venv/bin/pip` |

- **坑（Windows 激活脚本差异）**：cmd 用 `activate`，PowerShell 用 `Activate.ps1`；PowerShell 首次运行可能报"禁止运行脚本"，需先 `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`。
- 激活的本质只是把 `.venv/bin` 加到 `PATH` 最前面（机制见 4.1），所以 `python`/`pip` 都命中虚拟环境；脚本与 CI 里**免激活直接调用** `.venv/bin/python` 最稳。

### 3.2 pip 常用命令

```bash
python -m pip install requests             # 安装最新版
python -m pip install requests==2.32.0     # 安装指定版本
python -m pip install "requests>=2.28,<3"  # 安装版本区间
python -m pip show requests                # 查看包信息（版本、依赖、安装位置）
python -m pip freeze                       # 列出全部包与精确版本
python -m pip list                         # 简洁列表
python -m pip uninstall requests           # 卸载
python -m pip install --upgrade pip        # 升级 pip 本身
```

要点：**永远用 `python -m pip` 而非裸 `pip`**——裸 `pip` 可能属于另一个解释器（尤其多 Python 并存时）；**坑（全局环境污染）**：不建虚拟环境直接 `pip install` 会把包装进系统 Python，多项目版本互相覆盖，这是本阶段要根治的头号坏习惯；`pip freeze` 输出可直接重定向为 `requirements.txt`。

### 3.3 requirements.txt 与版本约束

```text
# requirements.txt —— 运行依赖清单
requests==2.32.0
numpy>=1.26,<2.0
pandas~=2.2.0
```

```bash
pip install -r requirements.txt      # 按清单安装
pip freeze > requirements.txt        # 生成锁定快照（当前环境的精确版本）
pip install -r requirements.txt -U   # 升级到清单允许的最新版
```

| 写法 | 含义 |
|------|------|
| `==2.32.0` | 精确锁定，最可复现 |
| `>=1.26` | 不低于 1.26 |
| `<2.0` | 低于 2.0 |
| `>=1.26,<2.0` | 区间（逗号是"且"） |
| `~=2.2.0` | 兼容版本：`>=2.2.0,==2.2.*`，只允许补丁级更新 |
| `2.*` | 任意 2.x 系列 |

要点：**依赖版本要可复现**（roadmap 必会概念）——**坑（requirements 不锁定）**：清单里写 `requests` 不写版本，今天能装、明年可能装出破坏性大版本，环境"漂移"到不可复现；`pip freeze` 快照是防漂移的标准手段。

### 3.4 pyproject.toml 现代项目入口（PEP 621）

```toml
[build-system]                          # PEP 517：构建后端
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]                               # PEP 621：项目元数据
name = "my-project"
version = "0.1.0"
description = "示例项目"
requires-python = ">=3.10"
dependencies = [                        # 运行依赖
    "requests>=2.28",
]
```

要点：**pyproject.toml 是现代项目入口**（roadmap 必会概念）——PEP 621 把元数据收进 `[project]` 表，PEP 517 让 `[build-system]` 声明构建后端，替代散落的 `setup.py`/`setup.cfg`/`requirements.txt`；`pip install .` 即可按它安装。**坑**：`requires-python` 写错（如 `>=3.13` 而机器是 3.11）安装会直接被拒。

### 3.5 开发依赖与运行依赖分组（optional-dependencies）

```toml
[project.optional-dependencies]         # 可选依赖分组（常用名：dev）
dev = ["pytest>=8.0", "ruff>=0.4", "mypy>=1.8"]
```

```bash
pip install .              # 只装运行依赖（生产/用户场景）
pip install -e ".[dev]"    # 运行依赖 + dev 开发分组，一次装齐
```

要点：**能说明运行和开发依赖**（roadmap 验收标准）——**运行依赖**是用户运行程序必需的（如 `requests`），**开发依赖**只是开发期工具（`pytest`、`ruff`、`mypy`），通过 `[project.optional-dependencies]` 分组；`pip install -e ".[dev]"` 是开发环境的标准安装姿势，生产只装运行依赖体积更小、攻击面更小。

### 3.6 poetry 与 uv 现代工具

```bash
# poetry —— 依赖声明 + 锁定 + 打包一体化
poetry new myapp                 # 脚手架：生成 pyproject.toml 骨架
poetry add requests              # 加依赖：写 pyproject + 更新 poetry.lock
poetry install                   # 按 poetry.lock 精确安装
poetry run python main.py        # 在项目环境里运行（免手动激活）

# uv —— Rust 编写，极速，自带 Python 版本管理
uv venv                          # 创建 .venv
uv add requests                  # 加依赖：写 pyproject + 更新 uv.lock
uv add --dev pytest              # 加开发依赖
uv sync                          # 按 uv.lock 精确同步环境
uv run python main.py            # 自动建环境并运行
uv python install 3.12           # 安装指定 Python 版本
```

要点：两者都以 `pyproject.toml` 声明、以锁定文件（`poetry.lock`/`uv.lock`）精确复现；uv 还自带 Python 版本管理，一条命令解决"环境 + 依赖 + 锁"。**坑（工具混用）**：团队里一部分人用 pip、一部分人用 poetry/uv 时，各自生成的锁定文件互相打架——选一个工具并写进 README，全组统一。

### 3.7 项目隔离与 .gitignore

```gitignore
# .gitignore
.venv/
__pycache__/
*.pyc
dist/
build/
*.egg-info/
```

要点：**不要把虚拟环境提交进仓库**（roadmap 必会概念）——`.venv/` 动辄数百 MB 且含本机绝对路径，提交后别人无法复用；仓库只提交"依赖清单"（`pyproject.toml` + 锁定文件或 `requirements.txt`），别人 `git clone` 后 `pip install -r` 重建环境；`.gitignore` 至少要有 `.venv/`、`__pycache__/`、`dist/` 三样。

### 3.8 打包小工具（pyproject build 与 pip install -e）

```toml
[project.scripts]                # console_scripts 入口点：把函数变成命令
hello = "hello.cli:main"
```

```bash
pip install -e .                 # 可编辑安装：源码改动即时生效，无需重装
pip install build && python -m build     # 构建 sdist + wheel 到 dist/
pip install dist/hello_cli-0.1.0-py3-none-any.whl   # 安装构建产物
```

要点：`[project.scripts]` 把包内函数变成全局可用的命令行入口（console_scripts）；**坑**：`pip install .` 是"快照式"安装，改代码后必须重装，开发期一律用 `pip install -e .`；`python -m build` 需要先 `pip install build`（不在标准库）。

## 4. 底层原理

### 4.1 venv 如何实现隔离（复制/软链解释器 + site-packages 重定向）

`python -m venv .venv` 创建三部分：

- **解释器**：`bin/python` 在 POSIX 下是**指向系统解释器的符号链接**（Windows 是副本，因为软链权限问题），保证版本一致、标准库共享；
- **`pyvenv.cfg`**：记录 `home`（系统 Python 位置）与版本，是"这是虚拟环境"的标记文件；
- **`lib/python3.x/site-packages/`**：独立的第三方包目录。

隔离的核心是 **site-packages 重定向**：进入虚拟环境后 `sys.prefix` 指向 `.venv`，第三方包只从 `.venv/lib/python3.x/site-packages/` 加载，系统 site-packages 被忽略；标准库仍从系统解释器目录读取（只读共享）。激活的本质只是**修改 `PATH` 环境变量**——把 `.venv/bin` 放到最前，于是 `python`、`pip` 都命中虚拟环境里的解释器；不激活时直接调用 `.venv/bin/python` 效果相同。

```text
.venv/
├── bin/
│   ├── python          # POSIX 下软链到系统解释器；Windows 为副本
│   ├── activate        # 激活脚本（只改 PATH，不复制任何东西）
│   └── pip             # 指向该环境的 pip
├── pyvenv.cfg          # home=…、version=…，虚拟环境的"身份证"
└── lib/
    └── python3.12/
        └── site-packages/   # 独立第三方包目录（重定向的目标）
```

### 4.2 pip 的依赖解析与冲突处理（旧版无解析器 vs 新版 resolver）

早期 pip 采用**贪心策略**：按命令行顺序逐个安装，每个包直接装"当前满足约束的最新版"，不回溯检查依赖图。于是装完 A 再装 B 时，若 B 需要 A 的旧版本，pip 会**悄悄降级或覆盖** A，甚至留下"A 要 X>=2、B 要 X<2"的坏组合——错误往往拖到运行时才暴露。

2020 年 pip 引入新 **resolver（依赖解析器）**：安装前先整体求解依赖图，发现冲突**立即报错**（"Cannot install ... because these package versions have conflicting dependencies"），绝不默默装坏；代价是解析更慢。这也解释了为什么"精确锁定"成为工程标配：`==` 锁得越死，解析器求解越快、冲突越少——锁定文件（lock file）正是把这一思想推到极致的产物。

### 4.3 pyproject.toml 与构建后端（PEP 517 build isolation）

PEP 517 把"如何把源码变成可安装包"抽象为**构建后端（build backend）**接口：后端提供 `build_wheel()`/`build_sdist()`，pip 调用它产出 wheel。`pyproject.toml` 的 `[build-system]` 声明用哪个后端（setuptools、hatchling、flit、poetry-core 等）。

配套机制是 **build isolation（构建隔离）**：pip 会在一个**临时隔离环境**里先安装 `[build-system].requires` 列出的构建工具，再调用后端构建——保证构建环境干净、不受项目依赖污染，也解释了为什么 `[build-system]` 必须写 `requires`。PEP 621 则规定 `[project]` 表的结构（name/version/dependencies/requires-python…），让所有工具读同一份元数据，不再各写各的 `setup.py`。

### 4.4 wheel 与 sdist 的区别

| 维度 | sdist（源码包） | wheel（轮子） |
|------|----------------|--------------|
| 扩展名 | `.tar.gz` | `.whl` |
| 内容 | 源码 + 构建配置 | 已打包好的文件（含预编译产物） |
| 安装过程 | 先构建（build）再安装 | 直接解压安装，即装即用 |
| 兼容标记 | 无 | `py3-none-any`、`cp312-cp312-macosx_*` 等 |
| 适用场景 | 无 wheel 的源码分发现场、审计源码 | 绝大多数安装场景：快、无构建依赖 |

wheel 本质是**预构建的 zip 包**，文件名中的兼容标记（platform tag）告诉 pip 它适用于哪个 Python 版本与平台；`pip install` 会优先选择 wheel，没有匹配的 wheel 才退回 sdist 现场编译——这就是"装某些含 C 扩展的包要先有编译器"的原因。`python -m build` 默认同时产出 sdist 和 wheel。

### 4.5 约束与锁定：你的项目是"库"还是"应用"

依赖写**区间**还是**精确版本**，取决于项目是库还是应用——这是新手最常犯的分类错误：

| | 库（给别人 import） | 应用（给人跑） |
|--|--------------------|---------------|
| 例子 | 自己封装的工具库 | CLI 工具、Web 服务、脚本 |
| dependencies 写法 | **区间** `"requests>=2.28,<3"` | 可区间，但要有锁 |
| 要不要锁文件 | **不要提交锁** | **要**（或 `pip freeze` 快照） |
| 为什么 | 你的依赖不该替下游决定版本；锁了反而与下游冲突 | 每次部署/复现都要"完全一样"，锁是唯一保证 |

道理一句话：**库要"兼容面大"，应用要"状态可复现"**——库把依赖写成区间，让下游在自己选定的版本上组合；应用把自己依赖的全部版本锁死，让环境可一键重建。实践中二者常混在一个仓库（一个带 CLI 的包同时是库和应用），此时以"发布形态"为准：要发到 PyPI 给别人用就按库写区间，只是自己内部跑就按应用锁。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 新项目开工 | `python -m venv .venv` + `pip install -e ".[dev]"` |
| 复现他人/服务器环境 | `pip install -r requirements.txt` 或按 lock 文件安装 |
| 多个项目用不同版本 | 每项目独立 venv，互不干扰 |
| 记录当前环境 | `pip freeze > requirements.txt` |
| 声明项目依赖与元数据 | `pyproject.toml`（PEP 621） |
| 区分运行/开发依赖 | `[project.optional-dependencies]` + `pip install -e ".[dev]"` |
| 分发命令行小工具 | `[project.scripts]` + `python -m build` + 安装 wheel |
| 快速实验/换 Python 版本 | `uv venv` + `uv add`（自带 Python 管理） |

**不适合此阶段的事项**：

- 大型项目的高级依赖锁定策略（lock 文件策略、多环境矩阵、供应商 vendoring）：ph13 测试/工程质量阶段结合 CI 展开
- Docker 镜像中的依赖安装与缓存优化：ph16 部署/CI-CD 阶段
- 发布到 PyPI 的完整流程（账号注册、`twine upload`、版本发布管理）：本阶段只到本地 build 为止

**高频坑速查表**（散见各节的坑汇总成一张表，遇到症状直接查）：

| 坑 | 症状 | 修法 |
|----|------|------|
| 裸 `pip install`（未激活） | 包装进系统 Python，污染全局 | 永远 `python -m pip`；先激活或直接用 `.venv/bin/pip` |
| 激活"失效" | 新开终端 `pip` 又指向系统环境 | `activate` 只对当前 shell 生效；脚本/CI 用 `.venv/bin/python` 免激活 |
| `.venv` 提交进 git | 仓库几百 MB、别人拉下来用不了 | `.gitignore` 加 `.venv/`；仓库只存依赖清单 |
| requirements 不写版本 | 隔段时间重装装出新版，行为漂移 | 至少给直接依赖写区间；要完全复现用 `pip freeze` 快照 |
| `pip install .` 当开发安装 | 改代码后行为不变（装的是快照） | 开发期用 `pip install -e .`（可编辑安装） |
| 打包后发现 import 不到 | 包没被找对（漏 `find` 配置 / 非 src 布局的隐式路径） | 用 `src/` 布局 + `where = ["src"]`（示例 4） |
| `requires-python` 高于本机 | 安装直接报版本不符被拒 | 声明"支持的最低版本"而不是"我机器的版本" |
| 团队混用 pip/poetry/uv | 锁定文件互相打架、环境对不上 | 选一个工具写进 README，全组统一（3.6） |

## 6. 代码示例

> 说明：示例 1/2/5 是命令序列（bash），示例 3 是配置文件，示例 4 是完整可安装包——每个示例的完整可运行/可复现版本在 [`examples/`](./examples/) 目录（示例 4 为 `examples/ex04-hello-cli/` 包目录），运行命令见 examples/README.md。

### 示例 1：创建并激活 venv + 安装依赖（完整命令序列）

呼应"创建虚拟环境"练习：完整走一遍"建环境 → 激活 → 装依赖 → 验证隔离"。

```bash
mkdir -p ~/projects/myapp && cd ~/projects/myapp
python3 -m venv .venv                 # 1. 创建虚拟环境
source .venv/bin/activate             # 2. 激活（Windows: .venv\Scripts\activate）
which python                          # 3. 确认解释器指向 .venv/bin/python
python -m pip install --upgrade pip   # 4. 升级 pip
python -m pip install requests        # 5. 安装依赖
python -c "import requests; print(requests.__version__)"
deactivate                            # 6. 退出
python -c "import requests" 2>&1 | head -1   # 7. 验证隔离：系统环境没有 requests
# ModuleNotFoundError: No module named 'requests'
```

完整文件：`examples/ex01-venv-create.sh`

### 示例 2：生成与使用 requirements.txt（freeze 快照 + 从零复现）

呼应"生成 requirements.txt"练习：环境 A 冻结快照，全新环境 B 一键复现。

```bash
# ---- 环境 A：安装若干包后冻结 ----
source .venv/bin/activate
python -m pip install requests pandas
pip freeze > requirements.txt
cat requirements.txt
# requests==2.32.0
# pandas==2.2.2
# numpy==1.26.4
# ...

# ---- 环境 B：git clone 后从零复现 ----
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -c "import requests, pandas; print('复现成功')"
```

完整文件：`examples/ex02-requirements-freeze.sh`

要点：`pip freeze` 会包含**所有间接依赖**（如 `numpy`），锁得最全、复现最稳；只想锁直接依赖可用 `pip-tools` 的 `pip-compile`（本阶段了解即可）。

### 示例 3：pyproject.toml 定义项目（PEP 621 元数据 + 可选依赖分组）

呼应"用 pyproject 管理项目"练习：一份 `pyproject.toml` 同时表达元数据、运行依赖、开发依赖。

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "can-toolkit"
version = "0.1.0"
description = "CAN 报文分析小工具"
readme = "README.md"
requires-python = ">=3.10"
dependencies = [
    "requests>=2.28,<3",
    "python-can>=4.3",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "ruff>=0.4",
    "mypy>=1.8",
]

[tool.setuptools.packages.find]
include = ["can_toolkit*"]
```

```bash
pip install -e ".[dev]"     # 运行依赖 + 开发依赖一次装齐（开发环境）
pip install .               # 仅运行依赖（生产/用户场景）
```

完整文件：`examples/ex03-pyproject.toml`

### 示例 4：可安装 CLI 工具包（pyproject + console_scripts 入口点 + pip install -e）

呼应"打包小工具"练习：把 ph06 的 argparse 工具包装成全局可用的 `hello` 命令。

```
hello_pkg/
├── pyproject.toml
├── README.md
└── src/
    └── hello/
        ├── __init__.py      # __version__ = "0.1.0"
        └── cli.py           # def main(): ...
```

```toml
# pyproject.toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "hello-cli"
version = "0.1.0"
requires-python = ">=3.10"

[project.scripts]
hello = "hello.cli:main"

[tool.setuptools.packages.find]   # src 布局：告诉 setuptools 去 src/ 找包
where = ["src"]
```

```python
# src/hello/cli.py
import argparse

def main(argv=None):
    parser = argparse.ArgumentParser(description="示例 CLI")
    parser.add_argument("name")
    args = parser.parse_args(argv)
    print(f"Hello, {args.name}!")

if __name__ == "__main__":
    main()
```

```bash
cd hello_pkg
python3 -m venv .venv && source .venv/bin/activate
pip install -e .            # 可编辑安装：生成 hello 命令
hello Alice                 # Hello, Alice! —— 任何目录都可用
pip install build && python -m build     # 构建 sdist + wheel 到 dist/
pip install dist/hello_cli-0.1.0-py3-none-any.whl   # 安装构建产物
```

完整文件：`examples/ex04-hello-cli/`（包目录：`pyproject.toml` + `src/hello/`）

注意 **src 布局**：源码放 `src/hello/`，避免"从仓库根目录 import"的隐式路径问题，是社区推荐的打包布局，打包配置里用 `where = ["src"]` 告诉 setuptools 去哪里找包。

### 示例 5：用 uv 快速管理环境（uv venv / uv add / uv lock 对比 pip）

呼应 roadmap"poetry、uv"学习内容：同样的"建环境 + 装依赖 + 锁定"，uv 一条命令一个文件。

```bash
uv init demo && cd demo      # 生成骨架 + pyproject.toml
uv venv                      # 创建 .venv（等价 python -m venv .venv）
uv add requests              # 安装并写入 pyproject.toml，生成 uv.lock
uv add --dev pytest          # 开发依赖
uv sync                      # 按 uv.lock 精确同步环境
uv run python main.py        # 在项目环境里运行（无需手动 activate）
uv python install 3.12 && uv venv --python 3.12   # 指定 Python 版本
```

| 能力 | pip 路线 | uv 路线 |
|------|---------|---------|
| 建环境 | `python -m venv .venv` | `uv venv` |
| 加依赖 | `pip install requests`（不自动写清单） | `uv add requests`（自动写 pyproject + 锁） |
| 锁定 | `pip freeze > requirements.txt` | `uv add`/`uv lock` 自动生成 `uv.lock` |
| 复现 | `pip install -r requirements.txt` | `uv sync` |
| 速度 | 慢（纯 Python 实现） | 快（Rust 实现） |

完整文件：`examples/ex05-uv-quickstart.sh`

要点：uv 的"自动写清单 + 自动锁定"把 pyproject 用法变得规范；本阶段 pip 路线必须熟练（它是基础），uv 作为提效工具了解其命令对应关系即可。

## 7. 总结

### 关键要点

1. **每个项目应有独立环境**：`python3 -m venv .venv` + 激活，杜绝全局环境污染（roadmap 必会概念）
2. **依赖版本要可复现**：`requirements.txt` 用 `==` 精确锁定，或用 `pip freeze` 生成快照（roadmap 必会概念）
3. **pyproject.toml 是现代项目入口**：PEP 621 元数据 + PEP 517 构建后端，替代散落的 `setup.py`（roadmap 必会概念）
4. **不要把虚拟环境提交进仓库**：`.venv/` 进 `.gitignore`，仓库只存依赖清单（roadmap 必会概念）
5. **永远用 `python -m pip` 而非裸 `pip`**：确保 pip 与当前解释器一致，多 Python 并存时尤其关键
6. **运行依赖与开发依赖分开声明**：`dependencies` + `[project.optional-dependencies]`，`pip install -e ".[dev]"` 一次装齐
7. **开发期用 `pip install -e .`**：源码改动即时生效；`[project.scripts]` 把函数变成全局命令
8. **新版 pip resolver 冲突即报错**：锁定越精确，解析越快、冲突越少
9. **poetry/uv 用 lock 文件精确复现**：uv 更快并自带 Python 管理，与 pip 二选一、团队统一

### 跨语言对比：依赖与包管理

| 维度 | Python（pip/poetry） | Go（modules） | Java（Maven） | Rust（Cargo） | npm |
|------|---------------------|---------------|---------------|---------------|-----|
| 包管理器 | pip / poetry / uv | `go mod` | Maven / Gradle | Cargo | npm / pnpm |
| 项目清单 | requirements.txt / pyproject.toml | go.mod | pom.xml | Cargo.toml | package.json |
| 锁定文件 | poetry.lock / uv.lock（pip 无默认锁） | go.sum | 无（仓库内定版本） | Cargo.lock | package-lock.json |
| 版本语法 | `==`、`>=`、`~=` | 语义化版本 | 区间/固定版本 | 语义化版本 | `^`、`~`、精确 |
| 环境隔离 | venv 虚拟环境 | 无（全局模块缓存） | 无（JVM 级） | 无（target/ 构建） | node_modules/ |
| 分发产物 | wheel / sdist | 编译二进制 | jar / war | crate | npm 包 |

### 阶段验收清单

- [ ] 能为项目创建并激活独立虚拟环境，能说明隔离原理（site-packages 重定向）（对应 roadmap"能隔离项目依赖"）
- [ ] 能用 `pip freeze` 生成 requirements.txt，并在全新环境一键复现（对应 roadmap"能复现安装环境"）
- [ ] 能说清运行依赖与开发依赖的区别，并用 `[project.optional-dependencies]` 分组管理（对应 roadmap"能说明运行和开发依赖"）
- [ ] 能用 `pyproject.toml` 声明项目元数据与依赖，并解释 PEP 517/621 的作用

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：创建虚拟环境、生成 requirements.txt、用 pyproject 管理项目、打包小工具共 4 题，与 roadmap「练习」小节一一对应。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**Python 项目模板**——一个"git clone 即可开工"的骨架（`pyproject.toml` PEP 621 + dev 分组、`src/` 布局、可安装 CLI、`.gitignore`、README 写清如何建环境/装依赖/跑测试），以后每个新项目都从它复制。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准

### 下一阶段

[第三方库阶段](../ph08-third-party/08-third-party.md) —— requests/httpx、numpy/pandas、FastAPI、pytest 等生态选型。
