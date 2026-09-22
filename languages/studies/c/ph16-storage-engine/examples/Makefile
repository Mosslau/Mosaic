# ph16 examples Makefile —— 一键构建并运行全部示例
# 产物一律写 /tmp/ph16c-ex（仓库零残留）; 演示数据写 /tmp/ph16c-ex-data
# 验证环境: Apple clang 21.0.0（cc，macOS arm64）
CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -O1 -g
BUILD   = /tmp/ph16c-ex

all: ex01 ex02 ex03 ex04 ex05 ex06

ex01: ex01-wal-record.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex01 && $(BUILD)/ex01

ex02: ex02-append-replay.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex02 && $(BUILD)/ex02

ex03: ex03-memtable.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex03 && $(BUILD)/ex03

ex04: ex04-sstable.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex04 && $(BUILD)/ex04

ex05: ex05-bloom-filter.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex05 -lm && $(BUILD)/ex05

ex06: ex06-lru-buffer-pool.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex06 && $(BUILD)/ex06

clean:
	rm -rf $(BUILD) /tmp/ph16c-ex-data

.PHONY: all ex01 ex02 ex03 ex04 ex05 ex06 clean
