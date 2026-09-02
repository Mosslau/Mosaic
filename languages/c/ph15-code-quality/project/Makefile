# ph15 project Makefile —— 通用状态机框架
# 产物一律写 /tmp/ph15c-proj（仓库零残留）；make clean 清理
# 验证环境: Apple clang 21.0.0（cc，macOS arm64）
CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -O1 -g
BUILD   = /tmp/ph15c-proj

all: $(BUILD)/fsm-demo

$(BUILD)/fsm-demo: fsm.c fsm.h main.c
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) fsm.c main.c -o $@

# 自测: 运行 demo, 断言全过则退出码 0
test: $(BUILD)/fsm-demo
	$(BUILD)/fsm-demo

clean:
	rm -rf $(BUILD)

.PHONY: all test clean
