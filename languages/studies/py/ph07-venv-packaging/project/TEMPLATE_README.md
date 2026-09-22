# pyproject-template

> 这是「Python 项目模板」自带的包说明文件（对应 `pyproject.toml` 的 `readme` 字段）。新项目从本模板复制后，把本文件改名为 `README.md` 并替换内容即可。

## 快速开始

```bash
# 1. 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate

# 2. 安装（运行依赖 + 开发依赖）
python -m pip install -e ".[dev]"

# 3. 运行 CLI
pyproj echo hello
pyproj echo hello --upper
pyproj --version

# 4. 跑测试与检查
pytest
ruff check src tests

# 5. 构建分发产物
python -m pip install build
python -m build                      # 产出 dist/*.whl 与 dist/*.tar.gz
```

## 目录结构

```text
project/
├── pyproject.toml                   # PEP 621 元数据 + dev 分组 + console_scripts
├── TEMPLATE_README.md               # 本文件（复制后改名为 README.md）
├── .gitignore                       # .venv/ __pycache__/ dist/ 等
├── src/
│   └── pyproject_template/
│       ├── __init__.py              # __version__
│       ├── cli.py                   # argparse CLI 主逻辑
│       └── __main__.py              # python -m pyproject_template 入口
└── tests/
    └── test_cli.py                  # pytest 单元测试
```
