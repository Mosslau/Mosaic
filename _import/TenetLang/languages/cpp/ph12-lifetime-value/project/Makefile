# Makefile —— 值语义配置对象（ph12 project）
# 产物隔离到 build/，仓库不落二进制；make clean 即净。

CXX := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
BUILD := build

CFG_SRCS := main.cpp config.cpp
CFG_HDRS := config.h
TEST_SRCS := test_config.cpp config.cpp

.PHONY: all test run clean

all: $(BUILD)/cfgcli

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/cfgcli: $(CFG_SRCS) $(CFG_HDRS) | $(BUILD)
	$(CXX) $(CXXFLAGS) $(CFG_SRCS) -o $@

$(BUILD)/test_config: $(TEST_SRCS) $(CFG_HDRS) | $(BUILD)
	$(CXX) $(CXXFLAGS) $(TEST_SRCS) -o $@

# ASan 自测：验证无越界/use-after-free/double-free（泄漏检测需 Linux，macOS 不支持 LSan）
$(BUILD)/test_config_asan: $(TEST_SRCS) $(CFG_HDRS) | $(BUILD)
	$(CXX) $(CXXFLAGS) -fsanitize=address -g $(TEST_SRCS) -o $@

test: $(BUILD)/test_config $(BUILD)/test_config_asan
	$(BUILD)/test_config
	$(BUILD)/test_config_asan

run: all
	./$(BUILD)/cfgcli load samples/engine.conf
	./$(BUILD)/cfgcli get samples/engine.conf server.port
	./$(BUILD)/cfgcli clone samples/engine.conf
	./$(BUILD)/cfgcli merge samples/engine.conf samples/overlay.conf

clean:
	rm -rf $(BUILD)
