# ph23 project Makefile —— vsearch：SIMD 加速 brute-force 检索库 + 快照持久化
# 验证环境：make 3.81+ / Apple clang 21.0.0（默认）+ Homebrew clang 21.1.8（make cross）
# 验证状态：已验证（make clean && make test 退出码 0、零警告、断言全绿；
#           make bench 与 make bench_scalar 实测数字见 project/README）
# 用法：
#   make            构建 SIMD 版 /tmp/ph23-vsearch（-O3，NEON 路径生效）
#   make test       自测（验收入口：metric 正确性 / ground truth 对照 / 持久化 round-trip+篡改检测）
#   make bench      实测：recall/QPS/P95 延迟/内存占用（SIMD 版）
#   make bench_scalar 同一份源码 -DVSEARCH_FORCE_SCALAR=1 构建并跑同参数 → 与 bench 对照 SIMD 加速比
#   make cross      Homebrew clang 交叉编译 + 跑自测与 bench
#   make sanitize   ASan/UBSan 复跑自测（先 make clean）
#   make clean      清理 /tmp 产物与数据文件（仓库不落二进制/数据）
CXX := clang++
CXXFLAGS := -std=c++20 -O3 -Wall -Wextra -I.
OBJS := /tmp/ph23-vsearch.o /tmp/ph23-vsearch-main.o
SCALAR_OBJS := /tmp/ph23-vsearch-scalar.o /tmp/ph23-vsearch-main-scalar.o

.PHONY: all test bench bench_scalar cross sanitize clean

all: /tmp/ph23-vsearch

/tmp/ph23-vsearch.o: vsearch.cpp vsearch.h
	$(CXX) $(CXXFLAGS) -c vsearch.cpp -o $@
/tmp/ph23-vsearch-main.o: main.cpp vsearch.h
	$(CXX) $(CXXFLAGS) -c main.cpp -o $@
/tmp/ph23-vsearch: $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $@

# 标量对照构建（编译期强制关 NEON —— 同一份源码两种后端）
/tmp/ph23-vsearch-scalar.o: vsearch.cpp vsearch.h
	$(CXX) $(CXXFLAGS) -DVSEARCH_FORCE_SCALAR=1 -c vsearch.cpp -o $@
/tmp/ph23-vsearch-main-scalar.o: main.cpp vsearch.h
	$(CXX) $(CXXFLAGS) -DVSEARCH_FORCE_SCALAR=1 -c main.cpp -o $@
/tmp/ph23-vsearch-scalar: $(SCALAR_OBJS)
	$(CXX) $(CXXFLAGS) $(SCALAR_OBJS) -o $@

test: all
	/tmp/ph23-vsearch selftest

bench: all
	/tmp/ph23-vsearch bench 100000 64 300 10 l2

bench_scalar: /tmp/ph23-vsearch-scalar
	/tmp/ph23-vsearch-scalar bench 100000 64 300 10 l2

cross: /tmp/ph23-vsearch-cross
	/tmp/ph23-vsearch-cross selftest

/tmp/ph23-vsearch-cross: vsearch.cpp vsearch.h main.cpp
	/opt/homebrew/opt/llvm/bin/clang++ $(CXXFLAGS) vsearch.cpp main.cpp -o $@

sanitize: /tmp/ph23-vsearch-asan
	/tmp/ph23-vsearch-asan selftest

/tmp/ph23-vsearch-asan: vsearch.cpp vsearch.h main.cpp
	$(CXX) $(CXXFLAGS) -O1 -g -fsanitize=address,undefined vsearch.cpp main.cpp -o $@

clean:
	rm -f /tmp/ph23-vsearch /tmp/ph23-vsearch.o /tmp/ph23-vsearch-main.o
	rm -f /tmp/ph23-vsearch-scalar /tmp/ph23-vsearch-scalar.o /tmp/ph23-vsearch-main-scalar.o
	rm -f /tmp/ph23-vsearch-cross /tmp/ph23-vsearch-asan
	rm -f /tmp/ph23-vsearch-selftest.bin /tmp/ph23-vsearch-selftest.bin.tmp
