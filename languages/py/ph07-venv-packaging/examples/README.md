# examples —— 虚拟环境与包管理阶段完整示例

> 每个示例是主文档 `07-venv-packaging.md` 第 6 章对应示例的完整可运行/可复现版。验证环境：Python 3.13.12（macOS / Linux，bash/zsh）。

| 文件 | 说明 | 运行 |
|------|------|------|
| `ex01-venv-create.sh` | 创建并激活 venv + 安装依赖 + 验证隔离（完整命令序列，临时目录自动清理） | `bash ex01-venv-create.sh` |
| `ex02-requirements-freeze.sh` | 环境 A freeze 生成 requirements.txt，全新环境 B 一键复现并对比包清单 | `bash ex02-requirements-freeze.sh` |
| `ex03-pyproject.toml` | PEP 621 元数据 + 运行依赖 + `[project.optional-dependencies]` dev 分组 | 复制到项目根后 `pip install -e ".[dev]"` |
| `ex04-hello-cli/` | 可安装 CLI 工具包：src 布局 + `[project.scripts]` 入口点 + `__main__.py` | 见下方说明 |
| `ex05-uv-quickstart.sh` | uv 快速管理环境：`uv init` / `uv venv` / `uv add` / `uv sync` | `bash ex05-uv-quickstart.sh` |

说明：

- `ex01`/`ex02` 在 `mktemp -d` 临时目录中演练并自动清理，不污染真实项目目录；需要联网安装 `requests`
- `ex04-hello-cli/` 是完整包目录，验证命令：

  ```bash
  cd ex04-hello-cli
  python3 -m venv .venv
  .venv/bin/pip install -e .            # 可编辑安装，生成 hello 命令
  .venv/bin/hello Alice                 # Hello, Alice!
  .venv/bin/python -m hello Alice       # __main__.py 入口，同样输出
  ```

- `ex05` 需本机已安装 `uv`；未安装时脚本会提示并正常退出

验证状态：`ex01`/`ex02`/`ex04`/`ex05` 均已在本环境（Python 3.13.12，本机装有 uv）实际运行验证通过（已验证）；`ex04` 另验证了 `python -m build` 产出 sdist + wheel。
