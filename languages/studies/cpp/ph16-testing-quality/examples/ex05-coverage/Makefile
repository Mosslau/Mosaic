# Makefile —— 覆盖率报告（ph16 examples/ex05）
# LLVM source-based coverage 三步流：插桩编译 → 运行收集 .profraw → llvm-cov 出报告。
# 产物全部在 /tmp/ph16cpp-ex05（可用 BUILD= 覆盖），仓库不落二进制。
#
# 工具链选择（本机实测）：编译用 Homebrew clang++ 21.1.8，与 llvm-profdata/llvm-cov
# 21.1.8 同源，profile 格式版本严格匹配；Apple clang 21.0.0 实测也能生成可读的
# profraw（见 README 备注），但「编译器与 llvm-cov 同版本」是最稳的组合。
#
# gcov 路线对照（roadmap 提到 gcov/lcov，本机实测见 README）：
#   c++ --coverage 生成 .gcno/.gcda，macOS 的 /usr/bin/gcov 是 Apple clang 的
#   gcov 兼容前端；lcov/genhtml 本机未安装（未在本环境验证）。

CXX          := /opt/homebrew/opt/llvm/bin/clang++
LLVM_PROFDATA := /opt/homebrew/opt/llvm/bin/llvm-profdata
LLVM_COV     := /opt/homebrew/opt/llvm/bin/llvm-cov
CXXFLAGS     := -std=c++20 -Wall -Wextra -O0 -g
COVFLAGS     := -fprofile-instr-generate -fcoverage-mapping
BUILD        ?= /tmp/ph16cpp-ex05

.PHONY: all run report show clean

all: $(BUILD)/test_cov

$(BUILD):
	mkdir -p $(BUILD)

# 1. 插桩编译：-fprofile-instr-generate（记录执行计数）+ -fcoverage-mapping（源码区域映射）
$(BUILD)/test_cov: test_main.cpp grade.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(COVFLAGS) test_main.cpp -o $@

# 2. 运行收集：LLVM_PROFILE_FILE 指定 profraw 输出位置
$(BUILD)/default.profraw: $(BUILD)/test_cov
	LLVM_PROFILE_FILE=$(BUILD)/default.profraw $(BUILD)/test_cov

run: $(BUILD)/default.profraw

$(BUILD)/coverage.profdata: $(BUILD)/default.profraw
	$(LLVM_PROFDATA) merge -sparse $(BUILD)/default.profraw -o $@

# 3. 汇总报告（每个源文件的行/区域/函数覆盖率）
report: $(BUILD)/coverage.profdata
	$(LLVM_COV) report $(BUILD)/test_cov -instr-profile=$(BUILD)/coverage.profdata

# 逐行视图：未执行的行会标红（终端）/ 带计数前缀
show: $(BUILD)/coverage.profdata
	$(LLVM_COV) show $(BUILD)/test_cov -instr-profile=$(BUILD)/coverage.profdata \
		--name=classify --show-line-counts-or-regions

clean:
	rm -rf $(BUILD)
