# 01 · RAII 资源管理

> demo: `make && ./demos/01_raii`

## 1. 设计动机

C 语言里每份资源（`malloc` 的内存、`fopen` 的文件、`lock` 的互斥量）都要手动释放，
漏一条路径就泄漏或死锁。C++ 的命题：**让资源的生命周期绑定对象的生命周期——
对象构造时获取资源，对象析构时自动释放，无论从哪条路径离开作用域**。

## 2. 机制拆解

RAII（Resource Acquisition Is Initialization）：资源获取即初始化。

```cpp
class File {
    FILE* f_;
public:
    explicit File(const char* path) { f_ = std::fopen(path, "r"); }  // 获取
    ~File() { if (f_) std::fclose(f_); }                             // 释放
    // ...
};

void process() {
    File f("data.txt");   // 构造：打开文件
    if (条件) return;      // 提前返回——析构依然会执行！
    // ... 正常路径
}                          // 作用域结束：f 析构，文件自动关闭
```

**关键**：析构函数在**任何**离开作用域的路径上都会执行（正常结束、`return`、
抛出异常），所以资源绝不会漏释放。现代 C++ 用 `unique_ptr`/`shared_ptr`/`lock_guard`
把 RAII 泛化到所有资源。

## 3. 代码验证（demos/01_raii.cpp）

demo 演示：自定义 RAII 守卫（作用域结束时自动打印"释放"）、`unique_ptr` 自动管理内存、
`lock_guard` 自动解锁。

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 拷贝语义陷阱 | 浅拷贝导致 double-free（需要正确实现拷贝/移动） |
| 析构时机隐式 | 依赖作用域规则，初学者容易困惑 |
| 异常安全 | 析构里抛异常是灾难（必须 noexcept） |

**换来的**：C 时代 90% 的资源泄漏/死锁 bug 消失；`unique_ptr` 让"谁拥有"显式化。

## 5. 对 Tenet 的启示

- ✅ **吸收"资源生命周期绑定作用域"**：Tenet 解释器的环境（Env）用 `Rc`/引用计数
  管理——作用域结束自动回收，正是 RAII 思想的运行时版本
- ✅ **吸收"谁拥有谁负责"**：Tenet 的值都是值语义（int/float/bool/string 拷贝），
  没有裸指针，不存在 double-free 问题域
- ❌ **拒绝把析构/所有权语法引入语言**：教学语言不需要 `unique_ptr` 级别的表达力；
  "值语义 + 引用计数"是最小实现
- 💡 若未来加 struct，可参照 RAII 设计"对象离开作用域自动清理"的语义

**一句话**：C++ 用「析构函数」把资源管理自动化；Tenet 用「值语义 + 引用计数」
在最小形态下拿到同样的安全性。
