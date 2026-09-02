# Makefile —— C++ UB 示例集（ph15 project）
# 产物隔离到 build/，仓库不落二进制；make clean 即净。
# 双编译器验证：CXX 换成 clang++（Homebrew clang 21.1.8）同样零警告。
#
# 为什么 -O0：实测（Apple clang 21.0.0）在 -O1/-O2 下 clang 会把"被测的那次越界写"
# 常量折叠/死代码消除掉，ASan 因此抓不到 heap-buffer-overflow（examples/ex01 实测）；
# -O0 下全部报告稳定触发。真实项目的 Sanitizer CI 构建才用 -O1。
# 为什么 bad_demos.cpp 单独编译加 -Wno-uninitialized：bad_uninit 故意触发
# -Wuninitialized 编译警告（教学点：编译器在编译期就能拦一部分坑），在单独目标里抑制；
# catalog.cpp（主文件，含全部好版本）保持零警告。
# 为什么 race 单独一个 TSan 二进制：TSan 与 ASan/UBSan 不能同进程共存（都拦截同一批
# 运行时函数），数据竞争条目用 -fsanitize=thread 独立构建。

CXX      := c++
CXXFLAGS := -std=c++20 -Wall -Wextra -O0 -g -fsanitize=address,undefined -fno-sanitize-recover=all
BADFLAGS := -Wno-uninitialized
TSANFLAGS := -std=c++20 -Wall -Wextra -O1 -g -fsanitize=thread
BUILD    := build
TARGET   := $(BUILD)/ub_catalog
RACE     := $(BUILD)/race_demo
OBJS     := $(BUILD)/catalog.o $(BUILD)/bad_demos.o

.PHONY: all check demos list race clean

all: $(TARGET)

$(BUILD):
	mkdir -p $(BUILD)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $@

$(BUILD)/catalog.o: catalog.cpp ub_catalog.h | $(BUILD)
	$(CXX) $(CXXFLAGS) -c catalog.cpp -o $@

$(BUILD)/bad_demos.o: bad_demos.cpp ub_catalog.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(BADFLAGS) -c bad_demos.cpp -o $@

# TSan 专用二进制：数据竞争坏/好版本（race.cpp 自选模式，见其文件头）
$(RACE): race.cpp | $(BUILD)
	$(CXX) $(TSANFLAGS) race.cpp -o $@

# 自检：8 个好版本在 ASan+UBSan 下零报告（退出码 0）+ race 好版本在 TSan 下零报告
check: $(TARGET) $(RACE)
	./$(TARGET) check
	./$(RACE) good

list: $(TARGET)
	./$(TARGET) list

# 逐个触发坏版本：每个被 Sanitizer 中止（非零退出）后循环继续演示下一个；
# alias/uninit 两个"工具抓不到的坑"会跑完并打印提示（见 README「检测工具的边界」）
demos: $(TARGET) $(RACE)
	@set +e; for d in oob dangling uaf doublefree uam alias align uninit; do \
		echo; echo "===== [$$d] 坏版本 ====="; ./$(TARGET) $$d 2>&1; \
	done; \
	echo; echo "===== [race] 坏版本（TSan 构建）====="; ./$(RACE) race 2>&1; \
	true

# 演示 race 的 TSan 报告（与 demos 分开，避免非 TSan 环境的误用）
race-demo: $(RACE)
	./$(RACE) race

clean:
	rm -rf $(BUILD)
