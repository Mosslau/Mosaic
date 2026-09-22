# ex03-test.py —— pybind11 扩展模块的 Python 侧测试
# 验证状态：未在本环境验证（需先按 ex03-greeter-bindings.cpp 文件头完成安装与构建）
# 运行：python3 ex03-test.py
# 教学点：Python 侧看不到 C ABI——Greeter 是原生 Python 类；方法签名是
#         Python 的 str/list；C++ 抛的异常自动变成 Python 异常。
import sys

import greeter  # 构建产物：greeter*.so 必须在当前目录或 PYTHONPATH

g = greeter.Greeter("Hello")
assert g.greet("World") == "Hello, World!"
assert g.shout_all(["a", "b"]) == ["Hello, a! (shout)", "Hello, b! (shout)"]

# 错误路径：C++ std::invalid_argument → Python ValueError（自动翻译）
try:
    g.greet("")
except ValueError as exc:
    assert "name must not be empty" in str(exc)
else:
    sys.exit("expected ValueError for empty name")

print("pybind11 Greeter OK")
