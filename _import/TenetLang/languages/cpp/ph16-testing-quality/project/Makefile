# Makefile —— 带测试的 STL 工具库（ph16 project）
# 「一键质量闭环」：make check 依次跑 单元测试 → ASan+UBSan → TSan → clang-tidy →
# 格式门禁 → 覆盖率报告，任何一环失败即非零退出（CI 直接调 make check 即可）。
# 产物隔离到 build/，make clean 即净，仓库不落二进制。
#
# 工具链（本机实测，详见 examples/ex04 Makefile 文件头）：
# - 常规/ASan/TSan 构建用 Apple clang（c++ 21.0.0）；Homebrew clang 21.1.8 的
#   ASan 运行时在本机初始化即挂起、TSan 崩溃；
# - 覆盖率用 Homebrew clang++ 21.1.8 + llvm-profdata/llvm-cov 21.1.8（同版本最稳）。

CXX          := c++
CXXFLAGS     := -std=c++20 -Wall -Wextra -O1 -g
INCLUDES     := -I../examples -I.
COV_CXX      := /opt/homebrew/opt/llvm/bin/clang++
LLVM_COV     := /opt/homebrew/opt/llvm/bin/llvm-cov
LLVM_PROFDATA := /opt/homebrew/opt/llvm/bin/llvm-profdata
CLANG_TIDY   := /opt/homebrew/opt/llvm/bin/clang-tidy
CLANG_FORMAT := /opt/homebrew/opt/llvm/bin/clang-format
BUILD        := build

.PHONY: all test asan tsan tidy format-check coverage check clean

all: test

$(BUILD):
	mkdir -p $(BUILD)

# ---- 1. 单元测试 ----
$(BUILD)/test_stl_utils: test_stl_utils.cpp stl_utils.h ../examples/ex01-mini-test.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(INCLUDES) test_stl_utils.cpp -o $@

test: $(BUILD)/test_stl_utils
	./$(BUILD)/test_stl_utils

# ---- 2. Sanitizer 复跑（插桩下再跑一遍测试，零报告才算过）----
$(BUILD)/test_asan: test_stl_utils.cpp stl_utils.h ../examples/ex01-mini-test.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -fsanitize=address,undefined -fno-sanitize-recover=all \
		test_stl_utils.cpp -o $@

asan: $(BUILD)/test_asan
	./$(BUILD)/test_asan

$(BUILD)/test_tsan: test_stl_utils.cpp stl_utils.h ../examples/ex01-mini-test.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(INCLUDES) -fsanitize=thread test_stl_utils.cpp -o $@

tsan: $(BUILD)/test_tsan
	./$(BUILD)/test_tsan

# ---- 3. 静态分析（WarningsAsErrors='*'：有告警即失败）----
tidy:
	$(CLANG_TIDY) test_stl_utils.cpp --config-file=.clang-tidy -- $(CXXFLAGS) $(INCLUDES)

# ---- 4. 格式门禁（不改文件，只检查；违规即非零退出）----
format-check:
	$(CLANG_FORMAT) --style=file:.clang-format --dry-run --Werror \
		stl_utils.h test_stl_utils.cpp

# ---- 5. 覆盖率（llvm-cov source-based 三步流）----
$(BUILD)/test_cov: test_stl_utils.cpp stl_utils.h ../examples/ex01-mini-test.h | $(BUILD)
	$(COV_CXX) -std=c++20 -Wall -Wextra -O0 -g $(INCLUDES) \
		-fprofile-instr-generate -fcoverage-mapping test_stl_utils.cpp -o $@

$(BUILD)/coverage.profdata: $(BUILD)/test_cov
	LLVM_PROFILE_FILE=$(BUILD)/test_cov.profraw ./$(BUILD)/test_cov
	$(LLVM_PROFDATA) merge -sparse $(BUILD)/test_cov.profraw -o $@

coverage: $(BUILD)/coverage.profdata
	$(LLVM_COV) report ./$(BUILD)/test_cov -instr-profile=$(BUILD)/coverage.profdata

# ---- 一键闭环 ----
check: test asan tsan tidy format-check coverage
	@echo "== 质量闭环全部通过 =="

clean:
	rm -rf $(BUILD)
