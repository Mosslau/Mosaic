# ph20 project Makefile —— Python 调用 C++ 向量检索库
# 验证环境：make 3.81+ / Apple clang 21.0.0 / Python 3.13.12
# 验证状态：已验证（make clean && make test 退出码 0：C 驱动与 Python 驱动断言全绿）
# 用法：
#   make        编译 dylib + C 驱动
#   make test   C 驱动 + Python ctypes 驱动全部跑一遍（验收入口）
#   make clean  清理 /tmp 产物（仓库不落任何二进制）
# CMake 等价编排见 examples/ex06（本目录刻意用 Makefile 保持与 ph19 project 一致）；
# 若装 CMake，等同理可用 add_library(vindex SHARED vec_index_wrap.cpp) 组织。
CXX    := clang++
CC     := clang
PY     := /Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
CFLAGS := -std=c++20 -Wall -Wextra

.PHONY: all test clean

all: /tmp/libvecindex.dylib /tmp/vecindex_c_driver

/tmp/libvecindex.dylib: vec_index_wrap.cpp vec_index_api.h vec_index_core.h
	$(CXX) $(CFLAGS) -dynamiclib $< -o $@

/tmp/vecindex_c_driver: driver_test.c vec_index_api.h /tmp/libvecindex.dylib
	$(CC) -std=c11 -Wall -Wextra $< -L/tmp -lvecindex -o $@

test: all
	/tmp/vecindex_c_driver
	$(PY) search_python.py

clean:
	rm -f /tmp/libvecindex.dylib /tmp/vecindex_c_driver
