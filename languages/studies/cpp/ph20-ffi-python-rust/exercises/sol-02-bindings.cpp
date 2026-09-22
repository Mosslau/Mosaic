// sol-02-bindings.cpp —— 练习 2 pybind11 绑定：类 + 方法 + 异常翻译
// 验证状态：未在本环境验证（pybind11 未 pip 安装）
// 安装/构建（exercises/ 目录内；命令与 examples/ex03 同构）：
//   PY=/Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
//   $PY -m pip install pybind11
//   EXT=$($PY -c 'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))')
//   clang++ -std=c++20 -Wall -Wextra -O3 -shared -fPIC $($PY -m pybind11 --includes) \
//       sol-02-bindings.cpp -o word_counter"$EXT"
// 运行：$PY sol-02-test.py
// 教学点：类直接成 Python 类，方法抛的异常自动翻译（对比 sol-01 只能拿错误码）。
#include <pybind11/pybind11.h>
#include <pybind11/stl.h>

#include "sol-02-word-counter.h"

namespace py = pybind11;

PYBIND11_MODULE(word_counter, m) {
    m.doc() = "pybind11 包装 word_counter（ph20 exercises/sol-02）";
    py::class_<sol02::word_counter>(m, "WordCounter")
        .def(py::init<>())
        .def("add", &sol02::word_counter::add, py::arg("word"))
        .def("total", &sol02::word_counter::total)
        .def("distinct", &sol02::word_counter::distinct)
        .def("most_common", &sol02::word_counter::most_common);
}
