# ph21 project Makefile —— SkipList MemTable（内存有序 KV 结构）
# 验证环境：make 3.81+ / Apple clang 21.0.0（默认）+ Homebrew clang 21.1.8（交叉核对）
# 验证状态：已验证（make clean && make test 退出码 0：对拍 std::map + 边界断言全绿、编译零警告）
# 用法：
#   make        编译 /tmp/ph21-project-memtable
#   make test   编译 + 运行（验收入口）
#   make clean  清理 /tmp 产物（仓库不落任何二进制）
CXX := clang++
CXXFLAGS := -std=c++20 -Wall -Wextra -I.

.PHONY: all test clean cross

all: /tmp/ph21-project-memtable

/tmp/ph21-project-memtable: memtable_demo.cpp skip_list.h
	$(CXX) $(CXXFLAGS) memtable_demo.cpp -o $@

test: all
	/tmp/ph21-project-memtable

# 可选：Homebrew clang 21.1.8 交叉核对
cross: /tmp/ph21-project-memtable-hb
	/tmp/ph21-project-memtable-hb

/tmp/ph21-project-memtable-hb: memtable_demo.cpp skip_list.h
	/opt/homebrew/opt/llvm/bin/clang++ $(CXXFLAGS) memtable_demo.cpp -o $@

clean:
	rm -f /tmp/ph21-project-memtable /tmp/ph21-project-memtable-hb
