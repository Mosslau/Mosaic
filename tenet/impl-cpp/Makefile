# tenet-cpp — Tenet 语言的 C++17 实现
CXX ?= clang++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra -Isrc

SRCS := src/main.cpp
HDRS := $(wildcard src/*.hpp)

.PHONY: all test clean

all: tenet test

tenet: $(SRCS) $(HDRS)
	$(CXX) $(CXXFLAGS) $(SRCS) -o tenet

test: test_tenet
	./test_tenet

test_tenet: tests/test_main.cpp $(HDRS)
	$(CXX) $(CXXFLAGS) tests/test_main.cpp -o test_tenet

clean:
	rm -f tenet test_tenet
