# 来源：project/ —— 多模块命令行工具 Makefile
# 验证环境：Apple clang 17（gcc 兼容），-Wall -Wextra -std=c11
# 构建：make
# 运行：./app file1.txt [file2.txt ...]
# 清理：make clean
# 验证状态：已验证
CC     = gcc
CFLAGS = -std=c11 -Wall -Wextra -g
TARGET = app
OBJS   = main.o io.o parse.o report.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

main.o: main.c io.h parse.h report.h
	$(CC) $(CFLAGS) -c main.c

io.o: io.c io.h
	$(CC) $(CFLAGS) -c io.c

parse.o: parse.c parse.h
	$(CC) $(CFLAGS) -c parse.c

report.o: report.c report.h parse.h
	$(CC) $(CFLAGS) -c report.c

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: clean
