# Makefile —— 查询执行器接口设计 demo（ph17 project）
# 分层 demo 的构建入口：4 个翻译单元对应 3 个逻辑层（storage / executor / engine）
# + 入口 main。产物隔离到 build/，make clean 即净，仓库不落二进制。
#
# 工具链（计划）：Apple clang 21.0.0（c++）/ Homebrew clang 21.1.8（clang++），C++17
# 验证状态：已验证（Apple clang 21.0.0 本机实测：make / make test 全过、自测退出码 0）

CXX      := clang++
CXXFLAGS := -std=c++17 -Wall -Wextra -O0 -g
BUILD    := build
TARGET   := $(BUILD)/query_demo
SRCS     := storage.cpp executor.cpp engine.cpp main.cpp
OBJS     := $(SRCS:%.cpp=$(BUILD)/%.o)

.PHONY: all run test clean

all: $(TARGET)

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/%.o: %.cpp storage.h executor.h engine.h | $(BUILD)
	$(CXX) $(CXXFLAGS) -c $< -o $@

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $@

run: $(TARGET)
	./$(TARGET)

test: $(TARGET)
	./$(TARGET) --selftest

clean:
	rm -rf $(BUILD)
