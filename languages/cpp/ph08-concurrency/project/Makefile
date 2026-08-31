CXX      ?= c++
CXXFLAGS ?= -std=c++20 -Wall -Wextra -pthread

TARGET  := async_logger_demo
OBJS    := async_logger.o main.o

all: $(TARGET)

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $@

async_logger.o: async_logger.cpp async_logger.h
	$(CXX) $(CXXFLAGS) -c async_logger.cpp -o $@

main.o: main.cpp async_logger.h
	$(CXX) $(CXXFLAGS) -c main.cpp -o $@

run: $(TARGET)
	./$(TARGET)

clean:
	rm -f $(OBJS) $(TARGET) async_logger_demo.log

.PHONY: all run clean
