# 文件同步工具（file_sync）Makefile
# 验证环境：Apple clang 21（g++ 兼容），C++20
CXX      ?= c++
CXXFLAGS ?= -std=c++20 -Wall -Wextra

TARGET := file_sync
OBJS   := main.o file_sync.o checksum.o

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $@

main.o: main.cpp file_sync.h checksum.h
	$(CXX) $(CXXFLAGS) -c main.cpp -o $@

file_sync.o: file_sync.cpp file_sync.h checksum.h
	$(CXX) $(CXXFLAGS) -c file_sync.cpp -o $@

checksum.o: checksum.cpp checksum.h
	$(CXX) $(CXXFLAGS) -c checksum.cpp -o $@

selftest: $(TARGET)
	./$(TARGET) --selftest

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: all selftest clean
