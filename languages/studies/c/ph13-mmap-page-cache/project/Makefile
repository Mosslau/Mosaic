# ph13 阶段项目 Makefile —— kvlog: 可靠 append-only log
# 目标: all(构建) / test(自测) / demo(演示: 写/读/崩溃/残尾/损坏) / clean
# 验证环境: Apple clang 21.0.0（cc）, macOS（Darwin arm64）
# 编译命令: make（零警告: -Wall -Wextra -std=c11）
CC       = cc
CFLAGS   = -Wall -Wextra -std=c11 -O1 -g
TARGET   = kvlog
SRCS     = kvl.c main.c
DEMOFILE = /tmp/kvlog-demo.log

all: $(TARGET)

$(TARGET): $(SRCS) kvl.h
	$(CC) $(CFLAGS) $(SRCS) -o $(TARGET)

# 自测: 往返 / 残尾 / 损坏(CRC) / magic, 全过退出码 0
test: $(TARGET)
	./$(TARGET) test

# 演示: 写 → 读 → 崩溃(SIGKILL+回放+修复) → 残尾 → 损坏拦截
demo: $(TARGET)
	rm -f $(DEMOFILE)
	./$(TARGET) write $(DEMOFILE) 8
	./$(TARGET) read $(DEMOFILE)
	./$(TARGET) crash $(DEMOFILE)
	./$(TARGET) torn $(DEMOFILE)
	@echo "---- 模拟损坏: corrupt $(DEMOFILE) 20（应报残尾/CRC 拦截）----"
	-./$(TARGET) corrupt $(DEMOFILE) 20
	rm -f $(DEMOFILE)

# Sanitizer 复跑（衔接 ph11 工具链）: 行为正确 + 内存无错
san: $(SRCS) kvl.h
	$(CC) $(CFLAGS) -fsanitize=address,undefined -fno-sanitize-recover=all $(SRCS) -o /tmp/kvlog_san
	/tmp/kvlog_san test
	rm -f /tmp/kvlog_san

clean:
	rm -rf $(TARGET) *.o *.dSYM

.PHONY: all test demo san clean
