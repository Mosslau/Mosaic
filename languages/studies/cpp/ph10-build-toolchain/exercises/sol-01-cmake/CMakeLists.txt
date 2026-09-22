# sol-01-cmake/CMakeLists.txt —— 练习 1 参考实现：CMake 组织"库 + 可执行"
# 验证环境：CMake 4.2.3，Apple clang 21（g++ 兼容），C++20
# 用法：
#   cmake -B build && cmake --build build     # 配置 + 构建（默认 Debug）
#   ./build/app                                # 运行
#   cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel
#   rm -rf build build-rel                     # 清理
cmake_minimum_required(VERSION 3.16)
project(sol01_cmake CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)   # 未指定时默认 Debug
endif()

add_library(text_utils STATIC text_utils.cpp)          # 库目标
target_include_directories(text_utils PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(text_utils PRIVATE -Wall -Wextra)

add_executable(app main.cpp)                           # 可执行目标
target_link_libraries(app PRIVATE text_utils)          # 显式声明依赖
target_compile_options(app PRIVATE -Wall -Wextra)
