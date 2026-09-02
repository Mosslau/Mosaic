# ph16 project Makefile —— lsmkv: 简化 LSM KV 文件层
# 产物一律写 /tmp/ph16c-proj（仓库零残留）; 演示数据写 /tmp/ph16c-proj-data
# 验证环境: Apple clang 21.0.0（cc，macOS arm64）
CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -O1 -g
BUILD   = /tmp/ph16c-proj
SRCS    = wal.c memtable.c bloom.c sstable.c lsm.c main.c
HDRS    = wal.h memtable.h bloom.h sstable.h lsm.h

all: $(BUILD)/lsmkv

$(BUILD)/lsmkv: $(SRCS) $(HDRS)
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) $(SRCS) -o $@

# 自测: 断言全过则退出码 0
test: $(BUILD)/lsmkv
	$(BUILD)/lsmkv test

# 演示链: 命令行走一遍 put/get/del/flush/stats
demo: $(BUILD)/lsmkv
	rm -rf /tmp/ph16c-proj-data/demo
	$(BUILD)/lsmkv put /tmp/ph16c-proj-data/demo hello world
	$(BUILD)/lsmkv get /tmp/ph16c-proj-data/demo hello
	$(BUILD)/lsmkv del /tmp/ph16c-proj-data/demo hello
	-$(BUILD)/lsmkv get /tmp/ph16c-proj-data/demo hello
	$(BUILD)/lsmkv flush /tmp/ph16c-proj-data/demo
	$(BUILD)/lsmkv stats /tmp/ph16c-proj-data/demo

clean:
	rm -rf $(BUILD) /tmp/ph16c-proj-data

.PHONY: all test demo clean
