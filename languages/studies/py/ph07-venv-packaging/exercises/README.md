# exercises —— 虚拟环境与包管理阶段练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。与 roadmap「练习」小节一一对应：创建虚拟环境、生成 requirements.txt、用 pyproject 管理项目、打包小工具。
>
> 参考实现都是可直接运行的 Python 脚本（`python3 sol-XX-*.py`），内部在临时目录用 `subprocess` 驱动 `venv`/`pip` 完成全流程并断言验收，运行后自动清理。你也可以不看脚本，按题目要求手动在 shell 里完成。

完成顺序建议：按 1~4 顺序完成。

## 练习 1：创建虚拟环境（★）

- **目标**：为一个新项目目录创建独立虚拟环境，激活后验证解释器与 pip 均指向该环境，退出后验证系统环境未被污染
- **要求**：
  - 用 `python3 -m venv .venv` 创建；激活后 `which python` 必须指向 `.venv/bin/python`
  - 用 `python -m pip`（不用裸 `pip`）安装任意一个第三方包
  - `deactivate` 后用系统 `python3` 验证该包**不可** import（若系统环境恰好也装了该包，改用 `sys.prefix` 判断当前是否在虚拟环境内）
- **验收**：激活后 `python -c "import sys; print(sys.prefix)"` 输出路径以 `.venv` 结尾；`deactivate` 后同一命令输出系统前缀

## 练习 2：生成 requirements.txt（★★）

- **目标**：在环境 A 安装 2~3 个包后 `pip freeze` 生成 `requirements.txt`，删掉环境重建环境 B，用 `pip install -r` 一键复现
- **要求**：
  - `requirements.txt` 中每个包都必须带精确版本（`==`），不允许裸包名
  - 环境 B 必须是**全新** `venv`，不能复用环境 A
  - 复现后对比两个环境的 `pip freeze` 输出必须完全一致
- **验收**：环境 B 中 `python -c "import <包装名>"` 全部成功；两次 `pip freeze` diff 为空

## 练习 3：用 pyproject 管理项目（★★）

- **目标**：为一个包写 `pyproject.toml`（PEP 621 元数据 + 运行依赖 + dev 分组），`pip install -e ".[dev]"` 后验证 `import` 与依赖分组生效
- **要求**：
  - `[project]` 表含 `name`/`version`/`description`/`requires-python`/`dependencies`
  - `[project.optional-dependencies]` 至少有一个 `dev` 分组（含 `pytest` 或 `ruff`）
  - `pip install .` 只装运行依赖；`pip install -e ".[dev]"` 运行 + 开发依赖一次装齐
- **验收**：`pip install -e .` 后 `import <包名>` 成功且 `__version__` 正确；`pip show` 能查到 dev 分组里的包

## 练习 4：打包小工具（★★★）

- **目标**：把一个 argparse 小工具改造成 src 布局的可安装包，用 `[project.scripts]` 生成全局命令，`pip install -e .` 后在任意目录可运行
- **要求**：
  - 目录结构为 `pyproject.toml` + `src/<包名>/__init__.py` + `cli.py`（+ `__main__.py` 支持 `python -m <包名>`）
  - `[project.scripts]` 把 `cli:main` 注册为命令；`pip install -e .` 后改源码**不重装**即生效
  - `python -m build` 产出 sdist + wheel（需 `pip install build`）
  - `.gitignore` 至少包含 `.venv/`、`__pycache__/`、`dist/`
- **验收**：可编辑安装后 `<命令> <参数>` 输出正确；`python -m <包名> <参数>` 输出一致；`dist/` 下有 `.whl` 与 `.tar.gz`；在新 venv 中 `pip install dist/*.whl` 后命令仍可用

> **提示**：练习 1~4 与主文档第 6 章示例 1/2/3/4 主题一一对应——先独立完成，再对照 `examples/` 检查思路。`sol-*` 为参考实现，做完再看。
