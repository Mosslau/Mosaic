# project/src/pyproject_template/__main__.py —— python -m pyproject_template 入口
# 来源：Python 项目模板（ph07 阶段项目）
# 验证环境：Python 3.13.12
# 运行：python3 -m pyproject_template echo hello（包已安装时）
# 验证状态：已验证

"""支持 `python -m pyproject_template` 调用，转发到 cli.main。"""

from pyproject_template.cli import main

if __name__ == "__main__":
    main()
