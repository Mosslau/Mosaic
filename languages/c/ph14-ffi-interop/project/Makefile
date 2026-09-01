# ph14 阶段项目 Makefile —— kvdb: C ABI KV 库（WAL 持久化）
# 验证环境: Apple clang 21.0.0（cc）+ Python 3.13.9 + rustc 1.92.0, macOS arm64
# 产物一律写 /tmp/ph14-proj（仓库零残留）; make clean 清理
CC      = cc
CFLAGS  = -Wall -Wextra -std=c11 -O1 -g
RUSTC   = rustc
PY      = python3
BUILD   = /tmp/ph14-proj

all: dylib cli

# C ABI 动态库（被 C CLI / Python ctypes / Rust FFI 三方调用）
dylib: kvdb.c kvdb.h
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) -dynamiclib kvdb.c -o $(BUILD)/libkvdb.dylib

# C 命令行自测
cli: cli.c kvdb.c kvdb.h
	mkdir -p $(BUILD)
	$(CC) $(CFLAGS) kvdb.c cli.c -o $(BUILD)/kvdb-cli

# Rust 调用方
rs: dylib rs_kvdb.rs
	$(RUSTC) --edition 2021 -D warnings rs_kvdb.rs -L $(BUILD) -l kvdb \
	    -o $(BUILD)/rs_kvdb

# 一键验证: C 自测(22 项断言) + Python 调用方 + Rust 调用方, 全部通过退出码 0
test: dylib cli rs
	$(BUILD)/kvdb-cli
	$(PY) py_kvdb.py
	$(BUILD)/rs_kvdb
	@echo "== make test 全部通过 =="

clean:
	rm -rf $(BUILD)

.PHONY: all dylib cli rs test clean
