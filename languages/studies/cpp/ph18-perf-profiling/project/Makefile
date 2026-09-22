# Makefile —— 向量距离计算性能对比（ph18 project）
# 单翻译单元项目：全部实现在 main.cpp 内，Makefile 只负责统一编译入口与产物隔离。
#
# 工具链（实测）：Apple clang 21.0.0（clang++）/ Homebrew clang 21.1.8，C++20，macOS arm64
# 验证状态：已验证（双编译器 -O3 -Wall -Wextra 编译零警告；make test 自测全绿、退出码 0）

CXX      := clang++
CXXFLAGS := -std=c++20 -O3 -Wall -Wextra
BUILD    := build
TARGET   := $(BUILD)/vec_bench

.PHONY: all run test clean

all: $(TARGET)

$(BUILD):
	mkdir -p $(BUILD)

$(TARGET): main.cpp | $(BUILD)
	$(CXX) $(CXXFLAGS) main.cpp -o $@

run: $(TARGET)
	./$(TARGET)

test: $(TARGET)
	./$(TARGET) --selftest

clean:
	rm -rf $(BUILD)
