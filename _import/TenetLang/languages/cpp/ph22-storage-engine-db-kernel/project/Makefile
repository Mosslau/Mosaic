# ph22 project Makefile —— Mini LSM KV（WAL + MemTable + SSTable + Bloom）
# 验证环境：make 3.81+ / Apple clang 21.0.0（默认）+ Homebrew clang 21.1.8（交叉核对）
# 验证状态：已验证（make clean && make test 退出码 0：4 组自测断言全绿、编译零警告）
# 用法：
#   make           编译 /tmp/ph22-project-minilsm
#   make test      编译 + 运行自测（验收入口）
#   make cross     用 Homebrew clang 交叉编译并运行
#   make sanitize  ASan/UBSan 复跑自测（先 make clean）
#   make clean     清理 /tmp 产物与数据目录（仓库不落任何二进制/数据文件）
CXX := clang++
CXXFLAGS := -std=c++20 -Wall -Wextra -I.

.PHONY: all test clean cross sanitize

all: /tmp/ph22-project-minilsm

/tmp/ph22-project-minilsm: mini_lsm.cpp lsm.h sstable.h bloom.h wal.h skip_list.h
	$(CXX) $(CXXFLAGS) mini_lsm.cpp -o $@

test: all
	/tmp/ph22-project-minilsm

# Homebrew clang 21.1.8 交叉核对
cross: /tmp/ph22-project-minilsm-hb
	/tmp/ph22-project-minilsm-hb

/tmp/ph22-project-minilsm-hb: mini_lsm.cpp lsm.h sstable.h bloom.h wal.h skip_list.h
	/opt/homebrew/opt/llvm/bin/clang++ $(CXXFLAGS) mini_lsm.cpp -o $@

sanitize: /tmp/ph22-project-minilsm-asan
	/tmp/ph22-project-minilsm-asan

/tmp/ph22-project-minilsm-asan: mini_lsm.cpp lsm.h sstable.h bloom.h wal.h skip_list.h
	$(CXX) $(CXXFLAGS) -O1 -g -fsanitize=address,undefined mini_lsm.cpp -o $@

clean:
	rm -f /tmp/ph22-project-minilsm /tmp/ph22-project-minilsm-hb /tmp/ph22-project-minilsm-asan
	rm -rf /tmp/ph22-proj-d1 /tmp/ph22-proj-d2 /tmp/ph22-proj-d3 /tmp/ph22-proj-d4
