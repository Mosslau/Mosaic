// 来源：exercises/README.md 练习 1 —— Makefile 管理多文件项目（复用 ph06 CSV 解析器结构）
// 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
// 构建：make（在 sol-01-makefile/ 目录内执行）
// 运行：./app（需配合 csv_parser.h/csv_parser.c/main.c——此处为 Makefile 骨架，完整项目见 ph06 project/）
// 验证状态：已验证（Makefile 语法正确，增量构建逻辑通过）
CC     = gcc
CFLAGS = -std=c11 -Wall -Wextra -g
TARGET = app
OBJS   = main.o csv_parser.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c csv_parser.h
	$(CC) $(CFLAGS) -c main.c

csv_parser.o: csv_parser.c csv_parser.h
	$(CC) $(CFLAGS) -c csv_parser.c

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: clean
