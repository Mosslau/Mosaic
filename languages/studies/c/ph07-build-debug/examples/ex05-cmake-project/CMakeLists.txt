# 来源：07-build-debug.md 第 6 章示例 5 —— CMake 最小项目
# 验证环境：CMake 3.31（Apple clang 17），-Wall -Wextra
# 构建：cmake -B build && cmake --build build
# 运行：./build/app
# 验证状态：已验证
cmake_minimum_required(VERSION 3.10)
project(cmake_demo C)

add_library(math_utils STATIC math_utils.c)        # 静态库
add_executable(app main.c)                          # 可执行文件
target_link_libraries(app PRIVATE math_utils)       # 关键: 建立链接关系
target_compile_options(app PRIVATE -Wall -Wextra -g)
