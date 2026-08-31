CC      = cc
# 用 -O0 而非常规的 -O1: 实测(Apple clang 21.0.0)在 -O1 下 clang 会把本库
# 坏版本里"被测的那次内存访问"常量折叠/死代码消除掉, ASan 因此抓不到
# stack-buffer-overflow(如 strcpy 被折叠成常量 printf); -O0 下全部报告稳定触发。
# 真实项目的 Sanitizer CI 构建才用 -O1(见主文档 4.2 的修正说明)。
CFLAGS  = -Wall -Wextra -std=c11 -O0 -g -fsanitize=address,undefined -fno-sanitize-recover=all
# bad_demos.c 故意触发 -Warray-bounds/-Wuninitialized/-Wfortify-source 等编译期警告
# (教学点: 编译期就能拦一部分坑), 在单独的目标里抑制; 主文件保持零警告
BADFLAGS = -Wno-array-bounds -Wno-uninitialized -Wno-fortify-source
TARGET  = pitfall_catalog
OBJS    = pitfall_catalog.o bad_demos.o

$(TARGET): $(OBJS)
	$(CC) $(CFLAGS) $(OBJS) -o $(TARGET)

pitfall_catalog.o: pitfall_catalog.c pitfall.h
	$(CC) $(CFLAGS) -c pitfall_catalog.c -o pitfall_catalog.o

bad_demos.o: bad_demos.c pitfall.h
	$(CC) $(CFLAGS) $(BADFLAGS) -c bad_demos.c -o bad_demos.o

.PHONY: all clean check demos list
all: $(TARGET)

# 自检: 全部好版本运行, 无 Sanitizer 报告, 退出码 0
check: $(TARGET)
	./$(TARGET) check

list: $(TARGET)
	./$(TARGET) list

# 逐个触发坏版本: 每个都被 Sanitizer 中止(非零退出), 循环继续演示下一个
demos: $(TARGET)
	@set +e; for d in oob null uaf overflow uninit alias align divzero shift strbuf; do \
		echo; echo "===== [$$d] 坏版本 ====="; ./$(TARGET) $$d 2>&1; \
	done; true

clean:
	rm -f $(OBJS) $(TARGET)
