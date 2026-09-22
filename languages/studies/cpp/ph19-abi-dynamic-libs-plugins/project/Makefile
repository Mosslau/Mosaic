# Makefile —— C ABI 插件式存储引擎 demo（ph19 project）
# 构建两个存储引擎插件（mem_store / file_store）与插件宿主 store_host。
# 产物一律输出到 build/（构建目录），验证后 make clean 清理，不落仓库。
#
# 工具链（实测）：Apple clang 21.0.0（clang++）/ Homebrew clang 21.1.8，
# C++20（libc++），macOS arm64。
# 验证状态：已验证（双编译器 -Wall -Wextra 编译零警告；make test 两引擎
#   自测全绿、退出码 0）。

CXX       := clang++
CXXFLAGS  := -std=c++20 -Wall -Wextra
BUILD     := build
PLUGIN_DIR := $(BUILD)/plugins
HOST      := $(BUILD)/store_host
PLUGINS   := $(PLUGIN_DIR)/libmem_store.dylib $(PLUGIN_DIR)/libfile_store.dylib
FILE_DAT  := /tmp/ph19_file_store_test.dat

.PHONY: all run run-file test clean

all: $(HOST) $(PLUGINS)

$(BUILD) $(PLUGIN_DIR):
	mkdir -p $(PLUGIN_DIR)

$(HOST): main.cpp storage_api.h | $(BUILD)
	$(CXX) $(CXXFLAGS) main.cpp -o $@

$(PLUGIN_DIR)/libmem_store.dylib: mem_store.cpp storage_api.h | $(PLUGIN_DIR)
	$(CXX) $(CXXFLAGS) -dynamiclib mem_store.cpp -o $@

$(PLUGIN_DIR)/libfile_store.dylib: file_store.cpp storage_api.h | $(PLUGIN_DIR)
	$(CXX) $(CXXFLAGS) -dynamiclib file_store.cpp -o $@

run: all
	./$(HOST) ./$(PLUGIN_DIR)/libmem_store.dylib

run-file: all
	rm -f $(FILE_DAT)
	./$(HOST) ./$(PLUGIN_DIR)/libfile_store.dylib $(FILE_DAT)

test: all
	rm -f $(FILE_DAT)
	@echo "===== 测试引擎 1: mem_store ====="
	./$(HOST) ./$(PLUGIN_DIR)/libmem_store.dylib
	@echo "===== 测试引擎 2: file_store ====="
	./$(HOST) ./$(PLUGIN_DIR)/libfile_store.dylib $(FILE_DAT)
	@rm -f $(FILE_DAT)

clean:
	rm -rf $(BUILD)
	rm -f $(FILE_DAT)
