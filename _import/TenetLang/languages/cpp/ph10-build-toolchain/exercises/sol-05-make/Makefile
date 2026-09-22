# sol-05-make/Makefile —— 练习 5 参考实现：Makefile 增量构建
# 验证环境：GNU Make 3.81（macOS 自带），Apple clang 21（g++ 兼容），C++20
# 用法：
#   make          # 全量构建 build/tool
#   make run      # 构建并运行
#   make clean    # 删除 build/
# 增量验证（touch 实测，GNU Make 3.81 只比较秒级时间戳，touch 前先 sleep 1）：
#   sleep 1 && touch calc.cpp && make     # 只重编 build/calc.o
#   sleep 1 && touch calc.h   && make     # calc.o 与 main.o 都重编（头文件依赖）
CXX      := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
OBJDIR   := build

TARGET := $(OBJDIR)/tool
OBJS   := $(OBJDIR)/calc.o $(OBJDIR)/main.o

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $^ -o $@

$(OBJDIR)/calc.o: calc.cpp calc.h | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -c calc.cpp -o $@

$(OBJDIR)/main.o: main.cpp calc.h | $(OBJDIR)
	$(CXX) $(CXXFLAGS) -c main.cpp -o $@

$(OBJDIR):
	mkdir -p $(OBJDIR)

run: all
	./$(TARGET)

clean:
	rm -rf $(OBJDIR)

.PHONY: all run clean
