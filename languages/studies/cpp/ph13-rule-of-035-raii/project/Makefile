# Makefile —— RAII 系统资源库（ph13 project）
# 产物隔离到 build/，仓库不落二进制；make clean 即净。
# 双编译器验证：CXX 换成 clang++（Homebrew clang 21.1.8）同样零警告。

CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
BUILD := build

.PHONY: all test run clean

all: $(BUILD)/raii-demo

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/raii-demo: demo.cpp raii/c_file.h raii/unique_fd.h | $(BUILD)
	$(CXX) $(CXXFLAGS) demo.cpp -o $@

$(BUILD)/test_raii: test_raii.cpp raii/c_file.h raii/unique_fd.h | $(BUILD)
	$(CXX) $(CXXFLAGS) test_raii.cpp -o $@

# ASan 自测：验证异常路径无 double-free/use-after-free（fd 泄漏用 /dev/fd 计数实测）
$(BUILD)/test_raii_asan: test_raii.cpp raii/c_file.h raii/unique_fd.h | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address -g test_raii.cpp -o $@

test: $(BUILD)/test_raii $(BUILD)/test_raii_asan
	$(BUILD)/test_raii
	$(BUILD)/test_raii_asan

run: all
	./$(BUILD)/raii-demo write /tmp/ph13-demo.txt
	./$(BUILD)/raii-demo read /tmp/ph13-demo.txt
	./$(BUILD)/raii-demo copy samples/hello.txt /tmp/ph13-copy.txt
	./$(BUILD)/raii-demo read /tmp/ph13-copy.txt
	rm -f /tmp/ph13-demo.txt /tmp/ph13-copy.txt

clean:
	rm -rf $(BUILD)
