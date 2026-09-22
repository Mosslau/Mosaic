# analyze-cpp 设计分析 demos
CXX ?= clang++
CXXFLAGS ?= -std=c++17 -O2 -Wall -Wextra

DEMOS := 01_raii 02_move 03_multiparadigm 04_stl 05_constexpr
SRCS := $(addsuffix .cpp,$(DEMOS))

.PHONY: all clean

all: $(DEMOS)

%: %.cpp
	$(CXX) $(CXXFLAGS) $< -o $@

clean:
	rm -f $(DEMOS)
