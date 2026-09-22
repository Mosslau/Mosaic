# Makefile —— 跨平台文件工具库（ph11 project）
# 产物隔离到 build/，仓库不落二进制；make clean 即净。

CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
BUILD := build

# 可执行文件依赖的源文件与头文件（头文件改动触发重编）
FT_SRCS := main.cpp path_util.cpp file_info.cpp
FT_HDRS := path_util.h file_info.h

.PHONY: all test run clean

all: $(BUILD)/ftool

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/ftool: $(FT_SRCS) $(FT_HDRS) | $(BUILD)
	$(CXX) $(CXXFLAGS) $(FT_SRCS) -o $@

# 路径自测：同一份测试代码跑两个平台分支（POSIX 与 -D_WIN32 模拟 Windows）
$(BUILD)/test_path: path_util.cpp test_path.cpp path_util.h | $(BUILD)
	$(CXX) $(CXXFLAGS) path_util.cpp test_path.cpp -o $@

$(BUILD)/test_path_win: path_util.cpp test_path.cpp path_util.h | $(BUILD)
	$(CXX) -D_WIN32 $(CXXFLAGS) path_util.cpp test_path.cpp -o $@

test: $(BUILD)/test_path $(BUILD)/test_path_win
	$(BUILD)/test_path
	$(BUILD)/test_path_win

run: all
	./$(BUILD)/ftool join data config.json
	./$(BUILD)/ftool normalize data//sub///x.txt
	./$(BUILD)/ftool ext data/config.json
	./$(BUILD)/ftool info $(BUILD)/ftool
	./$(BUILD)/ftool ls $(BUILD)

clean:
	rm -rf $(BUILD)
