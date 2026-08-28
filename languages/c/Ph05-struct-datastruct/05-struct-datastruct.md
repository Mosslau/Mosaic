# C 语言结构体与数据结构阶段

> Ph03 讲完了指针"指到哪"，Ph04 讲完了 malloc/free "从哪来"——本阶段将两者合体：**用指针 + 堆内存构建真正的动态数据结构**，是 C 语言从基础语法走向工程实践的里程碑。

## 1. 概述

结构体与数据结构阶段是 C 学习路线中"终于能写真正的数据结构"的节点。目标：**掌握 struct/union/enum 的定义与使用，理解结构体内存布局，能用指针+堆内存实现链表、栈、队列并正确处理生命周期**。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 聚合类型 | struct、typedef、嵌套结构体、结构体数组 |
| 成员访问 | `.` 访问栈对象成员、`->` 通过指针间接访问 |
| 特殊类型 | enum（替代魔术数字）、union（节省内存）、位域（压缩标志位） |
| 内存布局 | 对齐规则、padding、`offsetof`、`#pragma pack` |
| 数据结构 | 单链表（核心）、栈（数组实现+链表实现对比）、队列、哈希表（链地址法） |
| 生命周期 | init → 操作 → destroy 三段式接口设计 |

本阶段直接承接 Ph03+Ph04：Ph03 的指针操作对象从 `int` 变成 `struct Node`，Ph04 的 malloc/free 用来在堆上创建/销毁节点。链表节点的 `next` 指针就是 Ph03 的核心遗产——**指针指向同类型的下一个节点**，这是所有链式结构的基础。

## 2. 来源与演变

| 阶段 | 来源 | 关键演变 |
|------|------|---------|
| Algol 68（1968） | 引入记录类型 | 首次将异构字段组合为一个类型 |
| B 语言（1969） | 无 struct | 用 word 数组 + 偏移量模拟异构数据 |
| K&R C（1978） | struct 定型 | `struct tag { ... }` 语法，支持成员访问和取地址 |
| C89/C90 | 标准化 | 结构体赋值、作为函数参数/返回值、`offsetof` 宏 |
| C99 | 复合字面量 | `(struct Point){1, 2}` 匿名临时对象 |
| C11 | 匿名 struct/union | 嵌套时可省略成员名，直接访问内部字段 |

**struct 的本意不是封装而是布局**：C 的 struct 纯粹描述内存中一组字段的排列——没有访问控制、没有方法、没有继承。C++ 的 class 从此演化，加入了 private/public、成员函数和虚函数表——方向的差异决定了两者各自的设计哲学。

**`->` 运算符的由来**：早期 `*p.x` 因 `.` 优先级高于 `*` 导致 `*(p.x)` 的歧义，Ritchie 于是引入 `p->x` 作为 `(*p).x` 的语法糖——把解引用和成员访问合为一步。

## 3. 语法与参数

### 3.1 struct 定义、typedef 与 `->` / `.` 访问

```c
#include <stdio.h>
#include <stdlib.h>

/* 标签式：每次使用都要写 struct 关键字（自引用时不可省略） */
struct Point { int x; int y; };

/* typedef 别名：省略 struct 关键字，C 中惯用 */
typedef struct { int id; int speed; } Motor;

int main(void) {
    struct Point p1 = {10, 20};       /* . 访问栈对象 */
    Motor m1 = {1, 500};

    Motor *ptr = malloc(sizeof(Motor)); /* -> 通过指针访问堆对象 */
    if (ptr == NULL) return 1;
    ptr->id = 2;    /* 等价于 (*ptr).id */
    ptr->speed = 300;

    printf("Point: (%d,%d)  Motor1: id=%d  Motor2: id=%d,speed=%d\n",
           p1.x, p1.y, m1.id, ptr->id, ptr->speed);
    free(ptr);
    return 0;
}
```

| 操作符 | 左侧类型 | 等价写法 | 场景 |
|--------|---------|---------|------|
| `.` | 结构体（值） | — | 栈对象、函数值参数 |
| `->` | 结构体指针 | `(*ptr).member` | 堆对象、函数指针参数 |

记忆：**点访问对象，箭头穿指针**。

### 3.2 结构体数组、嵌套、自引用

```c
typedef struct { int day, month, year; } Date;
typedef struct {
    char name[32];
    Date birthday;          /* 嵌套结构体（值语义） */
} Person;

/* 结构体数组 */
Person team[2] = {{"Alice", {15, 3, 1999}}, {"Bob", {22, 7, 2001}}};

/* 自引用结构 —— 链表的基石 */
typedef struct Node {
    int          data;
    struct Node *next;      /* 必须用 struct Node，typedef 未完成 */
} Node;
```

| 模式 | 说明 |
|------|------|
| 嵌套（值） | 子结构体内联在父结构体中，连续内存 |
| 嵌套（指针） | 仅存指针，子结构体在堆上独立分配，需管理生命周期 |
| 自引用 | 只能通过指针（`struct Node *`），否则 sizeof 无限递归 |

### 3.3 enum — 替代魔术数字

```c
typedef enum {
    STATUS_IDLE, STATUS_RUNNING, STATUS_STOPPED, STATUS_ERROR, STATUS_COUNT
} MotorStatus;

typedef struct { int id; MotorStatus status; } Motor;

/* 用法：类型明确，比 int 更能表达意图 */
Motor m = {1, STATUS_IDLE};
switch (m.status) {
case STATUS_IDLE:    /* ... */ break;
case STATUS_RUNNING: /* ... */ break;
case STATUS_STOPPED: /* ... */ break;
case STATUS_ERROR:   /* ... */ break;
}
```

| 对比 | `#define` | `enum` |
|------|----------|--------|
| 作用域 | 全局无约束 | 受类型名约束 |
| 调试 | 丢失名称 | 调试器可显示枚举名 |
| 自增 | 不支持 | 未赋值成员自动 +1 |

### 3.4 union — 同一块内存存不同类型

```c
#include <stdio.h>

typedef union { int i; float f; char bytes[4]; } Value;

int main(void) {
    Value v;
    v.i = 0x41424344;
    printf("int: 0x%08X  bytes: %c%c%c%c  sizeof=%zu\n",
           v.i, v.bytes[0], v.bytes[1], v.bytes[2], v.bytes[3], sizeof(v));
    /* -> int: 0x41424344  bytes: DCBA  sizeof=4  (小端机器) */
    return 0;
}
```

**经典用法**：带 tag 的 union（tagged union）——在 struct 中放一个 enum 标记当前活跃成员：

```c
typedef enum { KIND_INT, KIND_FLOAT } ValKind;
typedef struct {
    ValKind kind;
    union { int i; float f; };  /* C11 匿名 union，直接访问 .i .f */
} TaggedValue;
```

### 3.5 位域 — 按 bit 压缩标志位

```c
typedef struct {
    unsigned int enabled   : 1;
    unsigned int direction : 1;   /* 0=正转 1=反转 */
    unsigned int fault     : 1;
    unsigned int reserved  : 5;
} MotorFlags;   /* sizeof(MotorFlags) = 4，但只用 8 bit */
```

| 限制 | 说明 |
|------|------|
| 不可取地址 | `&mf.enabled` 编译错误——位域不是独立字节 |
| 跨平台不可靠 | 位排列顺序由编译器决定，不可用于可移植序列化 |
| 适用场景 | 寄存器标志位、协议头紧凑字段、节约嵌入式内存 |

## 4. 底层原理

### 4.1 结构体内存布局与对齐

```text
struct Example {
    char  a;   // 偏移 0，占 1 字节
    // padding: 3 字节（让 int b 对齐到 4 的倍数）
    int   b;   // 偏移 4，占 4 字节
    char  c;   // 偏移 8，占 1 字节
    // padding: 3 字节（整体大小对齐到最大对齐值 4）
};
// sizeof = 12，远大于成员之和 6
```

**对齐规则**：成员偏移量必须能被其对齐值整除（对齐值 = `min(sizeof(成员), 平台默认)`）；整体大小必须能被最大对齐值整除。

```c
#include <stddef.h>
#include <stdio.h>

typedef struct { char a; int b; char c; } Example;

int main(void) {
    printf("sizeof=%zu  offsetof a=%zu b=%zu c=%zu\n",
           sizeof(Example),
           offsetof(Example, a),   /* 0 */
           offsetof(Example, b),   /* 4 (不是 1!) */
           offsetof(Example, c));  /* 8 */
    return 0;
}
```

**节约 padding**：按对齐值从大到小排列成员——`int b; char a; char c;` 只需 8 字节（减少 33%）。`#pragma pack(1)` 强制 1 字节对齐，但未对齐访问在 ARM/SPARC 上触发 bus error，在 x86 上也拖慢性能。

### 4.2 链表节点在堆上的布局

```text
               head (栈上指针)
                ↓
┌─────────┐   ┌─────────┐   ┌─────────┐
│ data:10 │   │ data:20 │   │ data:30 │
│ next ───┼──>│ next ───┼──>│ next ───┼──> NULL
└─────────┘   └─────────┘   └─────────┘
  malloc(1)     malloc(2)     malloc(3)
```

栈上只有一个 head 指针（8 字节），所有节点散落在堆上、通过 next 指针串联。释放时必须逐节点遍历——`free(head)` 只释放第一个节点，其余全部泄漏。

## 5. 使用场景

| 场景 | 用什么 | 理由 |
|------|:------:|------|
| 不同类型字段组合为一个实体 | struct | 聚合异构数据 |
| 链表/树/图节点 | struct + 自引用指针 | 动态链接，运行期增长 |
| 互斥类型（int/float/str 三选一） | union + tag enum | 节省内存，tag 保证类型安全 |
| 状态码、错误码、模式选择 | enum | 编译期检查，可读性好 |
| 寄存器/协议头中的紧凑标志位 | 位域 | 按 bit 压缩，语义清晰 |

## 6. 代码示例

### 示例 1：单链表（增删查改 + 完整生命周期）

```c
#include <stdio.h>
#include <stdlib.h>

typedef struct Node {
    int          data;
    struct Node *next;
} Node;

Node *node_create(int data) {
    Node *n = malloc(sizeof(Node));
    if (n == NULL) return NULL;
    n->data = data;
    n->next = NULL;
    return n;
}

void list_insert_head(Node **head, int data) {
    Node *n = node_create(data);
    if (n == NULL) return;
    n->next = *head;
    *head = n;
}

void list_insert_tail(Node **head, int data) {
    Node *n = node_create(data);
    if (n == NULL) return;
    if (*head == NULL) { *head = n; return; }
    Node *cur = *head;
    while (cur->next != NULL) cur = cur->next;
    cur->next = n;
}

int list_delete(Node **head, int data) {
    Node *cur = *head, *prev = NULL;
    while (cur != NULL && cur->data != data) {
        prev = cur; cur = cur->next;
    }
    if (cur == NULL) return 0;
    if (prev == NULL) *head = cur->next;   /* 删除头节点 */
    else              prev->next = cur->next;
    free(cur);
    return 1;
}

Node *list_find(Node *head, int data) {
    for (Node *cur = head; cur != NULL; cur = cur->next)
        if (cur->data == data) return cur;
    return NULL;
}

void list_print(Node *head) {
    for (Node *cur = head; cur != NULL; cur = cur->next)
        printf("%d%s", cur->data, cur->next ? " -> " : "");
    printf("\n");
}

void list_destroy(Node **head) {
    Node *cur = *head;
    while (cur != NULL) {
        Node *tmp = cur;
        cur = cur->next;
        free(tmp);
    }
    *head = NULL;
}

int main(void) {
    Node *head = NULL;
    list_insert_head(&head, 30); list_insert_head(&head, 20);
    list_insert_head(&head, 10);
    printf("头插 10,20,30: "); list_print(head);

    list_insert_tail(&head, 40);
    printf("尾插 40:       "); list_print(head);

    list_delete(&head, 20);
    printf("删除 20:       "); list_print(head);

    printf("查找 30:       %s\n", list_find(head, 30) ? "找到" : "未找到");

    list_destroy(&head);
    printf("销毁后: head=%p\n", (void *)head);
    return 0;
}
```

**设计要点**：`Node **head` 二级指针——插入/删除可能修改头指针本身，`Node *` 只能修改节点内容；`list_destroy` 最后置 NULL 防悬空；`node_create` 的 NULL 向上传播，调用链沿途静默失败（生产代码应返回错误码）。

### 示例 2：数组栈 + 括号匹配

```c
#include <stdio.h>

#define STACK_MAX 256

typedef struct { char data[STACK_MAX]; int top; } Stack;

void stack_init(Stack *s)      { s->top = -1; }
int  stack_is_empty(Stack *s)  { return s->top == -1; }
int  stack_is_full(Stack *s)   { return s->top == STACK_MAX - 1; }

int stack_push(Stack *s, char c) {
    if (stack_is_full(s)) return -1;
    s->data[++(s->top)] = c;
    return 0;
}

int stack_pop(Stack *s, char *out) {
    if (stack_is_empty(s)) return -1;
    *out = s->data[(s->top)--];
    return 0;
}

/* 括号匹配：返回 1 匹配，0 不匹配 */
int brackets_match(const char *expr) {
    Stack s;
    stack_init(&s);
    for (const char *p = expr; *p != '\0'; p++) {
        switch (*p) {
        case '(': case '[': case '{':
            if (stack_push(&s, *p) != 0) return 0;
            break;
        case ')': case ']': case '}': {
            char open;
            if (stack_pop(&s, &open) != 0) return 0;
            if ((*p == ')' && open != '(') ||
                (*p == ']' && open != '[') ||
                (*p == '}' && open != '{')) return 0;
            break;
        }
        }
    }
    return stack_is_empty(&s);
}

int main(void) {
    const char *tests[] = {"()", "([]){}", "([)]", "((())", "(]"};
    int         expected[] = {1, 1, 0, 0, 0};
    for (int i = 0; i < 5; i++)
        printf("\"%s\"  ->  %s  (预期 %s)\n",
               tests[i],
               brackets_match(tests[i]) ? "匹配" : "不匹配",
               expected[i]         ? "匹配" : "不匹配");
    return 0;
}
```

数组栈 vs 链表栈：数组栈容量固定、无 malloc 开销、缓存友好；链表栈（push = 头插）无容量上限但每次 push 有 malloc 开销。括号匹配场景输入长度可预测，选数组栈。

### 示例 3：链表队列 — 任务调度

```c
#include <stdio.h>
#include <stdlib.h>

typedef struct QNode { int data; struct QNode *next; } QNode;

typedef struct { QNode *head, *tail; int size; } Queue;

void queue_init(Queue *q) { q->head = q->tail = NULL; q->size = 0; }

int queue_enqueue(Queue *q, int data) {
    QNode *n = malloc(sizeof(QNode));
    if (n == NULL) return -1;
    n->data = data; n->next = NULL;
    if (q->tail == NULL) q->head = q->tail = n;
    else { q->tail->next = n; q->tail = n; }
    q->size++;
    return 0;
}

int queue_dequeue(Queue *q, int *out) {
    if (q->head == NULL) return -1;
    QNode *tmp = q->head;
    *out = tmp->data;
    q->head = q->head->next;
    if (q->head == NULL) q->tail = NULL;
    free(tmp);
    q->size--;
    return 0;
}

void queue_destroy(Queue *q) {
    while (q->head != NULL) {
        QNode *tmp = q->head;
        q->head = q->head->next;
        free(tmp);
    }
    q->tail = NULL; q->size = 0;
}

int main(void) {
    Queue q; queue_init(&q);
    printf("入队: T0 T1 T2 T3 T4\n");
    for (int i = 0; i < 5; i++) queue_enqueue(&q, i);
    printf("出队: ");
    int task;
    while (queue_dequeue(&q, &task) == 0) printf("T%d ", task);
    printf("\n队列空: %s\n", q.head == NULL ? "是" : "否");
    queue_destroy(&q);
    return 0;
}
```

**关键**：维护 `head`+`tail` 双指针是 O(1) 入队的前提；`dequeue` 队列变空时同步置 `tail=NULL`，否则后续 `enqueue` 误判非空。

### 示例 4：哈希表 — 词频统计（链地址法）

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HT_SIZE 101

typedef struct HTNode { char *key; int count; struct HTNode *next; } HTNode;
typedef struct { HTNode *buckets[HT_SIZE]; } HashTable;

static unsigned int ht_hash(const char *key) {
    unsigned int hash = 5381;
    int c;
    while ((c = *key++)) hash = ((hash << 5) + hash) + (unsigned int)c;
    return hash % HT_SIZE;
}

void ht_init(HashTable *ht) {
    for (int i = 0; i < HT_SIZE; i++) ht->buckets[i] = NULL;
}

void ht_inc(HashTable *ht, const char *key) {
    unsigned int idx = ht_hash(key);
    for (HTNode *cur = ht->buckets[idx]; cur != NULL; cur = cur->next)
        if (strcmp(cur->key, key) == 0) { cur->count++; return; }
    HTNode *n = malloc(sizeof(HTNode));
    if (n == NULL) return;
    n->key = malloc(strlen(key) + 1);
    if (n->key == NULL) { free(n); return; }
    strcpy(n->key, key);
    n->count = 1;
    n->next = ht->buckets[idx];
    ht->buckets[idx] = n;
}

void ht_print(HashTable *ht) {
    for (int i = 0; i < HT_SIZE; i++)
        for (HTNode *cur = ht->buckets[i]; cur != NULL; cur = cur->next)
            printf("  \"%s\": %d\n", cur->key, cur->count);
}

void ht_destroy(HashTable *ht) {
    for (int i = 0; i < HT_SIZE; i++) {
        HTNode *cur = ht->buckets[i];
        while (cur != NULL) {
            HTNode *tmp = cur; cur = cur->next;
            free(tmp->key); free(tmp);
        }
        ht->buckets[i] = NULL;
    }
}

int main(void) {
    HashTable ht; ht_init(&ht);
    const char *words[] = {
        "hello","world","hello","c","world","hello",
        "data","c","struct","data","data", NULL};
    for (int i = 0; words[i] != NULL; i++) ht_inc(&ht, words[i]);
    printf("词频统计:\n"); ht_print(&ht);
    ht_destroy(&ht);
    return 0;
}
```

**所有权**：哈希表存储动态分配 key（`malloc+strcpy`），不依赖调用者字符串生命周期。销毁时先 `free(tmp->key)` 再 `free(tmp)`。

## 7. 总结

### 关键要点

1. **`.` vs `->`**：点访问值本身，箭头通过指针间接访问——`p->x` 即 `(*p).x`
2. **自引用必须用标签**：`struct Node *next` 不能写成 `Node *next`（typedef 未完成）
3. **init/destroy 成对**：每个含堆内存的结构体应提供 `xxx_init`/`xxx_destroy`
4. **二级指针修改头指针**：链表插入/删除传 `Node **head`，否则无法更新 `head` 本身
5. **对齐影响 sizeof**：成员排列顺序决定 padding——大到小排列减少浪费
6. **union 需配 tag**：union 不记录当前活跃成员，用外部 enum 标记
7. **位域不可取地址**：仅在内存受限或寄存器映射场景使用

### 跨语言对比：struct / class 语义

| 特性 | C struct | C++ struct | Go struct | Rust struct | Java class |
|------|----------|-----------|-----------|-------------|------------|
| 成员函数 | 无 | 有 | 有（方法） | 有（impl） | 有 |
| 访问控制 | 无 | public 默认 | 首字母大小写 | 默认 private | 四档修饰符 |
| 继承 | 无 | 有 | 无（嵌入） | 无（trait） | 有 |
| 堆/栈分配 | 两者均可 | 两者均可 | 两者均可 | 两者均可 | 仅堆（new） |
| 生命周期管理 | 手动 | RAII | GC | Drop（编译期） | GC |
| 内存布局控制 | 精确 | 精确（有虚表除外） | 不保证 | `#[repr(C)]` | 不保证 |

C struct 的本质是**精确控制内存布局的聚合类型**——没有语法糖，每字节 padding 可用 `offsetof` 验证。其他语言的 struct/class 在此基础上叠加了方法、封装、继承和自动生命周期管理。

### 阶段验收标准

- 能解释 `.` 和 `->` 的区别，知道何时用哪个
- 能为结构体设计 `init`/`destroy` 函数，处理内部堆内存的申请与释放
- 能用 `offsetof` 和 `sizeof` 验证布局，解释 padding 产生的原因
- 能实现单链表（增删查改+完整释放），用二级指针正确修改头节点
- 能用数组栈解决括号匹配，能用链表队列实现 FIFO 调度
- 能说明 union/位域的使用场景和限制

### 推荐项目

- **学生管理系统**（链表实现）：增删查改 + 按成绩排序
- **数组栈**：括号匹配、表达式求值（中缀转后缀）
- **任务调度队列**：模拟 FIFO 处理，打印入队/出队时间戳
- **词频统计器**（哈希表）：读取文本统计单词出现次数

### 下一阶段

**文件操作阶段**（Ph06-file-io，文档规划中）— `fopen/fclose/fread/fwrite`、文本/二进制文件读写、`fseek/ftell`、CSV 解析、append-only log。
