# ph15 examples Makefile —— 一键构建并运行全部示例
# 产物一律写 /tmp/ph15c-ex（仓库零残留）；make clean 清理
# 验证环境: Apple clang 21.0.0（cc，macOS arm64）
CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -O1 -g
BUILD   = /tmp/ph15c-ex

all: ex01 ex02 ex03 ex04 ex05 ex06

ex01: ex01-macro-tricks.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex01 && $(BUILD)/ex01

ex02: ex02-callback-ctx.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex02 && $(BUILD)/ex02

ex03: ex03-state-machine.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex03 && $(BUILD)/ex03

ex04: ex04-error-code.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex04 && $(BUILD)/ex04

ex05: ex05-logging.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex05 && $(BUILD)/ex05

ex06: ex06-handle-api.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $< -o $(BUILD)/ex06 && $(BUILD)/ex06

clean:
	rm -rf $(BUILD)

.PHONY: all ex01 ex02 ex03 ex04 ex05 ex06 clean
