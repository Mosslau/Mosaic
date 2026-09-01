# Makefile —— 配置读取只读接口（ph14 project）
# 产物隔离到 build/，仓库不落二进制；make clean 即净。
# 双编译器验证：CXX 换成 clang++（Homebrew clang 21.1.8）同样零警告。

CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
BUILD := build

.PHONY: all test run clean

all: $(BUILD)/config-demo

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/config-demo: demo.cpp config.hpp | $(BUILD)
	$(CXX) $(CXXFLAGS) demo.cpp -o $@

$(BUILD)/test_config: test_config.cpp config.hpp | $(BUILD)
	$(CXX) $(CXXFLAGS) test_config.cpp -o $@

# ASan 自测：只读接口 + 视图生命周期在 sanitizer 下同样通过
$(BUILD)/test_config_asan: test_config.cpp config.hpp | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address -g test_config.cpp -o $@

test: $(BUILD)/test_config $(BUILD)/test_config_asan
	$(BUILD)/test_config
	$(BUILD)/test_config_asan

run: all
	./$(BUILD)/config-demo samples/app.conf host port missing_key
	./$(BUILD)/config-demo samples/app.conf

clean:
	rm -rf $(BUILD)
