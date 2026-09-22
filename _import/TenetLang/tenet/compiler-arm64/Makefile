# tenet compiler-arm64 —— 手写 AArch64 汇编后端（不用 LLVM/clang）
CXX ?= clang++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Isrc

.PHONY: all test clean

all: tenet test

tenet: src/main.cpp $(wildcard src/*.hpp)
	$(CXX) $(CXXFLAGS) src/main.cpp -o tenet

test: test_tenet
	./test_tenet

test_tenet: tests/test_main.cpp $(wildcard src/*.hpp)
	$(CXX) $(CXXFLAGS) tests/test_main.cpp -o test_tenet

clean:
	rm -f tenet test_tenet
