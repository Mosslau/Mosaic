# ex06-cmake-cross-build/Makefile —— 不用 CMake 的等价编排（命令与 ex01/ex02 实测一致）
# 验证环境：make 3.81+ / Apple clang 21.0.0 / Python 3.13.12
# 验证状态：已验证（make clean && make test 退出码 0）
# 教学点：CMakeLists.txt 想表达的「多语言目标图」，等价展开后就是下面的编译命令——
#         CMake 不替代编译器，只负责编排。本 Makefile 是 CMakeLists 的无 CMake 替身。
CXX     := clang++
CC      := clang
PY      := /Users/ninebot/.workbuddy/binaries/python/versions/3.13.12/bin/python3
CFLAGS  := -std=c++20 -Wall -Wextra
SRC     := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))..)

.PHONY: all test clean

all: /tmp/libvtest.dylib /tmp/ph20-ex01-host

/tmp/libvtest.dylib: $(SRC)/ex01-stats-wrap.cpp $(SRC)/ex01-stats-c-api.h $(SRC)/ex01-stats-core.h
	$(CXX) $(CFLAGS) -dynamiclib $< -o $@

/tmp/ph20-ex01-host: $(SRC)/ex01-host-main.c /tmp/libvtest.dylib
	$(CC) -std=c11 -Wall -Wextra $< -L/tmp -lvtest -o $@

test: all
	/tmp/ph20-ex01-host
	$(PY) $(SRC)/ex02-stats-ctypes.py

clean:
	rm -f /tmp/libvtest.dylib /tmp/ph20-ex01-host
