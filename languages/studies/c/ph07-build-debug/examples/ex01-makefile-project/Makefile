# 来源：07-build-debug.md 第 6 章示例 1 —— 多文件项目 + Makefile
# 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
# 构建：make（在 ex01-makefile-project/ 目录内执行）
# 运行：./app
# 清理：make clean
# 验证状态：已验证
CC     = gcc
CFLAGS = -std=c11 -Wall -Wextra -g
TARGET = app
OBJS   = main.o math_utils.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c math_utils.h
	$(CC) $(CFLAGS) -c main.c

math_utils.o: math_utils.c math_utils.h
	$(CC) $(CFLAGS) -c math_utils.c

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: clean
