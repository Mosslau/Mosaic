# 来源：languages/cpp/ph07-exception-safety/project/Makefile
# 说明：工程化配置库构建——error/config/logger 三模块 + main 自测
# 验证环境：Apple clang 17（g++ 兼容），-Wall -Wextra -std=c++17
# 构建：make
# 运行：./config_app
# 清理：make clean
# 验证状态：已验证

CXX      = g++
CXXFLAGS = -Wall -Wextra -std=c++17
LDFLAGS  = -pthread
TARGET   = config_app
OBJS     = main.o config.o error.o logger.o

$(TARGET): $(OBJS)
	$(CXX) $(CXXFLAGS) $(OBJS) -o $(TARGET) $(LDFLAGS)

main.o: main.cpp config.h error.h logger.h
	$(CXX) $(CXXFLAGS) -c main.cpp

config.o: config.cpp config.h error.h
	$(CXX) $(CXXFLAGS) -c config.cpp

error.o: error.cpp error.h
	$(CXX) $(CXXFLAGS) -c error.cpp

logger.o: logger.cpp logger.h
	$(CXX) $(CXXFLAGS) -c logger.cpp

clean:
	rm -f $(OBJS) $(TARGET)

.PHONY: clean
