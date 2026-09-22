# ex06-cmake/CMakeLists.txt —— CMake 多目标示例（可选主题）
# 验证环境：CMake 4.2.3，Apple clang 21（g++ 兼容），C++20
# 用法：
#   cmake -B build && cmake --build build      # 配置 + 构建（默认 Debug）
#   ./build/app                                 # 运行
#   ctest --test-dir build --output-on-failure  # 跑测试
#   cmake -B build-rel -DCMAKE_BUILD_TYPE=Release && cmake --build build-rel
#   rm -rf build build-rel                      # 清理（产物全部在 build 目录）
cmake_minimum_required(VERSION 3.16)
project(ph10_ex06 CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Debug)   # 未指定时默认 Debug
endif()

add_library(math STATIC math.cpp)                    # 静态库目标
target_include_directories(math PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})
target_compile_options(math PRIVATE -Wall -Wextra)

add_executable(app main.cpp)                         # 可执行目标
target_link_libraries(app PRIVATE math)
target_compile_options(app PRIVATE -Wall -Wextra)

enable_testing()
add_executable(test_math test_math.cpp)
target_link_libraries(test_math PRIVATE math)
target_compile_options(test_math PRIVATE -Wall -Wextra)
add_test(NAME test_math COMMAND test_math)
