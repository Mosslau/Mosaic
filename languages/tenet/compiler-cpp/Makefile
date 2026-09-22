# tenet compiler-cpp —— C++17 版（调用 LLVM 后端库）
CXX ?= clang++
LLVM_CONFIG ?= /opt/homebrew/opt/llvm/bin/llvm-config
LLVM_INC := $(shell $(LLVM_CONFIG) --includedir)
LLVM_LIB := $(shell $(LLVM_CONFIG) --libdir)
LLVM_LIBS := $(shell $(LLVM_CONFIG) --link-shared --libs core)

CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Isrc -isystem $(LLVM_INC)
LDFLAGS := -L$(LLVM_LIB) $(LLVM_LIBS)

.PHONY: all test clean

all: tenet test

tenet: src/main.cpp $(wildcard src/*.hpp)
	$(CXX) $(CXXFLAGS) src/main.cpp $(LDFLAGS) -o tenet

test: test_tenet
	./test_tenet

test_tenet: tests/test_main.cpp $(wildcard src/*.hpp)
	$(CXX) $(CXXFLAGS) tests/test_main.cpp $(LDFLAGS) -o test_tenet

clean:
	rm -f tenet test_tenet
