// ex03-greeter-bindings.cpp —— pybind11 绑定模块（声明式：类/方法/异常自动翻译）
// 验证状态：未在本环境验证（pybind11 未 pip 安装）
// 安装（选择解释器）：
//   /Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3 -m pip install pybind11
// 构建（在 examples/ 目录内，产物进当前目录 Python 才能 import）：
//   PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
//   $PY -m pybind11 --includes            # 打印 pybind11 与 Python 头文件 include 路径
//   EXT=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
//   clang++ -std=c++20 -Wall -Wextra -O3 -shared -fPIC $( $PY -m pybind11 --includes ) \
//       ex03-greeter-bindings.cpp -o greeter$EXT
// 运行：$PY ex03-test.py（预期 print Greeter OK 后退出码 0）
// 教学点：class_ + py::init 绑构造；.def 绑成员；<pybind11/stl.h> 开 STL 转换；
//         greet 抛的 std::invalid_argument 由 pybind11 翻成 Python ValueError（主文档 3.6）。
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>  // STL 自动转换：vector/string <-> list/str

#include "ex03-greeter.h"

namespace py = pybind11;

PYBIND11_MODULE(greeter, m) {
    m.doc() = "pybind11 包装 C++ 类的示例（ph20 examples/ex03）";

    py::class_<greeter::greeter>(m, "Greeter")
        .def(py::init<std::string>(), py::arg("prefix"))  // C++ 单参构造显式绑定
        .def("greet", &greeter::greeter::greet, py::arg("name"))
        .def("shout_all", &greeter::greeter::shout_all, py::arg("names"));
}
