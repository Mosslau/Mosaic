# ph14 examples Makefile —— 一键构建并运行全部示例
# 产物一律写 /tmp/ph14-ex（仓库零残留）；make clean 清理
# 验证环境: Apple clang 21.0.0（cc/c++）+ Python 3.13.9 + rustc 1.92.0（macOS arm64）
CC      = cc
CXX     = c++
RUSTC   = rustc
PY      = python3
CFLAGS    = -Wall -Wextra -std=c11 -O1 -g
CXXFLAGS  = -Wall -Wextra -std=c++17 -O1 -g
BUILD   = /tmp/ph14-ex

all: ex01 ex02 ex03 ex04 ex05 ex06

# ex01: C 动态库 + C 主程序 + nm 导出符号
ex01: calc.c calc.h ex01-c-main.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib calc.c -o $(BUILD)/libcalc.dylib
	$(CC) $(CFLAGS) ex01-c-main.c -L$(BUILD) -lcalc -o $(BUILD)/ex01
	$(BUILD)/ex01
	@echo "--- nm -gU（仅全局导出符号）---"
	nm -gU $(BUILD)/libcalc.dylib

# ex02: C++ 调 C（extern "C"）+ C 调 C++ 包装层 + 故意出错的 mangling 演示
ex02: calc.c calc.h ex02-cpp-main.cpp ex02-cpp-lib.cpp ex02-c-main.c \
       ex02-bad-header.h ex02-mangle-fail.cpp
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib calc.c -o $(BUILD)/libcalc.dylib
	$(CXX) $(CXXFLAGS) ex02-cpp-main.cpp -L$(BUILD) -lcalc -o $(BUILD)/ex02-cpp
	$(BUILD)/ex02-cpp
	$(CXX) $(CXXFLAGS) -dynamiclib ex02-cpp-lib.cpp -o $(BUILD)/libcppwrap.dylib
	$(CC) $(CFLAGS) ex02-c-main.c -L$(BUILD) -lcppwrap -o $(BUILD)/ex02-c
	$(BUILD)/ex02-c
	@echo "--- 故意出错: 无 extern \"C\" 守卫 → 预期链接失败 ---"
	-$(CXX) $(CXXFLAGS) ex02-mangle-fail.cpp -L$(BUILD) -lcalc \
	    -o $(BUILD)/ex02-mangle-fail 2>&1 | grep -E "Undefined|extern" || true

# ex03: Python ctypes 调 C
ex03: calc.c calc.h ex03-py-ctypes.py
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib calc.c -o $(BUILD)/libcalc.dylib
	$(PY) ex03-py-ctypes.py $(BUILD)/libcalc.dylib

# ex04: Rust extern "C" 调 C
ex04: calc.c calc.h ex04-rs-ffi.rs
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib calc.c -o $(BUILD)/libcalc.dylib
	$(RUSTC) --edition 2021 -D warnings ex04-rs-ffi.rs -L $(BUILD) -l calc \
	    -o $(BUILD)/ex04-rs
	$(BUILD)/ex04-rs

# ex05: opaque pointer + create/destroy + 错误码/消息（四种语言调用方）
ex05: session.c session.h ex05-c-handle.c ex05-cpp-handle.cpp \
       ex05-py-handle.py ex05-rs-handle.rs
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib session.c -o $(BUILD)/libsession.dylib
	$(CC) $(CFLAGS) ex05-c-handle.c -L$(BUILD) -lsession -o $(BUILD)/ex05-c
	$(BUILD)/ex05-c
	$(CXX) $(CXXFLAGS) ex05-cpp-handle.cpp -L$(BUILD) -lsession -o $(BUILD)/ex05-cpp
	$(BUILD)/ex05-cpp
	$(PY) ex05-py-handle.py $(BUILD)/libsession.dylib
	$(RUSTC) --edition 2021 -D warnings ex05-rs-handle.rs -L $(BUILD) -l session \
	    -o $(BUILD)/ex05-rs
	$(BUILD)/ex05-rs

# ex06: 跨语言所有权约定（约定 1/2/3 + 结构体按值传递）
ex06: bufio.c bufio.h ex06-c-ownership.c ex06-py-ownership.py ex06-rs-ownership.rs
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib bufio.c -o $(BUILD)/libbufio.dylib
	$(CC) $(CFLAGS) ex06-c-ownership.c -L$(BUILD) -lbufio -o $(BUILD)/ex06-c
	$(BUILD)/ex06-c
	$(PY) ex06-py-ownership.py $(BUILD)/libbufio.dylib
	$(RUSTC) --edition 2021 -D warnings ex06-rs-ownership.rs -L $(BUILD) -l bufio \
	    -o $(BUILD)/ex06-rs
	$(BUILD)/ex06-rs

clean:
	rm -rf $(BUILD)
	rm -f ex01 ex02 ex03 ex04 ex05 ex06 *.o *.dSYM

.PHONY: all ex01 ex02 ex03 ex04 ex05 ex06 clean
