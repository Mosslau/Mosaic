# ph07 阶段项目：Python 项目模板

> 对应 Roadmap（python.md）ph07「推荐项目」第一个「Python 项目模板」。一个"git clone 即可开工"的骨架：`pyproject.toml`（PEP 621 + dev 分组）、`src/` 布局、可安装 CLI、`.gitignore`、README 写清如何建环境/装依赖/跑测试，以后每个新项目都从它复制。

## 需求

实现一个可直接复制开工的 Python 项目骨架：用 PEP 621 `pyproject.toml` 声明元数据与依赖，运行依赖与开发依赖分组管理；源码采用社区推荐的 `src/` 布局；内置一个带 `--version` 与子命令的 argparse 示例 CLI，通过 `[project.scripts]` 注册为全局命令，并支持 `python -m <包名>` 调用；附 pytest 单元测试、ruff 配置与 `.gitignore`；模板自带说明文件写清"建环境 → 装依赖 → 跑测试 → 构建"全流程。

## 功能清单

- [x] `pyproject.toml`：PEP 621 元数据（name/version/description/requires-python）+ PEP 517 构建后端
- [x] 依赖分组：`dependencies`（运行）+ `[project.optional-dependencies].dev`（pytest、ruff）
- [x] `src/` 布局：`[tool.setuptools.packages.find] where = ["src"]`
- [x] 可安装 CLI：`[project.scripts] pyproj = "pyproject_template.cli:main"`，含 `--version` 与 `echo` 子命令（`--upper` 选项）
- [x] `__main__.py` 入口：支持 `python -m pyproject_template`
- [x] pytest 单元测试：`tests/test_cli.py` 覆盖 echo 两种模式
- [x] ruff 配置与 pytest 配置收进 `pyproject.toml`
- [x] `.gitignore`：`.venv/`、`__pycache__/`、`dist/`、`build/`、`*.egg-info/`、缓存目录
- [x] 模板说明文件 `TEMPLATE_README.md`：快速开始命令 + 目录结构（复制后改名为 README.md）

## 验收标准

- [ ] `python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"` 一次装齐运行 + 开发依赖
- [ ] `.venv/bin/pyproj echo hello` 输出 `hello`；`pyproj echo hello --upper` 输出 `HELLO`
- [ ] `.venv/bin/pyproj --version` 输出 `pyproj 0.1.0`；`.venv/bin/python -m pyproject_template echo hi` 与 `pyproj` 输出一致
- [ ] `.venv/bin/pytest` 全部通过（2 个用例）
- [ ] `.venv/bin/ruff check src tests` 无错误
- [ ] `.venv/bin/pip install build && .venv/bin/python -m build` 产出 `dist/*.whl` 与 `dist/*.tar.gz`；在**另一个**全新 venv 中 `pip install dist/*.whl` 后 `pyproj echo ok` 正常
- [ ] 可编辑安装后修改 `cli.py` 源码，不重装即生效
- [ ] 仓库中不含有 `.venv/`、`dist/`、`*.egg-info/`（被 `.gitignore` 覆盖）

## 扩展方向

- 加 `mypy` 进 dev 分组并配置 `[tool.mypy]` 严格模式（结合 ph13 工程质量）
- 用 `uv` 管理本模板：`uv venv` + `uv pip install -e ".[dev]"`，对比速度（主文档示例 5）
- 加 GitHub Actions CI：push 后自动跑 pytest + ruff（ph16 部署/CI-CD 阶段）
- 把 ph06 的批量重命名工具移植进本模板结构，作为第二个 console_scripts 命令

## 验证环境

- Python 3.13.12，构建后端 setuptools>=68，dev 分组 pytest>=8.0、ruff>=0.4，构建工具 build（均需联网安装）
- 运行：见「验收标准」各条命令
- 验证状态：已验证（全部验收命令在本环境实际执行通过）
