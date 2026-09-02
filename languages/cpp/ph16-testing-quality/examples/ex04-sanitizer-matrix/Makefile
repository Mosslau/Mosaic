# Makefile —— Sanitizer 工程化矩阵（ph16 examples/ex04）
# 承接 ph15 结论：vector 越界靠 ASan、数据竞争靠 TSan；本 Makefile 把
# 「同一份源码 × 多种 Sanitizer 构建」做成一键目标——这正是 ph16 要做的工程化。
#
# 产物输出到 /tmp/ph16cpp-ex04（可用 make BUILD=... 覆盖），仓库不落二进制。
#
# 平台事实（本机实测，macOS arm64 darwin25.6）：
# - **Sanitizer 构建一律用 Apple clang（c++）**：Homebrew clang 21.1.8 的 ASan 运行时
#   在本机初始化即挂起（连 hello world 都跑不起来，卡在 "libc interceptors initialized"
#   之后）；TSan 实测崩溃（ph15 已记录）；LSan 能编译但退出时挂起（泄漏检查永不返回）。
#   仅 Homebrew UBSan 可用。故本 Makefile 默认 CXX=c++（Apple clang 21.0.0）。
# - LSan（-fsanitize=leak）在 macOS 上不可用：Apple clang 实测编译即报
#   "clang: error: unsupported option '-fsanitize=leak' for target 'arm64-apple-darwin...'"
#   ——macOS 下泄漏检测用 `leaks` 命令或 Xcode Instruments，LSan 是 Linux CI 的福利。
# - 本环境 ASan/UBSan 报告栈帧未符号化（llvm-symbolizer spawn 失败，ph15 已记录），
#   但错误类型、访问大小、地址信息完整，不影响工程化结论。

CXX      := c++
CXXFLAGS := -std=c++20 -Wall -Wextra -O1 -g
BUILD    ?= /tmp/ph16cpp-ex04
SRC      := main.cpp

# -O1 是 Sanitizer 构建的常见选择：比 -O0 更接近发布代码形状，又保留足够的调试信息。
# ph15 实测：越界类报告在 -O0/-O1/-O2 三档均触发，优化级别不是漏报条件。

.PHONY: all matrix check demo-oob clean

all: matrix

# 矩阵：同一份源码 × 四种构建
matrix: $(BUILD)/normal $(BUILD)/asan $(BUILD)/asan-ubsan $(BUILD)/tsan

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/normal: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) $(SRC) -o $@

$(BUILD)/asan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address $(SRC) -o $@

$(BUILD)/asan-ubsan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address,undefined -fno-sanitize-recover=all $(SRC) -o $@

# TSan 与 ASan 不能同进程共存（ph15 3.5：都拦截同一批运行时函数）→ 独立二进制
$(BUILD)/tsan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=thread $(SRC) -o $@

# 故意出错版（越界写）：必须 ASan 构建
$(BUILD)/oob-asan: $(SRC) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address -DEX04_OOB $(SRC) -o $@

# 自检：四种构建全部零报告退出（退出码 0）
check: matrix
	@for b in normal asan asan-ubsan tsan; do \
		echo "== $$b =="; $(BUILD)/$$b || exit 1; \
	done
	@echo "check: 4 种构建全部零报告通过"

# 演示：越界版被 ASan 中止（退出码 134，非零退出是「预期内」，故 || true 收尾）
demo-oob: $(BUILD)/oob-asan
	-$(BUILD)/oob-asan
	@echo "demo-oob: 上方应出现 AddressSanitizer: heap-buffer-overflow（退出码 134）"

clean:
	rm -rf $(BUILD)
