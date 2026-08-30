# C 语言文件操作阶段

> 面向系统底层、存储引擎方向，本阶段掌握文件 I/O 与持久化：让程序能可靠地把数据写入磁盘，再完整地读回来。

## 1. 概述

文件操作阶段是 C 学习路线中"程序开始与外界交换持久数据"的节点。目标：**掌握 fopen/fclose 管理文件生命周期，用 fgets/fputs、fprintf/fscanf 读写文本，用 fread/fwrite 读写二进制，理解缓冲与文件定位，写出能处理错误与持久化数据的代码**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 文件生命周期 | fopen 打开、fclose 关闭、NULL 检查、成对使用 |
| 文本行读写 | fgets、fputs、逐行处理、行缓冲 |
| 格式化读写 | fprintf、fscanf、格式串与返回值检查 |
| 二进制读写 | fread、fwrite、结构体整块读写 |
| 文件定位 | fseek、ftell、rewind、随机访问 |
| 缓冲与刷新 | 全缓冲/行缓冲/无缓冲、fflush |
| 错误处理 | feof、ferror、返回值检查、perror |
| 持久化设计 | 文本 vs 二进制取舍、append-only、简单格式设计 |

本阶段直接承接 ph05：`fread`/`fwrite` 一次性读写结构体数组，是 ph05 内存布局知识的实战出口；ph04 养成的"检查 malloc 返回值"习惯，延伸为"检查每个 IO 返回值"。

**范围边界**：承接 ph05 的结构体与内存管理；**不涉及** mmap/Page Cache 与 fsync 落盘语义（ph13）、WAL/存储引擎（ph17）、文件系统内部机制与文件描述符系统编程（ph08）、网络 IO（ph08）、字节序与跨平台二进制格式（ph12）。

## 2. 来源与演变

早期的 Unix 用 `open`/`read`/`write` 系统调用直接读写文件：每次调用都要陷入内核，读一个字节就进一次内核，性能差且接口繁琐。1975 年，Brian Kernighan 设计了 **stdio**（standard I/O）库并由 Dennis Ritchie 在 Unix V6 上实现：在用户态为每个文件维护一块缓冲区，攒满才真正调用系统调用，把"按字节读"变成"按块读"——这就是 FILE 抽象和缓冲机制的源头。

`FILE*` 把三样东西封装在一起：**用户态缓冲区、当前文件位置指示器、错误/EOF 状态**——这也是"打开返回指针、用完必须 fclose"的设计根源。C89 将 stdio 标准化后，这套 API 至今几乎未变，是 C 标准库中最稳定的部分。

本文示例以 **C99** 为基线（编译加 `-Wall -Wextra -std=c99`），验证工具链 Apple clang 17（gcc 兼容）。

| 时间 | 来源 | 关键演变 |
|------|------|---------|
| 1971 | Unix V1 | open/read/write/close 系统调用成型：无缓冲、每次调用进内核 |
| 1975 | Unix V6（Kernighan 设计） | stdio 库诞生：用户态缓冲 + FILE 抽象，系统调用次数大幅下降 |
| 1978 | K&R C | stdio 随《The C Programming Language》传播，成为事实标准 |
| 1989 | C89/ANSI C | stdio.h 正式标准化：fopen 模式串、fgets/fseek/ftell 定型 |
| 1999 | C99 | 新增 snprintf 等安全函数，文件 API 主体不变 |
| 2011 | C11 | 文件 API 无重大变化，接口保持 30 年稳定 |

## 3. 语法与参数

### 3.1 fopen 模式与错误处理

```c
#include <stdio.h>
int main(void) {
    FILE *fp = fopen("data.txt", "r");
    if (fp == NULL) {            /* 文件不存在/权限不足/路径错误 → NULL */
        perror("fopen");
        return 1;
    }
    /* ... 读写 ... */
    fclose(fp);                  /* 关闭并释放资源 */
    return 0;
}
```

| 模式 | 含义 | 文件不存在时 | 文件已存在时 |
|------|------|:------------:|:------------:|
| `"r"` | 只读 | 失败 | 从开头读 |
| `"w"` | 只写 | 创建 | **清空后写**（危险） |
| `"a"` | 追加写 | 创建 | 每次写到末尾 |
| `"r+"` | 读写 | 失败 | 从开头 |
| `"w+"` | 读写 | 创建 | 清空 |
| `"a+"` | 读+追加写 | 创建 | 末尾追加 |

在 `r`/`w`/`a` 后加 `b` 得到二进制模式（`"rb"`/`"wb"`），Windows 下含义重大（见 4.3）。

**要点**：
- **fopen 返回值必须检查**——NULL 表示失败，`perror` 打印错误原因；不检查就使用是崩溃的常见来源。
- **`"w"` 会静默清空已有文件**（误用等于删数据），模式区分大小写、`"R"` 非法；**每个 fopen 必须配一个 fclose**，泄漏句柄会耗尽进程的文件描述符上限。

### 3.2 fgets / fputs 文本行读写

```c
#include <stdio.h>
#include <string.h>
int main(void) {
    FILE *fp = fopen("lines.txt", "r");
    if (fp == NULL) { perror("fopen"); return 1; }
    char line[128];
    while (fgets(line, sizeof(line), fp) != NULL) {
        line[strcspn(line, "\n")] = '\0';   /* 去掉行尾换行 */
        printf("行: %s\n", line);
    }
    fclose(fp);
    return 0;
}
```

| 函数 | 行为 | 注意 |
|------|------|------|
| `fgets(buf, size, fp)` | 最多读 size-1 个字符，自动补 `\0`，**保留行尾 `\n`** | 读到 EOF/出错返回 NULL |
| `fputs(str, fp)` | 写入字符串，**不自动加 `\n`** | 失败返回 EOF |

**要点**：
- **fgets 通常比不受限读取更安全**：`gets` 已从标准移除，`scanf("%s")` 不限制长度——两者都会缓冲区溢出；fgets 以 size 为边界，天然防溢出。
- 行长超过 size 时 fgets 会分多次返回同一行片段，且**不保证以 `\n` 结尾**——用 `strcspn` 查找换行；判断结束看 **fgets 的返回值**，而不是 `feof`（见 3.7）。

### 3.3 fprintf / fscanf 格式化读写

```c
#include <stdio.h>
int main(void) {
    FILE *fp = fopen("out.txt", "w");            /* 写 */
    if (fp == NULL) { perror("fopen"); return 1; }
    fprintf(fp, "name=%s age=%d\n", "alice", 25);
    fprintf(fp, "name=%s age=%d\n", "bob", 30);
    fclose(fp);
    fp = fopen("out.txt", "r");                  /* 读 */
    if (fp == NULL) { perror("fopen"); return 1; }
    char name[32];
    int  age;
    while (fscanf(fp, " name=%31s age=%d", name, &age) == 2)
        printf("读到: %s, %d 岁\n", name, age);
    fclose(fp);
    return 0;
}
```
**要点**：
- 格式串与 `printf`/`scanf` 完全一致，只是把目标从 `stdout`/`stdin` 换成 `FILE*`。
- **fscanf 返回成功赋值的参数个数**，必须与期望值比较（如 `== 2`）；格式串开头的空格用来吞掉上一行残留的换行。
- `%s` 必须限制宽度（`%31s`），否则同样溢出；字符串含空格时 `%s` 会拆断，结构化文本优先用 fgets + sscanf 组合。

### 3.4 fread / fwrite 二进制读写

```c
#include <stdio.h>
typedef struct { int id; char name[16]; } Item;
int main(void) {
    Item items[3] = {{1, "a"}, {2, "b"}, {3, "c"}};
    FILE *fp = fopen("items.bin", "wb");
    if (fp == NULL) { perror("fopen"); return 1; }
    size_t n = fwrite(items, sizeof(Item), 3, fp);
    if (n != 3) fprintf(stderr, "只写入了 %zu 项\n", n);
    fclose(fp);
    fp = fopen("items.bin", "rb");
    if (fp == NULL) { perror("fopen"); return 1; }
    Item buf[3] = {{0}};
    n = fread(buf, sizeof(Item), 3, fp);
    printf("读回 %zu 项\n", n);
    fclose(fp);
    return 0;
}
```
**要点**：
- `fwrite(ptr, size, nmemb, fp)` 返回**完整写入的元素个数**，`fread` 同理——小于请求值就是磁盘满、短读或提前 EOF，必须检查。
- **不要直接写含指针的结构体**：指针值只在本次进程内有效，重启后指向的堆内存早已不存在；结构体只能含定长字段（数值 + 定长字符数组）。
- 二进制文件跨机器迁移要考虑结构体 padding 与字节序（ph12）；写入用 `sizeof(Item)`，读取也必须用同一结构体定义。

### 3.5 fseek / ftell / rewind 文件定位

```c
#include <stdio.h>
int main(void) {
    FILE *fp = fopen("data.bin", "rb");
    if (fp == NULL) { perror("fopen"); return 1; }
    fseek(fp, 0, SEEK_END);      /* 跳到末尾 */
    long size = ftell(fp);       /* 偏移量即文件大小 */
    printf("大小: %ld 字节\n", size);
    rewind(fp);                  /* 回开头, 并清错误标志 */
    fseek(fp, 10, SEEK_SET);     /* 距开头 10 字节 */
    fseek(fp, 4, SEEK_CUR);      /* 从当前位置再跳 4 字节 */
    fseek(fp, -8, SEEK_END);     /* 从末尾往前 8 字节 */
    fclose(fp);
    return 0;
}
```

| 函数 | 作用 |
|------|------|
| `ftell(fp)` | 返回当前位置（距开头的字节偏移），`-1L` 表示出错 |
| `fseek(fp, offset, whence)` | 定位；成功返回 0，失败返回非 0 |
| `rewind(fp)` | 等价 `fseek(fp, 0, SEEK_SET)` + 清除 EOF/错误标志 |

`whence` 取 `SEEK_SET`（开头）/ `SEEK_CUR`（当前位置）/ `SEEK_END`（末尾）。

**要点**：
- 偏移单位是**字节**，不是行、不是记录——"跳到第 N 条记录"要自己算 `N * sizeof(Record)`；`ftell` 用 `long`，超 2GB 用 `fgetpos`/`fsetpos`（ph08）。
- 读和写**共享同一个位置指示器**，交替读写前要先想清楚当前在哪个位置；文本模式下 `fseek`/`ftell` 的偏移在 Windows 上**不可靠**（见 4.3）。

### 3.6 缓冲与刷新 fflush

```c
#include <stdio.h>
int main(void) {
    FILE *fp = fopen("log.txt", "a");
    if (fp == NULL) { perror("fopen"); return 1; }
    fprintf(fp, "critical event\n");
    fflush(fp);      /* 强制把用户态缓冲交给内核 */
    fclose(fp);
    return 0;
}
```
**要点**：
- stdio 默认**全缓冲**（攒满一块才写，通常 4KB~8KB），所以 `fprintf` 之后数据可能还在用户态缓冲区里；`fflush(fp)` 立即冲刷，`fflush(NULL)` 冲刷所有输出流。**fflush 对输入流是未定义行为**。
- 程序正常 `fclose`/退出会刷新，但**崩溃（kill -9、断电）时不保证**；fflush 只是"用户态 → 内核"，真正落盘还需 `fsync`（POSIX，ph13 详解）。

### 3.7 feof / ferror 状态判断

```c
#include <stdio.h>
int main(void) {
    FILE *fp = fopen("data.txt", "r");
    if (fp == NULL) { perror("fopen"); return 1; }
    char line[128];
    while (fgets(line, sizeof(line), fp) != NULL) {
        /* 正常处理每一行 */
    }
    if (ferror(fp))      fprintf(stderr, "读取过程中发生 IO 错误\n");
    else if (feof(fp))   printf("正常读到文件末尾\n");
    fclose(fp);
    return 0;
}
```
**要点**：
- `feof` 只在**读取失败之后**才有意义：它回答"刚才那次失败是不是因为到了末尾"；`ferror` 区分"正常读完"与"真 IO 错误"，`clearerr(fp)` 可清除这两个标志。
- **不要用 `while (!feof(fp))` 控制循环**：EOF 标志要等一次读取失败才置位，循环体会多执行一次空读，这是经典 bug。

## 4. 底层原理

### 4.1 stdio 缓冲机制

stdio 在用户态为每个流维护一块缓冲区，按类型分三种：

| 缓冲类型 | 触发刷新的时机 | 典型对象 |
|----------|---------------|---------|
| 全缓冲（块缓冲） | 缓冲区满、显式 fflush、fclose、程序正常退出 | 普通文件 |
| 行缓冲 | 遇到 `\n`、缓冲区满、显式 fflush | 终端（stdin/stdout） |
| 无缓冲 | 立即写入 | stderr |

```text
fprintf("hello") ──▶ 用户态缓冲区 (FILE 内, 默认全缓冲)
                              │ 攒满 4KB, 或 fflush / fclose
                              ▼
                        write() 系统调用 ──▶ 内核 Page Cache ──▶ 磁盘
```
理解这个链条，就能解释两个现象：程序崩溃时最近几次 `printf`/`fprintf` 的内容可能丢了（还在用户态缓冲）；`fseek` 等定位函数会先隐式刷新缓冲，保证偏移与缓冲一致。

### 4.2 FILE 与文件描述符（fd）的关系

`FILE` 是**库层抽象**，文件描述符（file descriptor，fd）是**内核资源句柄**：

```text
应用层:    FILE *fp ── 用户态缓冲区 + 位置指示器 + 错误状态
                      │ fopen 内部: open() → 得到 fd
系统调用层: int fd  ── 内核维护: 文件偏移、打开方式、引用计数
                      │ read()/write()/lseek()/close()
内核:       磁盘 / 设备
```
- `fopen` 内部调用 `open` 拿到 fd，再把 fd 包进 `FILE`；`fclose` 内部先刷新缓冲再 `close(fd)`。
- **同一个文件不要 fd 与 FILE 混用**：`FILE` 有自己的缓冲，`write(fd, ...)` 的数据可能排在 `FILE` 缓冲之后，顺序错乱；反之 `read(fd)` 会绕过 FILE 缓冲读到旧数据。
- 多个 `FILE` 可以指向同一个 fd（如 `stdout` 与 `stderr` 常指向同一终端），各有各的缓冲。

### 4.3 文本模式与二进制模式在 Windows/Unix 的差异

C 标准只定义文本流与二进制流的抽象区别，具体映射由平台决定：

| 行为 | Unix/Linux | Windows |
|------|-----------|---------|
| 换行转换 | 无转换，`\n` 原样存储 | 文本模式：`\n` ↔ `\r\n` 自动转换 |
| 读文本 | 无 | 把 `\r\n` 转成 `\n`；`\x1A`（Ctrl+Z）视为 EOF |
| fseek/ftell | 偏移=真实字节位置，两种模式一致 | 文本模式下偏移是"逻辑位置"，与物理字节数不一致 |
| 二进制文件 | 加不加 `b` 无差别 | **必须用 `"b"` 模式**，否则数据被改写 |

因此**二进制文件必须显式使用 `"rb"`/`"wb"`**：在 Windows 上不加 `b`，写入时数据里的 `0x0A` 会被悄悄改成 `0x0D 0x0A`、读到 `0x1A` 会提前终止；在 Unix 上加不加都无差别，但写上 `b` 让代码可移植——这也是示例 4 必须用 `"wb"`/`"rb"` 的原因。

### 4.4 文件偏移与 fseek/ftell 的物理含义

文件在内核眼里是**一串字节**，`文件偏移`（file offset）就是"下一个字节在文件中的序号"，从 0 开始。每个打开的 `FILE`/fd 都维护一个**位置指示器**：

```text
偏移:  0   1   2   3   4   5   6   7  ...
文件: [b] [y] [t] [e] [s] [\n] [x] [y] ...
                    ▲
           fread / fwrite / fseek 都会移动这个位置
```
- 读 5 字节后位置指示器停在 5；再读 2 字节就到 7。`ftell` 就是把位置读出来；`fseek` 直接改这个位置，下一次读写从新位置开始。
- **偏移是逻辑位置，不等于物理扇区**：文件数据落在磁盘哪里由文件系统决定（inode → block 映射，ph08/ph13 涉及）；随机访问只是让内核去"找"对应块。
- 位置指示器可以跳到文件末尾之后（`fseek(fp, 100, SEEK_END)`），再写入会形成空洞（hole），空洞处读出的是 `\0`——这是稀疏文件的基础概念。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 读取配置文件 | `fopen("r")`、fgets、sscanf、注释与错误行处理 |
| CSV 数据交换 | fgets、strtok、sscanf、字段校验、坏行跳过 |
| 日志系统 | `fopen("a")`、fprintf、时间戳、fflush |
| 结构体数据持久化 | fwrite/fread、`"wb"`/`"rb"`、sizeof、定长记录 |
| 文件末尾追加数据 | `"a"` 模式、append-only 语义 |
| 大文件随机读取 | fseek、ftell、rewind、`N * sizeof(Record)` 定位 |
| 数据备份与导出 | 文本 ↔ 二进制互转、字段格式设计 |
| 状态保存/恢复 | 固定大小记录 + 版本字段 + 首条元数据记录 |

**不适合**此阶段的事项：
- mmap 内存映射文件、Page Cache 调优与 fsync 落盘边界（ph13 可靠文件 IO）
- WAL、崩溃恢复、SSTable 等存储引擎设计（ph17 数据库存储引擎基础）
- 网络 IO、socket、非阻塞/异步 IO（ph08 Linux 系统编程）
- 多线程并发读写同一文件、文件锁（ph08）

## 6. 代码示例

> 说明：示例均可直接编译运行（标准 C99），除示例 5 结尾附注的 fsync 片段外不依赖平台 API。每个示例的完整可运行文件在 [`examples/`](./examples/) 目录（含样例数据 students.csv / app.conf），验证环境 Apple clang 17（gcc 兼容），编译命令统一 `gcc -Wall -Wextra -std=c99`（命令见 examples/README.md）。

### 示例 1：文本文件逐行读取与统计（fgets）

对应 roadmap 练习"日志系统/文本统计工具"的读取骨架：逐行读、按行统计，并正确处理"文件不存在"。

```c
#include <stdio.h>
#include <string.h>
int main(int argc, char *argv[]) {
    if (argc != 2) {
        fprintf(stderr, "用法: %s <文件名>\n", argv[0]);
        return 1;
    }
    FILE *fp = fopen(argv[1], "r");
    if (fp == NULL) {                 /* 文件不存在/权限不足 */
        perror(argv[1]);
        return 1;
    }
    char line[512];
    int  lines = 0, words = 0, chars = 0;
    while (fgets(line, sizeof(line), fp) != NULL) {
        lines++;
        chars += (int)strlen(line);
        for (char *tok = strtok(line, " \t\n"); tok != NULL; tok = strtok(NULL, " \t\n"))
            words++;
    }
    if (ferror(fp)) {                 /* 区分"读完"与"读出错" */
        perror("读取失败");
        fclose(fp);
        return 1;
    }
    fclose(fp);
    printf("%s: %d 行, %d 单词, %d 字符\n", argv[1], lines, words, chars);
    return 0;
}
```

完整文件：`examples/ex01-line-stats.c`

要点：`fgets` 返回值控制循环、`strtok` 统计单词、`ferror` 兜底——把本阶段三大核心（行读、解析、错误处理）浓缩在一个例子里。

### 示例 2：CSV 文件解析器（fgets + strtok/sscanf）

对应 roadmap 练习"CSV 文件解析"与推荐项目"CSV 解析器"：处理空行与错误行，坏行报告行号并跳过。

```c
#include <stdio.h>
#include <string.h>
typedef struct {
    char   name[32];
    int    age;
    double score;
} Student;
int main(void) {
    FILE *fp = fopen("students.csv", "r");
    if (fp == NULL) { perror("students.csv"); return 1; }
    char line[256];
    int  line_no = 0, valid = 0, skipped = 0;
    while (fgets(line, sizeof(line), fp) != NULL) {
        line_no++;
        line[strcspn(line, "\r\n")] = '\0';   /* 兼容 \r\n 与 \n */
        if (line[0] == '\0') { skipped++; continue; }   /* 空行 */
        char *name  = strtok(line, ",");
        char *age   = strtok(NULL, ",");
        char *score = strtok(NULL, ",");
        char *extra = strtok(NULL, ",");
        if (name == NULL || age == NULL || score == NULL || extra != NULL) {
            fprintf(stderr, "第 %d 行: 字段数错误, 已跳过\n", line_no);
            skipped++;
            continue;
        }
        Student s;
        if (sscanf(age, "%d", &s.age) != 1 || sscanf(score, "%lf", &s.score) != 1) {
            fprintf(stderr, "第 %d 行: 数字格式错误, 已跳过\n", line_no);
            skipped++;
            continue;
        }
        if (strlen(name) >= sizeof(s.name)) {
            fprintf(stderr, "第 %d 行: 名字过长, 已跳过\n", line_no);
            skipped++;
            continue;
        }
        strcpy(s.name, name);
        printf("%-8s 年龄=%d 成绩=%.1f\n", s.name, s.age, s.score);
        valid++;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return 1; }
    fclose(fp);
    printf("共 %d 行: 有效 %d 条, 跳过 %d 行\n", line_no, valid, skipped);
    return 0;
}
```

完整文件：`examples/ex02-csv-parser.c`（样例数据 `examples/students.csv`）

要点：字段数校验（`extra != NULL` 拒绝多余列）、`sscanf` 返回值校验、长度上限校验——一个能扛住脏数据的解析器；测试时用含空行、坏行与多余列的文件验证跳过逻辑。注意 `strtok` 会破坏原字符串且非线程安全，生产级 CSV（含引号转义、字段内逗号）需要手写状态机解析（ph16）。

### 示例 3：配置文件的 key=value 读取

对应 roadmap 练习"读取配置文件"：支持空行、`#` 注释、`key = value` 与 `key=value` 两种写法，报告格式错误行。

```c
#include <stdio.h>
#include <string.h>
#define MAX_KEY 32
#define MAX_VAL 128
static char *trim(char *s) {               /* 去掉首尾空白(含行尾换行) */
    while (*s == ' ' || *s == '\t') s++;
    size_t len = strlen(s);
    while (len > 0 && (s[len - 1] == ' ' || s[len - 1] == '\t' ||
                       s[len - 1] == '\n' || s[len - 1] == '\r'))
        s[--len] = '\0';
    return s;
}
int main(void) {
    FILE *fp = fopen("app.conf", "r");
    if (fp == NULL) { perror("app.conf"); return 1; }
    char line[256];
    int  line_no = 0, loaded = 0;
    while (fgets(line, sizeof(line), fp) != NULL) {
        line_no++;
        char *s = trim(line);
        if (*s == '\0' || *s == '#') continue;       /* 空行/注释 */
        char *eq = strchr(s, '=');
        if (eq == NULL) {
            fprintf(stderr, "第 %d 行: 缺少 '=', 已忽略\n", line_no);
            continue;
        }
        *eq = '\0';                                  /* 拆成 key 与 value */
        char *key = trim(s);
        char *val = trim(eq + 1);
        if (*key == '\0' || *val == '\0') {
            fprintf(stderr, "第 %d 行: key 或 value 为空, 已忽略\n", line_no);
            continue;
        }
        if (strlen(key) >= MAX_KEY || strlen(val) >= MAX_VAL) {
            fprintf(stderr, "第 %d 行: 字段超长, 已忽略\n", line_no);
            continue;
        }
        printf("key=%-12s value=%s\n", key, val);
        loaded++;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return 1; }
    fclose(fp);
    printf("共 %d 行, 成功解析 %d 条配置\n", line_no, loaded);
    return 0;
}
```

完整文件：`examples/ex03-config-reader.c`（样例数据 `examples/app.conf`）

要点：`strchr` 找 `=` 再手工拆字段，比 `sscanf` 更可控；`trim` 让 `key = value` 与 `key=value` 统一；错误行只报告不中断——配置文件容忍坏行是工程惯例，测试文件应包含注释、错误格式行与空值。

### 示例 4：二进制文件读写结构体（fwrite/fread）

对应 roadmap 练习"二进制文件读写结构体数据"与"能设计简单持久化格式"：写定长记录、读回校验、检查短读写。

```c
#include <stdio.h>
typedef struct {
    int    id;        /* 数值 + 定长字符数组, 不含指针 */
    double score;
    char   name[32];
} Record;
static int write_records(const char *path) {
    FILE *fp = fopen(path, "wb");            /* 必须显式二进制模式 */
    if (fp == NULL) { perror(path); return -1; }
    Record data[] = {
        {1, 88.5,  "Alice"},
        {2, 92.0,  "Bob"},
        {3, 79.25, "Carol"},
    };
    size_t n = sizeof(data) / sizeof(data[0]);
    size_t written = fwrite(data, sizeof(Record), n, fp);
    if (written != n) {
        fprintf(stderr, "写入不完整: %zu/%zu\n", written, n);
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 0;
}
static int read_records(const char *path) {
    FILE *fp = fopen(path, "rb");
    if (fp == NULL) { perror(path); return -1; }
    Record r;
    size_t count = 0;
    while (fread(&r, sizeof(Record), 1, fp) == 1) {   /* 逐条读回 */
        printf("id=%d  name=%-8s  score=%.2f\n", r.id, r.name, r.score);
        count++;
    }
    if (ferror(fp)) { perror("读取失败"); fclose(fp); return -1; }
    fclose(fp);
    printf("共读回 %zu 条记录 (每条 %zu 字节)\n", count, sizeof(Record));
    return 0;
}
int main(void) {
    const char *path = "records.bin";
    if (write_records(path) != 0) return 1;
    return read_records(path) == 0 ? 0 : 1;
}
```

完整文件：`examples/ex04-bin-record.c`（运行生成 records.bin，验证后清理）

要点：
- **结构体只含定长字段**——如果 `name` 是 `char *`，写进文件的只是堆地址，重启后无效。
- `fread` 返回 1 表示读满一条；文件被截断时返回 0 且 `ferror` 可能未置位，可再配合 `feof` 判断"是否恰好结束"。
- 记录按 `sizeof(Record)` 等长排列，天然支持 `fseek(fp, N * sizeof(Record), SEEK_SET)` 随机读第 N 条；跨机器迁移需考虑 padding 与字节序（ph12），严谨格式会加 magic/版本/校验（ph17 起）。

### 示例 5：append-only 日志文件

对应 roadmap 练习"日志系统"与推荐项目"append-only 数据文件"：`"a"` 模式追加、时间戳、每次写入后 fflush。

```c
#include <stdio.h>
#include <time.h>
static int log_write(const char *path, const char *msg) {
    FILE *fp = fopen(path, "a");         /* "a": 每次写入前定位到末尾 */
    if (fp == NULL) { perror(path); return -1; }
    time_t now = time(NULL);
    struct tm *t = localtime(&now);
    if (fprintf(fp, "%04d-%02d-%02d %02d:%02d:%02d  %s\n",
                t->tm_year + 1900, t->tm_mon + 1, t->tm_mday,
                t->tm_hour, t->tm_min, t->tm_sec, msg) < 0) {
        fclose(fp);
        return -1;
    }
    if (fflush(fp) != 0) {               /* 用户态缓冲 → 内核 */
        perror("fflush");
        fclose(fp);
        return -1;
    }
    fclose(fp);
    return 0;
}
int main(void) {
    const char *path = "app.log";
    log_write(path, "server start");
    log_write(path, "user login: alice");
    log_write(path, "order created: #1001");
    printf("日志已追加写入 %s\n", path);
    return 0;
}
```

完整文件：`examples/ex05-append-log.c`（运行生成 app.log，验证后清理）

**append-only 的含义**：只允许在文件末尾追加，绝不修改/删除已有记录——天然抗并发写冲突，是 WAL（ph17）、LSM 顺序写（ph17）的核心思想雏形，也是推荐项目"append-only 数据文件"的骨架。

**关于持久化的两层保证**：

```c
fflush(fp);                              /* ① 用户态缓冲 → 内核 Page Cache */
fsync(fileno(fp));                       /* ② 内核 → 磁盘 (POSIX, ph13 详解) */
```
`fflush` 保证数据离开进程，但断电仍可能丢（还在内核 Page Cache）；`fsync` 才强制落盘。`fsync` 是 POSIX 函数（需要 `#include <unistd.h>`），不属于标准 C——ph06 阶段先用 `fflush` 理解缓冲，ph13 再深入刷盘边界。

## 7. 总结

### 关键要点

1. **文件打开后必须关闭**：fopen/fclose 成对出现，泄漏文件句柄会耗尽进程资源
2. **IO 操作必须检查返回值**：fopen 的 NULL、fread/fwrite 的短读写、fscanf 的匹配数，全部要查
3. **fgets 通常比不受限读取更安全**：带 size 边界、自动补 `\0`，代替 `gets`/`scanf("%s")`
4. **文本便于调试，二进制更紧凑**：文本可读可 diff，二进制按字节存、省空间快解析
5. **`"w"` 模式会清空文件**：误用等于删数据；追加用 `"a"`
6. **二进制结构体不能含指针**：只能写定长字段，否则写进文件的是无效地址
7. **fseek/ftell 是字节偏移**：随机读第 N 条记录要 `N * sizeof(Record)`；Windows 文本模式下不可靠
8. **fflush 只到内核，fsync 才落盘**：崩溃丢数据的边界在 ph13 补全
9. **feof 不能控制循环**：用读取函数返回值判断结束，feof/ferror 只在失败后区分原因

### 跨语言对比：文件操作

| 维度 | C stdio | C++ fstream | Go os.File | Python open | Rust File |
|------|---------|-------------|------------|-------------|-----------|
| 打开文件 | `fopen("f","r")` | `ifstream in("f")` | `os.Open` | `open("f")` | `File::open` |
| 逐行读取 | `fgets` + 手动处理 | `std::getline` | `bufio.Scanner` | `for line in f:` | `BufReader::lines()` |
| 二进制读写 | `fread`/`fwrite` | `read`/`write` | `Read`/`Write` 接口 | `f.read`/`f.write` | `Read`/`Write` trait |
| 错误处理 | 返回值/NULL 检查 | 流状态标志 | 显式 error 返回值 | 异常 | `Result<T, E>` |
| 缓冲控制 | `setvbuf`/`fflush` | `rdbuf` 精细控制 | `bufio.Writer` | 默认（解释器内建） | `BufReader`/`BufWriter` |
| 资源释放 | 手动 `fclose` | RAII 析构 | `defer f.Close()` | `with` 语句 | Drop |

C 的模型最"裸露"：没有 RAII、没有异常、没有自动关闭——**一切生命周期与错误都要自己负责**，这正是存储引擎场景需要的精确控制力。

### 阶段验收清单

- [ ] 能处理文件不存在（fopen 返回 NULL → perror + 优雅退出）、权限不足、格式错误（坏行报告并跳过）
- [ ] 能用 fgets/fputs/fprintf 读写文本文件，能用 fread/fwrite（`"wb"`/`"rb"`）读写二进制文件
- [ ] 能设计简单持久化格式（定长记录 / key=value / CSV），并说明文本与二进制的取舍
- [ ] 能检查每个 IO 调用的返回值，能正确处理 fclose 与 fflush
- [ ] 能用 fseek/ftell/rewind 随机定位读取，如"读第 N 条记录"或"计算文件大小"
- [ ] 能解释全缓冲/行缓冲/无缓冲的区别，以及 fflush 与 fsync 的边界

### 动手练习

本阶段练习见 [exercises/](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）：读取配置文件、CSV 文件解析、日志系统、二进制读写结构体共 4 题。完成 4 题后继续。

### 阶段项目

本阶段综合项目见 [project/](./project/)：**CSV 解析器**（三重校验 + 坏行报告 + 失败原因统计 + `-s` 按成绩排序，为后续日志系统提供数据输入）。

- [ ] 完成 exercises 全部练习并复盘
- [ ] 独立完成 project（通过 README 验收标准）

### 下一阶段

[编译、调试与工程化阶段](../ph07-build-debug/07-build-debug.md) — gcc/clang、Makefile/CMake、GDB 调试、静态库动态库。
