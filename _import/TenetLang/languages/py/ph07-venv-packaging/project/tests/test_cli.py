# project/tests/test_cli.py —— CLI 单元测试（pytest，dev 分组提供）
# 来源：Python 项目模板（ph07 阶段项目）
# 验证环境：Python 3.13.12，pytest>=8.0
# 运行：pip install -e ".[dev]" 后 pytest
# 验证状态：已验证

"""pyproj echo 子命令的单元测试。"""

from pyproject_template.cli import main


def test_echo_plain(capsys) -> None:
    """echo 原样回显文本。"""
    main(["echo", "hello"])
    assert capsys.readouterr().out == "hello\n"


def test_echo_upper(capsys) -> None:
    """echo --upper 转大写回显。"""
    main(["echo", "hello", "--upper"])
    assert capsys.readouterr().out == "HELLO\n"
