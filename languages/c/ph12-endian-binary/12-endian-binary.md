# C 语言字节序、内存对齐与二进制格式解析阶段

> 面向系统底层、存储引擎方向，本阶段把"会写 C"升级为"能处理字节与布局"——从大小端、结构体对齐这些内存事实出发，掌握二进制 record / frame 的安全解析、checksum 与 varint，为数据库文件、WAL 日志、网络协议和跨平台二进制格式打好位级地基。

## 1. 概述

字节序、内存对齐与二进制格式解析阶段是 C 学习路线中"从语言机制到真实数据格式"的转折点。目标（roadmap §12）：**能处理数据库文件、WAL 日志、SSTable block、网络 frame 和跨平台二进制数据布局**。ph09 埋下"结构体存在对齐填充、上'线'要逐字段处理字节序"的伏笔，ph10 埋下"序列化/网络代码不要强转结构体指针、未对齐访问是 UB"的伏笔，ph11 埋下"解析器的边界逻辑要用测试钉死、越界靠 Sanitizer 兜底"的伏笔——本阶段把它们全部兑现为一套可复用的位级处理能力。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 字节序 | 大端/小端的定义与检测、显式大端/小端读写函数、网络字节序（htonl/ntohl 对照） |
| 内存布局 | 结构体对齐与 padding、sizeof 与字段偏移（offsetof）、_Alignof/_Alignas、packed 的取舍 |
| 位级操作 | 位运算、掩码、移位、flags 打包/解包、位域（bit-field）的跨平台禁忌 |
| 安全解析 | 不可信字节流的安全读取（长度先校验、逐字段显式读取）、length-prefix frame 增量解析 |
| 完整性 | checksum / CRC-32、损坏与截断的错误码区分 |
| 格式演进 | varint 编码、magic number 与版本号、保留字段与兼容策略 |

这个阶段只涉及字节序（大端/小端/网络字节序）、结构体对齐与 padding、sizeof/offsetof、位运算掩码移位、二进制 record 与 length-prefix frame 的安全解析、checksum/CRC、varint、magic number 与版本号，**不涉及 mmap、Page Cache 与 fsync 刷盘语义（ph13，roadmap 第 13 节）、跨语言互操作 ABI（ph14，roadmap 第 14 节，目录待建）、存储引擎的完整 WAL/MemTable/SSTable 实现（ph16，roadmap 第 16 节，目录待建）和网络 socket 编程（ph08）** — 那些是 ph13 mmap、Page Cache 与可靠文件 IO 阶段、ph14 C 与 C++ / Python / Rust 互操作阶段、ph16 数据库存储引擎基础阶段和 ph08 Linux 系统编程阶段的内容；位域（bit-field）布局是实现定义的，本阶段只做对照演示，**不用于跨平台格式**；并发与内存序不属于本阶段（衔接 ph08，深入属并发专题）。

## 2. 来源与演变

**二进制格式的三大设计支柱——字节序、对齐、校验——各有清晰的历史脉络**。字节序问题源自 1970 年代早期计算机对"多字节整数在内存中如何摆放"的分歧：PDP-11（1970）甚至在同一台机器上混合两种字节序（16 位与 32 位访问互为反序），IEEE 754（1985）只定义浮点数的位模式、不定义字节序，而 1980 年 Danny Cohen 的论文 *On Holy Wars and a Plea for Peace* 借用《格列佛游记》里"从小端敲鸡蛋 vs 从大端敲鸡蛋"的党派之争，把 little-endian / big-endian 两个词固定进了计算机词汇。**网络字节序（network byte order）统一为大端**是互联网协议的务实选择：RFC 791（1981，IPv4）与 RFC 1700（1994）规定所有多字节字段按大端传输，`htonl`/`ntohl` 就是为此提供的宿主序 ↔ 网络序转换函数——这一决策让 1980 年代的异构机器能互连，代价是至今每个 C 网络程序员都要面对"字节序"这件事。

**对齐（alignment）则源于硬件寻址**：早期内存按"字"访问，未对齐的取数要么不能执行、要么被拆成多次总线事务。C 标准把结构体字段的排布交给"实现定义"（自然对齐 + 填充），于是同一份 struct 在不同编译器/平台下 `sizeof` 不同——这正是"struct 不能直接当线上格式"的历史根源。**校验与格式自描述是工程演进的结果**：COBOL/FORTRAN 时代的固定 record 文件假设"字节一字不差"，一旦磁道损坏整文件报废；1980~1990 年代网络协议引入长度前缀与校验（如以太网帧尾 FCS、TCP 首部校验和）；1996 年发布的 PNG 把 magic + 分块长度 + CRC-32 变成图像文件的标准形态；2008 年 Google 开源 protobuf 把 varint（7 位一组 + 续位标记的紧凑整数编码）推成跨语言序列化的主流做法。

| 里程碑 | 年份 | 对二进制格式的意义 |
|--------|------|-------------------|
| PDP-11 | 1970 | 混合字节序暴露"多字节字段摆放"问题 |
| IEEE 754 | 1985 | 浮点位模式标准化，但字节序仍随平台 |
| RFC 791 / 1700 | 1981 / 1994 | 网络字节序统一为大端；htonl/ntohl 进入 POSIX |
| PNG 1.0 | 1996 | magic + 分块长度 + CRC-32 成为文件格式标准形态 |
| protobuf | 2008 | varint 让"紧凑、自描述、跨语言"成为序列化主流 |
| C11 | 2011 | _Alignof/_Alignas 进入标准（offsetof 自 C89 已有），显式对齐可控 |

本文示例以 **C11** 为基线（C99 之后、C23 普及之前，GCC/Clang/MSVC 支持度最一致的公共子集，与 ph11 同一口径）。验证工具链：**Apple clang 21.0.0（`cc`，macOS Darwin arm64）**，全部代码 `-Wall -Wextra -std=c11` 零警告编译运行。`htonl`/`ntohl` 属于 POSIX（`arpa/inet.h`）而非标准 C，本阶段以"显式逐字节组装/拆解"为主、POSIX 函数仅作对照——显式读写是任何平台都可移植的写法。字节序与对齐的事实（"低地址放低位还是高位""int 对齐到 4 字节"）由硬件决定、数十年稳定，本阶段讲的位级处理方法短期内不会过时。

## 3. 语法与参数

### 3.1 大端与小端：多字节字段的内存顺序

**字节序（endianness）** 描述"多字节整数在内存里从低地址到高地址按什么顺序放"：**小端**（little-endian）低位字节在前（低地址），**大端**（big-endian）高位字节在前。值 `0x01020304` 在小端机器内存里是 `04 03 02 01`，在大端机器是 `01 02 03 04`——同一段字节，读法不同，值就不同。

```c
// examples/ex01-endian.c —— 大小端检测与显式字节序读写（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int is_little_endian(void) {
    uint16_t x = 0x0102u;
    uint8_t b[2];
    memcpy(b, &x, sizeof x);      /* 位模式搬运（memcpy 可移植，union 是 C 扩展语义） */
    return b[0] == 0x02u;         /* 低地址字节是低位 → 小端 */
}

static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static void write_be32(uint8_t *p, uint32_t v) {
    p[0] = (uint8_t)(v >> 24);
    p[1] = (uint8_t)(v >> 16);
    p[2] = (uint8_t)(v >> 8);
    p[3] = (uint8_t)v;
}
```

**为什么不能用"强转指针后读字段"判字节序或做交换**：`uint32_t x; uint8_t *b = (uint8_t *)&x;` 这类"用 `unsigned char *` 查看对象表示"是 C 标准明确允许的（字符类型例外条款）；但把**字节流**强转成结构体指针再读字段就是另一回事——那会把平台字节序与 padding 一起泄露到线上格式（见 3.6）。检测字节序的可移植写法就是上面的 `memcpy` 位模式搬运：**memcpy 是 C 标准定义好的"字节 ↔ 值"搬运通道**，编译器会把它优化成单条加载指令。

**关键认知**

- 字节序只影响**多字节**字段的**内存表示**；单字节（`uint8_t`）无字节序问题，字符串按字节序逐字节传输也无问题
- **显式读写函数是跨平台格式的基石**：`read_be32` 无论跑在大端还是小端机器上，读同一段字节都得同一个值——落线格式只认"字节序列"，不认平台
- 现代主流处理器（x86-64、ARM64 实际配置、RISC-V 常见配置）都是小端；但**"我的机器是小端所以无所谓"是经典错误**——文件/网络数据可能来自任何平台

### 3.2 网络字节序：htonl / ntohl 与显式读写

**网络字节序 = 大端**（见第 2 章来源）。POSIX 提供 `htonl`/`ntohl`（host-to-network / network-to-host，`uint32_t`）与 `htons`/`ntohs`（`uint16_t`）在宿主序与网络序之间转换：在小端机器上它们是字节翻转，在大端机器上是恒等。它们不属于标准 C（Windows 上在 winsock 里，签名也可能不同），跨平台代码要么用它们、要么用 3.1 的显式读写。

| 写法 | 可移植性 | 适用 |
|------|---------|------|
| `htonl(x)` / `ntohl(x)` | POSIX / winsock | 单机小工具、协议栈内部 |
| 显式 `read_be32` / `write_be32` | 任何 C 编译器 | 文件格式、库代码、跨平台发布 |

`examples/ex01-endian.c` 在小端机器上实测：`htonl(0x01020304)` 首 4 字节为 `01 02 03 04`，且 `ntohl(htonl(x)) == x` 往返不变；小端平台上 `htonl(x) == swap32(x)`（网络序转换就是字节翻转）由练习 2 的参考实现 `sol-02-endian-swap.c` 验证。**要点**：网络传输、文件落盘时"多字节字段必须明确字节序"（roadmap 必会概念）——显式读写把这句话变成代码，任何平台读同一字节流都得同一结果。

### 3.3 结构体对齐与 padding：sizeof 不等于字段大小之和

**对齐（alignment）** 指对象在内存中的起始地址必须是指定值的倍数（如 `int` 对齐到 4）。编译器按"自然对齐"排布结构体字段：每个字段从"其对齐值倍数"的偏移开始，放不下就在前一个字段后插入 **padding（填充）**，结构体总大小再圆整到对齐值的倍数。

```c
// examples/ex02-align.c —— 结构体对齐、padding 与 sizeof/offsetof（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
struct S1 {           /* 按声明顺序自然对齐 */
    char     a;       /* 偏移 0 */
    int32_t  b;       /* 需要 4 字节对齐 → 偏移 4（1~3 是 padding） */
    char     c;       /* 偏移 8 */
};                    /* 总大小 9 → 圆整到对齐值 4 的倍数 = 12 */

struct S2 {           /* 把 4 字节字段提前，padding 更少 */
    int32_t  b;       /* 偏移 0 */
    char     a;       /* 偏移 4 */
    char     c;       /* 偏移 5 */
};                    /* 总大小 6 → 圆整到 4 的倍数 = 8 */

struct __attribute__((packed)) SP {   /* 编译器扩展：取消填充 */
    char     a;
    int32_t  b;
    char     c;
};                                      /* sizeof = 1 + 4 + 1 = 6 */
```

本机（Apple clang 21.0.0, arm64）实测：`sizeof(struct S1) = 12`（`a` 后 3 字节 padding + 末尾 3 字节圆整）、`sizeof(struct S2) = 8`、`sizeof(struct SP) = 6`；`_Alignof(int32_t) = 4`、`_Alignof(uint64_t) = 8`。**字段重排可以显著省空间**（S1 → S2 省 4 字节）：把大对齐字段往前放，padding 自然减少——这是结构体设计的第一条经验法则。

**packed 的陷阱**：`__attribute__((packed))`（GCC/Clang 扩展，MSVC 用 `#pragma pack`）取消填充、把 `sizeof` 压到字段大小之和，但它是**编译器扩展而非标准**，且 packed 结构体里的字段可能未对齐（访问 `SP.b` 是未对齐访问，见 4.3）。**跨平台格式不要依赖 packed 结构体**：不同编译器对位域与 packed 的布局细节是实现定义的，换了工具链就变。正确的姿势是"**布局写死在解析逻辑里**"（3.6）——用显式偏移 + 显式字节序读写，struct 只作为已对齐的内存视图。

### 3.4 sizeof 与字段偏移：offsetof 与 _Alignof

`sizeof` 给出对象/类型的字节数（含 padding），`offsetof(type, member)` 给出字段相对结构体起始的偏移（`<stddef.h>`，C11 标准），`_Alignof(type)` 给出类型的对齐要求。三者是"看穿结构体内存布局"的调试与设计工具，`examples/ex02-align.c` 实测：

```text
S1       sizeof=12 align=4  offsetof: a=0 b=4 c=8
S2       sizeof=8  align=4  offsetof: a=4 b=0 c=5
SP       sizeof=6  align=1  offsetof: a=0 b=1 c=5
Align16  sizeof=16 align=16  offsetof: a=0 b=8 c=0
```

- `offsetof` 是**编译期常量**，可用来做 `_Static_assert`（ph09 已示范）：把"字段必须在这个偏移"写进编译期契约
- `_Alignas(16)` 可强制**对象**按 16 对齐（C11 标准，作用于变量声明）；给结构体**类型**指定对齐用 `__attribute__((aligned(16)))`（GNU 扩展）——`_Alignas` 不能直接修饰 struct 类型（实测 clang 报 "'_Alignas' attribute ignored [-Wignored-attributes]" 警告，修饰被忽略）
- **struct 的 sizeof/偏移是编译期事实，但换了编译器/平台就变**——这正是 ph06 说的"跨机器迁移要考虑 padding 与字节序"的落点：严谨的二进制格式不依赖 struct 布局，而是显式定义字节偏移

### 3.5 位运算、掩码与移位：flags 打包与字段提取

二进制格式的"小字段"（flag 位、4 位类型 + 12 位长度这种打包字段）用**位运算 + 掩码 + 移位**读写。铁律来自 ph10：**位运算一律用无符号类型**（有符号右移是算术移位、实现定义，移位溢出是 UB），移位位数先检查。

```c
// examples/ex03-bits.c —— 位运算、掩码、移位与位域对比（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
#define FLAG_READ  0x01u   /* bit0 */
#define FLAG_WRITE 0x02u   /* bit1 */
#define FLAG_EXEC  0x04u   /* bit2 */
#define FLAG_OWNER 0x80u   /* bit7 */

#define MASK_TYPE 0xF000u   /* 高 4 位 */
#define MASK_LEN  0x0FFFu   /* 低 12 位 */
static uint16_t pack_fields(unsigned type, unsigned len) {
    return (uint16_t)(((uint16_t)(type & 0x0Fu) << 12) | (uint16_t)(len & 0x0FFFu));
}
```

常用操作模式：**置位** `f |= FLAG_X`、**清位** `f &= ~FLAG_X`、**翻转** `f ^= FLAG_X`、**提取** `(f >> n) & 1u`、**打包字段** `(type << 12) | (len & 0x0FFF)`、**解包字段** `(packed >> 12) & 0xF`。`examples/ex03-bits.c` 实测：`pack_fields(3, 0xABC)` → `0x3abc` → 解回 `type=3 len=2748` 往返一致。

**位域（bit-field）对照**：`struct BitFieldHeader { unsigned type : 4; unsigned len : 12; };` 写法更"像结构体"，但位域从字段顺序、跨字节切分到高低位端全部是实现定义的——同一份代码在 GCC 与 MSVC 下布局可能不同。**跨平台协议禁止用位域**，一律显式掩码 + 移位（roadmap 必会概念"位运算、掩码、移位"正是为此）。

### 3.6 安全解析不可信字节流：先校验长度，再逐字段读取（核心）

roadmap 必会概念第一条：**不要直接把不可信字节强转成结构体指针**。为什么？三重风险：

| 风险 | 说明 |
|------|------|
| 字节序 | 结构体字段按主机序解释，跨平台直接读错值 |
| padding/布局 | struct 布局由编译器决定，`sizeof` 与线上长度对不上 |
| 对齐 | 字节流起始地址未必对齐到结构体对齐值，未对齐访问是 UB（ph10） |

安全做法是一条固定流水线（`examples/ex04-record.c` 的 `record_parse`，本阶段最重要的代码模式）：

```c
// examples/ex04-record.c —— 安全解析二进制 record（重点示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int record_parse(const uint8_t *buf, size_t avail, size_t off,
                        Record *out, size_t *consumed) {
    if (avail - off < REC_HEADER_SIZE)
        return PARSE_TRUNC;                       /* ① 头部长度先校验 */
    if (read_be32(buf + off) != REC_MAGIC)
        return PARSE_MAGIC;                       /* ② magic */
    if (read_be16(buf + off + 4) != REC_VERSION)
        return PARSE_VERSION;                     /* ③ 版本 */
    uint16_t type = read_be16(buf + off + 6);
    if (type != REC_TYPE_PUT && type != REC_TYPE_DEL)
        return PARSE_TYPE;                        /* ④ 类型 */
    uint32_t key_len = read_be32(buf + off + 8);
    uint32_t value_len = read_be32(buf + off + 12);
    /* ⑤ payload + CRC 的总长度先校验（uint64 防溢出） */
    if ((uint64_t)REC_HEADER_SIZE + key_len + value_len + REC_CRC_SIZE >
        avail - off)
        return PARSE_TRUNC;
    /* ⑥ checksum 覆盖 [0, 16+k+v) —— 头部字段 + key + value */
    size_t covered = REC_HEADER_SIZE + (size_t)key_len + value_len;
    if (crc32(buf + off, covered) != read_be32(buf + off + covered))
        return PARSE_CRC;
    out->type = type;
    out->key = buf + off + REC_HEADER_SIZE;
    out->key_len = key_len;
    out->value = buf + off + REC_HEADER_SIZE + key_len;
    out->value_len = value_len;
    *consumed = covered + REC_CRC_SIZE;
    return PARSE_OK;
}
```

流水线六步：**① 长度先校验（头部）→ ② magic → ③ 版本 → ④ 字段合法性 → ⑤ payload 长度校验 → ⑥ checksum → 才读取字段**。顺序不能乱——长度校验永远在读取之前（roadmap 必会概念"多数二进制解析应先检查长度再读取字段"），错误码区分"截断 / 非本格式 / 版本旧 / 类型非法 / 损坏"五类，让调用方能给出准确诊断。`examples/ex04-record.c` 实测：正常 2 条 record 全部通过（CRC 校验通过）；翻转 payload 一字节 → `PARSE_CRC`；payload 截到一半 → `PARSE_TRUNC`。

> 本阶段只讲"内存字节流"的安全解析；**从文件/网络读到字节流本身（read/write、socket）属于 ph06/ph08 阶段**，这里把"已到手的字节流"当作起点。

### 3.7 length-prefix frame：先读长度、按长度等数据

**length-prefix frame** 是网络协议与日志格式最常见的定界方式：`[len: u16 大端][payload: len 字节]`。它的核心价值是"**长度先于数据到达**"——解析器先读 2 字节长度，就知道还要等多少字节，天然支持**分块到达**（一个 frame 可能被拆在多次 read 里）与**截断识别**（EOF 时长度没凑够）。

```c
// examples/ex05-frame.c —— length-prefix frame 增量解析器（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
typedef struct {
    uint8_t buf[FRAME_MAX_PAYLOAD + 2];   /* 上限 + 2 字节长度字段 */
    size_t  len;                          /* 当前缓冲字节数 */
    size_t  need;                         /* 当前 frame 期望总长(2+payload) */
} FrameReader;

static int fr_feed(FrameReader *r, const uint8_t *data, size_t n,
                   uint8_t *out, size_t cap, size_t *out_len) {
    if (n > sizeof r->buf - r->len)
        n = sizeof r->buf - r->len;              /* 防内部溢出: 只收得下的部分 */
    if (n > 0) {
        memcpy(r->buf + r->len, data, n);
        r->len += n;
    }
    if (r->len >= 2) {                           /* 长度字段(大端)齐了 */
        uint16_t plen = (uint16_t)(((uint16_t)r->buf[0] << 8) | r->buf[1]);
        if (plen > FRAME_MAX_PAYLOAD)
            return -1;                           /* 长度超上限: 直接判非法 */
        r->need = (size_t)plen + 2;
        if (r->len >= r->need) {                 /* 整个 frame 齐了 */
            if (plen > cap) return -1;           /* 调用方缓冲太小 */
            memcpy(out, r->buf + 2, plen);
            *out_len = plen;
            memmove(r->buf, r->buf + r->need, r->len - r->need);
            r->len -= r->need;                   /* 消费掉, 窗口前移 */
            r->need = 0;
            return 1;
        }
    }
    return 0;
}
```

增量状态机返回三态：`1 = 解出一个完整 frame` / `0 = 还差数据（继续喂）` / `-1 = 长度非法（超上限，直接放弃）`。**上限检查是必须的**：长度字段是 u16 但缓冲区有限，`0xFFFF` 这样的长度必须先判非法再分配/拷贝，否则就是内存炸弹（ph10 的越界与 ph04 的内存管理在这里交汇）。`examples/ex05-frame.c` 实测：25 字节流（3 个 frame）按 5 字节一块喂入，任意切分下 3 个 frame 全部正确解出；截断场景返回"还差数据"，超限场景返回"长度非法"。

### 3.8 checksum / CRC：发现损坏、截断与半写入

**checksum** 是格式的"体检报告"：写入时对字段计算一个校验值随数据存储，读取时重算对比——不一致就说明数据在写、传、存的过程中被改动了。**CRC-32**（IEEE 802.3，反射多项式 `0xEDB88320`）是文件格式与网络协议最常用的强校验：检错能力远好于求和/异或这类简单 checksum（能检测突发错误），32 位宽度让碰撞概率足够低。标准检验值：`crc32("123456789") == 0xCBF43926`（本机已验证，`examples/ex04-record.c` 内实现）。

```c
// examples/ex04-record.c —— CRC-32 实现（IEEE 802.3, 反射多项式）
static uint32_t crc32(const uint8_t *data, size_t len) {
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
    }
    return ~crc;
}
```

**CRC 覆盖范围要"连续且不含校验字段自身"**——本阶段踩过的坑：校验值放中间会导致"被覆盖区间横跨校验字段"，写入与读取算出的值不一致。经验法则：**校验字段放记录尾部**（PNG 也是把 CRC 放 chunk 末尾），被覆盖区间从记录头到校验字段前，天然连续。roadmap 必会概念"checksum 能帮助发现半写入、截断和数据损坏"：崩溃/断电产生的半写入 record，要么长度字段非法、要么 CRC 对不上——回放时跳过即可（project/ 的 WAL 工具就是完整示例）。

### 3.9 varint 编码：小整数只占 1 字节

**varint**（LEB128）是无符号整数的紧凑编码：**每字节低 7 位是数据，最高位是"还有后续"的续位标记**，小整数只占 1 字节，大整数按需扩展（`uint32_t` 最多 5 字节）。它按字节流解释、与平台字节序无关，是 protobuf、WAL 长度字段、RocksDB 等系统的标配。

```c
// examples/ex06-varint.c —— varint 编码解码（已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static size_t varint_encode(uint32_t v, uint8_t out[VARINT_MAX_BYTES]) {
    size_t n = 0;
    while (v >= 0x80u) {
        out[n++] = (uint8_t)(v & 0x7Fu) | 0x80u;   /* 续位标记 0x80 */
        v >>= 7;
    }
    out[n++] = (uint8_t)v;                          /* 末字节无续位标记 */
    return n;
}

static size_t varint_decode(const uint8_t *in, size_t avail, uint32_t *out) {
    uint32_t v = 0;
    size_t n = 0;
    while (n < avail && n < VARINT_MAX_BYTES) {
        v |= (uint32_t)(in[n] & 0x7Fu) << (7u * n);   /* 每字节 7 位 */
        if ((in[n] & 0x80u) == 0) {                   /* 无续位 → 结束 */
            *out = v;
            return n + 1;
        }
        n++;
    }
    return 0;   /* 截断或超 5 字节: 非法 */
}
```

`examples/ex06-varint.c` 实测：`0 → 00`、`127 → 7f`、`128 → 80 01`、`16383 → ff 7f`、`16384 → 80 80 01`、`0xFFFFFFFF → ff ff ff ff 0f`（5 字节）全部往返一致；`{0x80, 0x80}`（全是续位、没有结束字节）判非法。**解码必须检查截断与超长**（超过 5 字节意味着高位数据丢失，是格式损坏信号）——与 3.7 的长度上限检查是同一个原则：解析器的每个"读取"之前都有"检查"。

### 3.10 magic number 与版本号：文件格式的身份证

**magic number** 是文件/记录开头的固定字节序列，让工具一读就能回答"这是不是我的文件"（`file` 命令、PNG 的 `\x89PNG`、ELF 的 `\x7fELF` 都是）。**版本号**回答"这是哪个时代的格式"。两者加上 checksum 构成 roadmap 必会概念"**二进制格式要考虑版本兼容和损坏检测**"的完整契约：

| 组件 | 作用 | 坏文件的表现 |
|------|------|-------------|
| magic | 识别格式 | 读错文件 → 立刻拒绝，不产生垃圾输出 |
| 版本号 | 格式演进 | 旧版本文件 → 提示"需升级"而非崩溃 |
| reserved | 为未来留位 | 非 0 视为损坏，杜绝"未定义字段被任意利用" |
| checksum | 数据完整性 | 半写入/位翻转 → 精确报"损坏于哪个 record" |

`examples/ex06-varint.c` 演示了最小文件头：`magic("NV01") + 版本(1) + 记录数(varint)`，读取时先校验 magic 与版本再解析。**版本演进策略**：永远在头部放版本号；新版本可加字段但不动旧字段的偏移；reserved 字段固定写 0、读取时校验为 0——这样旧程序读新文件能安全拒绝，新程序读旧文件能兼容（或明确报"版本过低"）。project/ 的 WAL 工具把这三件套（magic + 版本 + CRC）完整落地。

## 4. 底层原理

### 4.1 对齐的硬件根源：为什么内存要求"按倍数放"

CPU 访问内存的单位是**字（word）**，早期机器的 load/store 指令要求地址按字对齐：一次取 4 字节，地址必须是 4 的倍数，否则要么硬件报 fault、要么拆成多次总线事务。x86 出于兼容允许未对齐访问（但慢——现代 x86 上未对齐 load/store 可能触发异常处理路径或多次事务），ARM 的早期版本直接 fault，ARM64 的部分场景静默产生错误结果。**C 标准把"未对齐访问"交给实现定义，而 ph10 已讲过：对"对齐要求更高的类型"做未对齐访问，在 C 里就是 UB**——这正是"字节流不能直接强转 struct 指针"的底层原因之一：编译器假定指针是对齐的，一旦不成立，一切赌注都作废。

### 4.2 编译器如何排布结构体

结构体布局是"字段对齐 + 填充 + 尾部圆整"三步：每个字段从"其对齐值倍数"的偏移开始，前一个字段结束后若下一个字段对齐值更大，就插入 padding；结构体总大小圆整到最大字段对齐值的倍数。以 `struct S1 { char a; int32_t b; char c; }` 为例（`_Alignof(int32_t)=4`）：

```text
struct S1 (arm64, _Alignof(int32_t)=4, sizeof=12)
偏移:  0  1  2  3  4  5  6  7  8  9 10 11
字段:  a  ■  ■  ■  b  b  b  b  c  ■  ■  ■
       │  └─ padding(3) ─┘  │        └─ 尾部圆整(3) ─┘
       │                    │
       └─ char 偏移 0       └─ int32_t 需 4 对齐 → 偏移 4
```

`S2`（字段重排：`int32_t b; char a; char c;`）则 `sizeof=8`——**大对齐字段提前，padding 减少**。这是"结构体字段排序影响内存占用"的全部秘密：不是玄学，是三个简单规则的组合。

### 4.3 未对齐访问为什么是 UB（ph10 衔接）

ph10 3.3 已定义"未对齐访问"这一类 UB：对 `int32_t` 指针做 `*p` 时，若地址不是 4 的倍数，行为未定义。本阶段从"解析器视角"重看：`memcpy(&local, wire, sizeof local)` 是安全的——`memcpy` 逐字节搬运不要求对齐，且编译器会把它优化成"若地址已对齐则单条加载，否则安全慢路径"（**零性能损失的便携写法**）；而 `struct S2 *p = (struct S2 *)wire; p->b` 是赌博：地址对齐就碰巧能跑，不对齐就是 UB，且换编译器行为还会变。**安全解析 = memcpy 到对齐的本地对象 / 或逐字段显式读取，二选一，绝不裸强转**。

### 4.4 字节序的硬件视角：寄存器里没有字节序

字节序只存在于"内存 ↔ 寄存器"的搬运瞬间：`uint32_t x = 0x01020304;` 后寄存器里 x 就是那个值，无论大小端；内存里怎么摆（`01 02 03 04` 还是 `04 03 02 01`）由平台 load/store 的字节通路决定。因此：**同一进程内交换数据（函数参数、struct 传值）永远没有字节序问题；跨进程/跨机器（文件、网络）才有**。网络字节序选大端是历史妥协（1980 年代的机器以"字序"通信，大端在按字节流处理时更自然），但今天唯一重要的是"**协议里写清楚用什么序，代码里显式转换**"——不写清楚字节序的协议就是没法互操作的协议（roadmap 必会概念"多字节字段必须明确字节序"）。

### 4.5 CRC 的数学原理：多项式除法与反射实现

CRC 把数据看作一个巨大二进制数，除以一个固定的**生成多项式**（CRC-32 用 `0x04C11DB7`），余数就是校验值——除法和普通整数除法不同，是**模 2 的多项式除法**（异或代替减法，不进位）。"反射"（reflected）实现把多项式按位翻转（`0xEDB88320`）并反向移位，是为了配合小端字节流逐字节处理，等价于标准定义。为什么比求和强：单 bit 翻转、突发错误（连续多位）在多项式除法下会产生确定性的非零余数，而求和/异或可能互相抵消（两个 bit 同时翻转时异或检不出来）。CRC-32 对长度 ≤ 32768 bit 的数据能检测全部 ≤ 3 位错误与所有奇数位错误——对"半写入、位翻转、截断"这类真实损坏模式足够可靠（roadmap 必会概念）。

## 5. 使用场景

| 场景 | 涉及知识点 |
|------|-----------|
| 数据库文件 / WAL 日志 | magic + 版本 + length-prefix record + CRC（3.6/3.8/3.10，project/ 完整落地） |
| 网络协议 frame | length-prefix frame 增量解析、网络字节序（3.2/3.7） |
| 跨平台序列化 | 显式字节序读写、varint（3.1/3.9），衔接 ph14 互操作 |
| 二进制文件格式解析 | 先校验长度再读字段、CRC 检损坏（3.6/3.8） |
| 嵌入式固件 / 驱动 | 寄存器位域访问、大小端转换（3.1/3.5） |
| 结构体内存优化 | offsetof/_Alignof 分析、字段重排省 padding（3.3/3.4） |

**不适合**此阶段的事项：

- mmap、Page Cache 与 fsync 刷盘边界（ph13 mmap、Page Cache 与可靠文件 IO 阶段（roadmap 第 13 节）：本阶段假设字节流已到手，ph13 回答"怎么可靠地落盘/刷盘"）
- 跨语言 ABI / FFI（ph14 C 与 C++ / Python / Rust 互操作阶段（roadmap 第 14 节，目录待建）：opaque pointer、导出符号）
- 存储引擎完整实现（ph16 数据库存储引擎基础阶段（roadmap 第 16 节，目录待建）：WAL 的崩溃恢复语义、MemTable、SSTable、LSM）
- 文本格式解析（CSV/JSON/INI 用文本解析，ph06 已示范 CSV 状态机，不需要字节序概念）
- 纯内存同进程数据交换（结构体传值无字节序问题，见 4.4；字节序只在跨进程/跨机器时才需要处理）

## 6. 代码示例

> 完整可运行文件在 [`examples/`](./examples/) 目录（编译/运行命令与验证状态见其 README）。本阶段示例均为**正常工程代码**，无故意出错演示，可任意编译运行；但请留意：示例演示的是"安全解析"模式，把字节流强转成结构体指针的坏写法只出现在文档讲解中、不落成可运行代码。以下所有实测输出来自 Apple clang 21.0.0（macOS arm64），编译命令 `cc -Wall -Wextra -std=c11` 零警告。

### 示例 1：大小端检测与显式字节序读写

对应 roadmap 学习内容"大端、小端"与练习"实现大端、小端转换函数"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex01-endian.c —— 大小端检测与显式字节序读写（安全示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int is_little_endian(void) {
    uint16_t x = 0x0102u;
    uint8_t b[2];
    memcpy(b, &x, sizeof x);      /* 位模式搬运（memcpy 可移植，union 是 C 扩展语义） */
    return b[0] == 0x02u;         /* 低地址字节是低位 → 小端 */
}

static uint16_t read_be16(const uint8_t *p) {
    return (uint16_t)(((uint16_t)p[0] << 8) | (uint16_t)p[1]);
}

static uint32_t read_be32(const uint8_t *p) {
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16) |
           ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex01-endian.c -o /tmp/ph12/ex01
# 2. 运行
/tmp/ph12/ex01
```

实测输出关键行（本机为小端）：

```text
编译期判定: 小端（__BYTE_ORDER__ 宏）
write_be32(0x01020304) 落线字节: 01 02 03 04
htonl(0x01020304) 首 4 字节: 01 02 03 04
ntohl(htonl(0x01020304)) = 0x01020304（往返不变）
```

解读：`write_be32` 写出的字节序列是**固定**的（大端，与平台无关）——这就是"显式读写是跨平台格式基石"的直观证据；`htonl` 在任意平台都产生网络序（大端）字节。练习 2 要求自己实现这一整套函数并验证往返。

### 示例 2：结构体对齐与 padding

对应 roadmap 学习内容"结构体对齐、padding"与"sizeof 与字段偏移"，衔接 ph09 的"上'线'要逐字段 memcpy"伏笔。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex02-align.c —— 结构体对齐、padding 与 sizeof/offsetof（安全示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
struct S1 {           /* 按声明顺序自然对齐 */
    char     a;       /* 偏移 0 */
    int32_t  b;       /* 需要 4 字节对齐 → 偏移 4（1~3 是 padding） */
    char     c;       /* 偏移 8 */
};                    /* 总大小 9 → 圆整到对齐值 4 的倍数 = 12 */

struct S2 {           /* 把 4 字节字段提前，padding 更少 */
    int32_t  b;       /* 偏移 0 */
    char     a;       /* 偏移 4 */
    char     c;       /* 偏移 5 */
};                    /* 总大小 6 → 圆整到 4 的倍数 = 8 */
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex02-align.c -o /tmp/ph12/ex02
# 2. 运行
/tmp/ph12/ex02
```

实测输出关键行：

```text
S1       sizeof=12 align=4  offsetof: a=0 b=4 c=8
S2       sizeof=8  align=4  offsetof: a=4 b=0 c=5
SP       sizeof=6  align=1  offsetof: a=0 b=1 c=5
Align16  sizeof=16 align=16  offsetof: a=0 b=8 c=0
memcpy 解析: b=0x44332211 a=0x55 c=0x66（b 的字节序随平台!）
```

解读：字段重排把 S1 的 12 字节压到 S2 的 8 字节；packed 只有 6 字节但是编译器扩展、不能当线上格式；`memcpy` 到对齐本地对象后 `b` 的值是**主机序**（小端 `0x44332211`）——这正说明"struct 视图 ≠ 线上字节序"，位级转换还得靠显式读写。

### 示例 3：位运算、掩码与移位

对应 roadmap 学习内容"位运算、掩码、移位"与 ph10 的"位运算字段一律用无符号类型"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex03-bits.c —— 位运算、掩码、移位与位域对比（安全示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static uint16_t pack_fields(unsigned type, unsigned len) {
    return (uint16_t)(((uint16_t)(type & 0x0Fu) << 12) | (uint16_t)(len & 0x0FFFu));
}

/* ---- 位域版（对照）：布局由编译器决定，跨平台不可移植 ---- */
struct BitFieldHeader {
    unsigned type : 4;
    unsigned len  : 12;
};
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex03-bits.c -o /tmp/ph12/ex03
# 2. 运行
/tmp/ph12/ex03
```

实测输出关键行：

```text
flags=0x85 → read=1 write=0 exec=1 owner=1
packed=0x3abc → type=3 len=2748
位域版: type=3 len=2748, sizeof=4（布局实现定义）
1u << 31 = 2147483648
0x80000000u >> 4 = 0x08000000（无符号右移是逻辑移位, 高位补 0）
```

解读：显式掩码 + 移位的打包/解包与位域版数值一致，但位域布局是实现定义的——协议格式用显式写法；`1u << 31` 合法（无符号回绕语义）而 `1 << 31` 是 UB（ph10 已讲），这正是"位运算用无符号"的落点。

### 示例 4：安全解析二进制 record（本阶段核心）

对应 roadmap 必会概念"**不要直接把不可信字节强转成结构体指针**"、学习内容"二进制 record 解析"与"checksum / CRC"、练习"解析固定格式二进制 record"。

> 运行前提：无（正常工程代码；该文件演示的是安全解析模式，可任意编译运行）。

```c
// examples/ex04-record.c —— 安全解析二进制 record（重点示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int record_parse(const uint8_t *buf, size_t avail, size_t off,
                        Record *out, size_t *consumed) {
    if (avail - off < REC_HEADER_SIZE)
        return PARSE_TRUNC;                       /* ① 头部长度先校验 */
    if (read_be32(buf + off) != REC_MAGIC)
        return PARSE_MAGIC;                       /* ② magic */
    if (read_be16(buf + off + 4) != REC_VERSION)
        return PARSE_VERSION;                     /* ③ 版本 */
    uint16_t type = read_be16(buf + off + 6);
    if (type != REC_TYPE_PUT && type != REC_TYPE_DEL)
        return PARSE_TYPE;                        /* ④ 类型 */
    uint32_t key_len = read_be32(buf + off + 8);
    uint32_t value_len = read_be32(buf + off + 12);
    /* ⑤ payload + CRC 的总长度先校验（uint64 防溢出） */
    if ((uint64_t)REC_HEADER_SIZE + key_len + value_len + REC_CRC_SIZE >
        avail - off)
        return PARSE_TRUNC;
    /* ⑥ checksum 覆盖 [0, 16+k+v) —— 头部字段 + key + value */
    size_t covered = REC_HEADER_SIZE + (size_t)key_len + value_len;
    if (crc32(buf + off, covered) != read_be32(buf + off + covered))
        return PARSE_CRC;
    out->type = type;
    out->key = buf + off + REC_HEADER_SIZE;
    out->key_len = key_len;
    out->value = buf + off + REC_HEADER_SIZE + key_len;
    out->value_len = value_len;
    *consumed = covered + REC_CRC_SIZE;
    return PARSE_OK;
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex04-record.c -o /tmp/ph12/ex04
# 2. 运行
/tmp/ph12/ex04
```

实测输出（尾部）：

```text
record 1: type=PUT key="name" value="mosslau" (key_len=4 value_len=7)
record 2: type=DEL key="old" value="" (key_len=3 value_len=0)
解析结果: 2 条 record 全部通过 (CRC 校验通过)
== 损坏 payload 一字节 ==
解析结果: PARSE_CRC —— checksum 不匹配, 检测到数据损坏
== 截断 record（payload 只到一半）==
解析结果: PARSE_TRUNC —— 剩余字节不足, 检测到截断
```

解读：record 布局是 roadmap 示例 `RecordHeader` 的完整版（magic + version + type + key_len + value_len + checksum），但**解析绝不强转结构体指针**——长度 → magic → 版本 → 类型 → payload 长度 → CRC 的顺序把"截断"与"损坏"精确区分开。练习 1 与练习 5 分别是这个模式的简化版与 WAL 版。

### 示例 5：length-prefix frame 增量解析

对应 roadmap 学习内容"length-prefix frame"与练习"实现 length-prefix frame 解析器"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex05-frame.c —— length-prefix frame 增量式流式解析（安全示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static int fr_feed(FrameReader *r, const uint8_t *data, size_t n,
                   uint8_t *out, size_t cap, size_t *out_len) {
    if (n > sizeof r->buf - r->len)
        n = sizeof r->buf - r->len;              /* 防内部溢出: 只收得下的部分 */
    if (n > 0) {
        memcpy(r->buf + r->len, data, n);
        r->len += n;
    }
    if (r->len >= 2) {                           /* 长度字段(大端)齐了 */
        uint16_t plen = (uint16_t)(((uint16_t)r->buf[0] << 8) | r->buf[1]);
        if (plen > FRAME_MAX_PAYLOAD)
            return -1;                           /* 长度超上限: 直接判非法 */
        r->need = (size_t)plen + 2;
        if (r->len >= r->need) {                 /* 整个 frame 齐了 */
            if (plen > cap) return -1;           /* 调用方缓冲太小 */
            memcpy(out, r->buf + 2, plen);
            *out_len = plen;
            memmove(r->buf, r->buf + r->need, r->len - r->need);
            r->len -= r->need;                   /* 消费掉, 窗口前移 */
            r->need = 0;
            return 1;
        }
    }
    return 0;
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex05-frame.c -o /tmp/ph12/ex05
# 2. 运行
/tmp/ph12/ex05
```

实测输出关键行（25 字节流按 5 字节一块喂入）：

```text
喂入 5 字节 → 完整 frame
  解出 frame: "hi" (2 字节)
喂入 5 字节 → 还差数据
...
截断场景: 喂 2 字节(长度=16) → 还差数据
超限场景: 长度=0xFFFF(>上限 4096) → 长度非法
```

解读：任意分块下 frame 都能正确拆出——"还差数据"不是错误，是增量解析的正常状态；EOF 时仍"还差数据"才判截断。练习 3 要求自己写这个状态机并换变长块验证。

### 示例 6：varint 编码与 magic/版本文件头

对应 roadmap 学习内容"varint 编码基础"与"文件格式版本号与 magic number"、练习"实现 varint 编码和解码"。

> 运行前提：无（正常工程代码，可任意编译运行）。

```c
// examples/ex06-varint.c —— varint 编码解码 + magic/版本号文件头（安全示例，已验证）
// 验证环境：Apple clang 21.0.0（cc，macOS arm64）—— 编译/运行命令见下方命令块
static size_t varint_encode(uint32_t v, uint8_t out[VARINT_MAX_BYTES]) {
    size_t n = 0;
    while (v >= 0x80u) {
        out[n++] = (uint8_t)(v & 0x7Fu) | 0x80u;   /* 续位标记 0x80 */
        v >>= 7;
    }
    out[n++] = (uint8_t)v;                          /* 末字节无续位标记 */
    return n;
}

static size_t varint_decode(const uint8_t *in, size_t avail, uint32_t *out) {
    uint32_t v = 0;
    size_t n = 0;
    while (n < avail && n < VARINT_MAX_BYTES) {
        v |= (uint32_t)(in[n] & 0x7Fu) << (7u * n);   /* 每字节 7 位 */
        if ((in[n] & 0x80u) == 0) {                   /* 无续位 → 结束 */
            *out = v;
            return n + 1;
        }
        n++;
    }
    return 0;   /* 截断或超 5 字节: 非法 */
}
```

```bash
# 1. 编译
cc -Wall -Wextra -std=c11 examples/ex06-varint.c -o /tmp/ph12/ex06
# 2. 运行
/tmp/ph12/ex06
```

实测输出关键行：

```text
varint(128       ) = 80 01  (2 字节) → 解码 128 (往返一致)
varint(16384     ) = 80 80 01  (3 字节) → 解码 16384 (往返一致)
varint(4294967295) = ff ff ff ff 0f  (5 字节) → 解码 4294967295 (往返一致)
解码 {0x80 0x80}: 非法(截断)
文件头: magic=0x4e563031 版本=1 记录数=300000 (8 字节头)
```

解读：128 之后每 7 位一个字节，`0xFFFFFFFF` 占满 5 字节；截断的 varint（全是续位）被拒——解码与帧解析共享同一条纪律"读取之前先检查"。文件头示例把 magic + 版本 + varint 三个机制串成一个最小可演进格式。

## 7. 总结

### 关键要点

1. **不要直接把不可信字节强转成结构体指针**（roadmap 必会概念）：字节序、padding、对齐三重风险；安全解析 = 长度先校验 + 逐字段显式读取（3.6）
2. **多字节字段必须明确字节序**（roadmap 必会概念）：显式 `read_be32`/`write_be32` 落线格式与平台无关；`htonl` 是 POSIX 便捷方式，网络序 = 大端（3.1/3.2）
3. **多数二进制解析应先检查长度再读取字段**（roadmap 必会概念）：头部长度 → magic → 版本 → 类型 → payload 长度 → checksum，顺序固定（3.6/3.7）
4. **对齐不一致会导致性能问题，甚至触发未定义行为**（roadmap 必会概念）：struct padding 是编译器排的；packed 是扩展不能当格式；`memcpy` 到对齐本地对象是零性能损失的便携做法（3.3/4.2/4.3）
5. **二进制格式要考虑版本兼容和损坏检测**（roadmap 必会概念）：magic + 版本 + reserved + checksum 四件套（3.10）
6. **checksum 能帮助发现半写入、截断和数据损坏**（roadmap 必会概念）：CRC-32 覆盖区间要连续且不含校验字段自身——校验放尾部；错误码区分"截断/损坏/非本格式"（3.8）
7. **位运算一律用无符号类型**（ph10 衔接）：掩码 + 移位是打包字段的唯一可移植写法，位域布局实现定义、协议禁用（3.5）
8. **length-prefix frame 天然支持分块与截断识别**：增量状态机三态（完整/还差/非法），长度上限必须先判（3.7）
9. **varint 是紧凑且字节序无关的整数编码**：7 位一组 + 续位标记，解码必须查截断与超长（3.9）
10. **字段重排省 padding**：大对齐字段提前，S1(12 字节) → S2(8 字节)（3.3/3.4）

### 跨语言对比：二进制数据读写

| 维度 | C | C++ | Go | Python | Rust |
|------|---|-----|----|--------|------|
| 显式字节序 | 手写 read_be32（本阶段） | 手写或 endian 库 | `encoding/binary`（BigEndian/LittleEndian） | `struct.unpack('>I', ...)` | `byteorder` / `from_be_bytes` |
| 结构体对齐 | 编译器自然对齐 + offsetof | 同 C，可 `#pragma pack` | 对齐由编译器决定，`unsafe` 可查 | 无（纯对象） | `#[repr(C)]` / `#[repr(packed)]` |
| 位域/位操作 | 位域实现定义，用掩码 | 同 C | 位运算直接支持 | `int` 无限长，移位随意 | 类型安全位运算 |
| 解析不可信数据 | 手写长度+CRC 校验 | 手写或解析框架 | `encoding/binary` + 手动检查 | `struct` 需自己处理截断 | `bytes` 切片 + 检查，安全默认 |

C 是所有语言里最"裸露"的：**没有内建的字节序抽象、没有运行时边界检查**——但这也正是它被选作存储引擎与协议实现语言的原因：布局完全可控、零开销（ph11 的"质量保险"补上安全）。Go 的 `encoding/binary`、Python 的 `struct`、Rust 的 `byteorder` 把"显式字节序读写"包装成库函数，但底层原理与 C 的 `read_be32` 完全一致（为 analysis/ 与 Tenet 合成积累素材）。

### 阶段验收清单

- [ ] 能解释结构体 padding：`sizeof(struct S1) == 12` 是怎么算出来的（自然对齐 + 填充 + 圆整，示例 2）
- [ ] 能安全解析长度可变 record：先校验长度再逐字段读取、错误码区分截断与损坏（示例 4，练习 1/5）
- [ ] 能避免字节序导致的跨平台错误：显式读写/`htonl` 明确字节序，任何平台读同一字节流结果一致（示例 1，练习 2）
- [ ] 能识别截断、长度不足和 checksum 错误：length-prefix frame 的"还差数据"与 CRC 失败各有明确信号（示例 5，project/）
- [ ] 能设计一个可演进的二进制文件头：magic + 版本 + reserved + checksum，旧程序读新文件安全拒绝（示例 6，project/）

### 动手练习

本阶段练习见 [`exercises/`](./exercises/)（题目在 exercises/README.md，参考实现 sol-* 先别看）。五题与 roadmap ph12「练习」一一对应：

- 解析固定格式二进制 record（★）
- 实现大端、小端转换函数（★）
- 实现 length-prefix frame 解析器（★★）
- 实现 varint 编码和解码（★★）
- 为 WAL record 设计 header 和 checksum（★★★）

完成 5 题后继续。

### 阶段项目

本阶段综合项目见 [`project/`](./project/)：**WAL record 解析器**——对应 roadmap 推荐项目「WAL record 解析器」，一个带 magic + 版本 + length-prefix + CRC32 的 WAL 文件工具（`make` 构建 / `make test` 自测 / `make demo` 演示损坏拦截），把"先校验长度再读字段、绝不强转结构体指针、magic/版本/checksum 格式契约"三条核心纪律落地成可运行代码。roadmap 的另三个推荐项目：「length-prefix frame parser」由示例 5 与练习 3 覆盖，「二进制数据文件解析库」由示例 4 与 project/ 的 `wal.c` 接口示范，「SSTable block header parser」同构于本项目的 record 头解析（换字段即可）。建议完成练习后再动手。

- [ ] 完成 exercises/ 全部练习并对照参考实现复盘
- [ ] 独立完成 project/ 并通过其验收标准（`make test` 退出码 0、`make demo` 演示 CRC 拦截、`make clean` 零残留）

### 下一阶段

[mmap、Page Cache 与可靠文件 IO 阶段](../ph13-mmap-page-cache/13-mmap-page-cache.md) — 本阶段解决了"字节怎么排、怎么安全解析"，下一阶段解决"怎么可靠地落盘与刷盘"：fsync/fdatasync 的刷盘边界、mmap 与 read/write 的取舍、Page Cache 对性能与基准测试的影响、崩溃恢复中的半写入处理——本阶段 project/ 的 WAL 工具正是 ph13 讲"append-only 落盘 + 崩溃恢复"时的现成载体；两者组合即存储引擎的 IO 底座，ph16 数据库存储引擎基础阶段的 WAL replay 将直接复用本阶段的 record 格式。
