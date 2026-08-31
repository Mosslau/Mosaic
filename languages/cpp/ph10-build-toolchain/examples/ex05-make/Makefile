# ex05-make/Makefile —— Makefile 增量构建示例
# 验证环境：GNU Make 3.81（macOS 自带），Apple clang 21（g++ 兼容），C++20
# 用法：
#   make            # 全量构建 build/calc
#   make run        # 构建并运行
#   make clean      # 删除 build/（产物全部隔离在 build/，源码目录不落 .o）
# 增量验证（touch 实测，注意 GNU Make 3.81 只比较秒级时间戳，touch 前先 sleep 1）：
#   sleep 1 && touch calc.cpp && make     # 只重编 build/calc.o 并重链接
#   sleep 1 && touch calc.h   && make     # calc.o 与 main.o 都重编（头文件依赖！）
#   sleep 1 && touch main.cpp && make     # 只重编 build/main.o
CXX      := c++
CXXFLAGS := -std=c++20 -Wall -Wextra
OBJDIR   := build

TARGET := $(OBJDIR)/calc
OBJS   := $(OBJDIR)/calc.o $(OBJDIR)/main.o

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $^ -o $@

# 每个目标文件都显式声明头文件依赖：头文件改动才会触发重编
# （用 := 而非 ?= 赋 CXX/CXXFLAGS：环境变量可能已导出 CC/CXX，?= 不会覆盖环境值；
#   命令行 make CXX=clang++-19 仍可覆盖本文件赋值）
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
