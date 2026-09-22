# sol-02-test.py —— 练习 2 Python 侧测试
# 验证状态：未在本环境验证（需先按 sol-02-bindings.cpp 文件头安装 pybind11 并构建）
# 运行：python3 sol-02-test.py
import sys

import word_counter

wc = word_counter.WordCounter()
wc.add("cpp")
wc.add("rust")
wc.add("cpp")
wc.add("python")
assert wc.total() == 4
assert wc.distinct() == 3
assert wc.most_common() == "cpp"

# 异常翻译：std::invalid_argument → ValueError；std::runtime_error → RuntimeError
try:
    wc.add("")
except ValueError as exc:
    assert "word must not be empty" in str(exc)
else:
    sys.exit("expected ValueError for empty word")

empty = word_counter.WordCounter()
try:
    empty.most_common()
except RuntimeError as exc:
    assert "no words yet" in str(exc)
else:
    sys.exit("expected RuntimeError on empty counter")

print("pybind11 WordCounter OK")
