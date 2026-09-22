# ph11 阶段项目 Makefile —— 带测试的 append-only buffer 库
# 目标: all(普通构建) / test(一键跑测试) / asan(ASan+UBSan 组合跑测试) /
#       coverage(gcov 覆盖率报告) / check(test+asan) / clean
# 设计: 测试、Sanitizer、覆盖率全部固化进 make, 一条命令可复现——
#       这正是"工具要固化进构建"的落地(主文档 3.9)。
CC       = cc
CFLAGS   = -Wall -Wextra -std=c11 -O1 -g
# Sanitizer 组合: 一次编译 ASan(地址类)+UBSan(逻辑类)双查;
# -fno-sanitize-recover=all 让 UBSan 报错即中止(CI 里"报错即失败")
SANFLAGS = -fsanitize=address,undefined -fno-sanitize-recover=all
TARGET   = test_buffer

all: $(TARGET)

$(TARGET): buffer.c buffer.h test_buffer.c
	$(CC) $(CFLAGS) buffer.c test_buffer.c -o $(TARGET)

# 一键跑测试: ./test_buffer 全过则退出码 0
test: $(TARGET)
	./$(TARGET)

# Sanitizer 构建下跑同一套测试: 行为正确 + 内存无错 双证明
asan:
	$(CC) $(CFLAGS) $(SANFLAGS) buffer.c test_buffer.c -o $(TARGET)_asan
	./$(TARGET)_asan

# 覆盖率: --coverage 编译(计数插桩) → 运行生成 .gcda → gcov 文本报告
# macOS 的 .gcda 名带可执行名前缀(test_buffer_cov-buffer.gcda);
# Linux gcc 直接是 buffer.gcda / test_buffer.gcda
coverage:
	$(CC) -Wall -Wextra -std=c11 --coverage -g buffer.c test_buffer.c -o $(TARGET)_cov
	./$(TARGET)_cov > /dev/null
	@for f in $(TARGET)_cov-*.gcda buffer.gcda test_buffer.gcda; do \
		[ -e "$$f" ] || continue; \
		echo "===== $$f ====="; gcov -b "$$f"; \
	done
	@echo "覆盖率报告见 *.c.gcov: ##### 行为未执行行, taken 0% 为未取分支"

check: test asan

clean:
	rm -rf $(TARGET) $(TARGET)_asan $(TARGET)_cov *.o *.gcda *.gcno *.gcov *.dSYM

.PHONY: all test asan coverage check clean
