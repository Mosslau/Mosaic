# ph12 阶段项目 Makefile —— WAL record 解析器
# 目标: all(构建) / test(自测) / demo(写+读+损坏演示) / clean
# 验证环境: Apple clang 21.0.0（cc）, macOS（Darwin arm64）
# 编译命令: make（零警告: -Wall -Wextra -std=c11）
CC       = cc
CFLAGS   = -Wall -Wextra -std=c11 -O1 -g
TARGET   = wal_tool
SRCS     = wal.c main.c
DEMOFILE = /tmp/wal-demo.bin

all: $(TARGET)

$(TARGET): $(SRCS) wal.h
	$(CC) $(CFLAGS) $(SRCS) -o $(TARGET)

# 自测: 往返 / 损坏(CRC) / 截断 / magic, 全过退出码 0
test: $(TARGET)
	./$(TARGET) test

# 演示: 写 8 条 → 正常回放 → 模拟损坏回放（演示 CRC 拦截, 退出码 1 属预期）
demo: $(TARGET)
	rm -f $(DEMOFILE)
	./$(TARGET) write $(DEMOFILE) 8
	./$(TARGET) read $(DEMOFILE)
	@echo "---- 模拟损坏: read $(DEMOFILE) 43（应报 checksum 不匹配）----"
	-./$(TARGET) read $(DEMOFILE) 43

clean:
	rm -rf $(TARGET) *.o *.dSYM

.PHONY: all test demo clean
