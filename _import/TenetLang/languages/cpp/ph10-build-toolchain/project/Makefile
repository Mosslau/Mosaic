# project/Makefile —— C++ 工程模板：多目标（core 库 + app + tests）+ 增量构建
# 验证环境：GNU Make 3.81（macOS 自带），Apple clang 21（g++ 兼容），C++20
# 用法：
#   make           # 全量：core 库 + app + tests（产物在 build/，源码目录不落 .o）
#   make test      # 构建并运行测试 ./build/test_core
#   make release   # 以 -O2 -DNDEBUG 构建到独立 build-release/（Debug/Release 互不污染）
#   make clean     # rm -rf build build-release
# 增量验证（touch 实测，GNU Make 3.81 只比较秒级时间戳，touch 前先 sleep 1）：
#   sleep 1 && touch app/main.cpp && make     # 只重编 build/app.o 并重链接 app
#   sleep 1 && touch core/stats_utils.cpp && make  # 只重编 stats_utils.o，app 与 test_core 重链接
#   sleep 1 && touch core/stats_utils.h && make    # 三个 .o 都重编（头文件依赖！）
CXX      := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
OBJDIR   := build

CORE_H   := core/stats_utils.h
CORE_OBJ := $(OBJDIR)/stats_utils.o
APP_OBJ  := $(OBJDIR)/app.o
TEST_OBJ := $(OBJDIR)/test_core.o

APP  := $(OBJDIR)/app
TEST := $(OBJDIR)/test_core

all: $(APP) $(TEST)

$(OBJDIR):
	mkdir -p $(OBJDIR)

# 每个目标文件显式声明源文件与头文件依赖：头文件改动才会触发重编
$(CORE_OBJ): core/stats_utils.cpp $(CORE_H) | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -c core/stats_utils.cpp -o $@

$(APP_OBJ): app/main.cpp $(CORE_H) | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -I. -c app/main.cpp -o $@

$(TEST_OBJ): tests/test_core.cpp $(CORE_H) | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -I. -c tests/test_core.cpp -o $@

$(APP): $(APP_OBJ) $(CORE_OBJ)
	$(CXX) $(CXXFLAGS) $^ -o $@

$(TEST): $(TEST_OBJ) $(CORE_OBJ)
	$(CXX) $(CXXFLAGS) $^ -o $@

test: $(TEST)
	./$(TEST)

# release 目标：以 -O2 -DNDEBUG 构建到独立的 build-release/ 目录（Debug/Release
# 互不污染，符合主文档 3.7「不同构建类型用不同 build 目录」）；先清空 build-release/
# 再全量重建，保证每次 make release 都是真正的 Release 产物（编译命令含 -O2 -DNDEBUG）。
# 用 $(MAKE) 子进程 + 命令行变量覆盖 OBJDIR/CXXFLAGS：子 make 重读本文件时
# 命令行变量优先于文件内赋值，全部产物路径随之落到 build-release/。
release:
	$(MAKE) OBJDIR=build-release CXXFLAGS="$(CXXFLAGS) -O2 -DNDEBUG" clean all

clean:
	rm -rf $(OBJDIR) build-release

.PHONY: all test release clean
