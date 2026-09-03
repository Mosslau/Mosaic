# ex06-cmake-cross-build/CMakeLists.txt —— 跨语言构建：一个构建系统编排 C++/C/Python
# 验证状态：未在本环境验证（本机未安装 cmake；macOS 可 brew install cmake 后执行）
# 构建/测试（本目录内）：
#   cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure
# 与本目录 Makefile 等价（Makefile 已在本环境实测通过，见其文件头）。
# 教学点（主文档 3.5）：
#   ① C++ 包装层独立成 static 库目标，C 宿主与 Python 扩展都只依赖它；
#   ② Python 侧的 ctypes 路径不需要编译任何东西——只要解释器可用即可（find_package(Python3)）；
#      pybind11 路径才需要扩展目标（pybind11_add_module）；
#   ③ Rust 侧不在这里——cargo 有自己 build.rs（见 ../ex04-cxx-bridge/build.rs），
#      CMake 与 cargo 的编排是「谁产出谁消费」而非合并。
cmake_minimum_required(VERSION 3.20)
project(ph20_ex06 LANGUAGES CXX C)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_C_STANDARD 11)

# 复用 ../ex01-* 的真实源码（C++ 包装层 + C 宿主）
set(EX01_DIR ${CMAKE_CURRENT_SOURCE_DIR}/..)

add_library(vtest_core STATIC ${EX01_DIR}/ex01-stats-wrap.cpp)
target_include_directories(vtest_core PUBLIC ${EX01_DIR})

add_executable(c_host ${EX01_DIR}/ex01-host-main.c)
target_link_libraries(c_host PRIVATE vtest_core)

# 1. 纯 C ABI + ctypes：无 Python 扩展目标，只要解释器可查（运行期 CDLL 加载）
find_package(Python3 COMPONENTS Interpreter REQUIRED)
add_test(NAME host_c COMMAND c_host)
add_test(NAME python_ctypes
         COMMAND ${Python3_EXECUTABLE} ${EX01_DIR}/ex02-stats-ctypes.py)

# 2. pybind11 扩展目标（需要 pip install pybind11；未装则跳过整段）
find_package(pybind11 CONFIG QUIET)
if(pybind11_FOUND)
    pybind11_add_module(greeter ${EX01_DIR}/ex03-greeter-bindings.cpp)
    target_include_directories(greeter PRIVATE ${EX01_DIR})
    add_test(NAME python_pybind11 COMMAND ${Python3_EXECUTABLE} ${EX01_DIR}/ex03-test.py)
endif()
