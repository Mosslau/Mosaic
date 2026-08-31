# project/Makefile —— C++ 工程模板：多目标（core 库 + app + tests）+ 增量构建
# 验证环境：GNU Make 3.81（macOS 自带），Apple clang 21（g++ 兼容），C++20
# 用法：
#   make           # 全量：core 库 + app + tests（产物在 build/，源码目录不落 .o）
#   make test      # 构建并运行测试 ./build/test_core
#   make release   # 以 -O2 -DNDEBUG 构建（对比 Debug/Release，见主文档 3.7）
#   make clean     # rm -rf build
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

# release 目标：追加优化与 NDEBUG（关闭 assert），其余规则复用
release: CXXFLAGS += -O2 -DNDEBUG
release: all

clean:
	rm -rf $(OBJDIR)

.PHONY: all test release clean
