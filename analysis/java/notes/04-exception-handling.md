# 04 · 受检异常：错误处理的一场设计赌注

> demo: `java demos/04_exception_handling.java`

## 1. 设计动机

C 的错误是返回码（忘查就吞掉），C++ 的异常是非受检的（抛不抛、抛什么全靠文档）。
Java 的赌注：**让编译器强制处理可预见的错误**——把异常分成**受检（checked）**与
**不受检（unchecked）**两类：`IOException`/`SQLException` 这类"方法签名的承诺会失败"
的异常，**不 catch 或不声明就编译不过**；`NullPointerException`/`ArithmeticException`
这类"程序员的错"则运行时才抛。这是语言史上最激进也最富争议的错误处理设计：
一半人认为它逼出了健壮代码，一半人认为它毁掉了 API 设计。

## 2. 机制拆解

```java
void readConfig() throws IOException {   // 声明：我可能抛受检异常
    Files.readAllLines(Path.of("app.conf"));  // 调用受检 API → 必须处理或上抛
}

// 调用方三选一：catch（就地处理）
try {
    readConfig();
} catch (IOException e) {
    System.err.println("配置读取失败：" + e.getMessage());
    // 恢复或降级
}

// 或：上抛（把责任交给上层）
void load() throws IOException { readConfig(); }
```

**异常表（exception table）**：编译后的字节码为每个 try 块生成一张表
（起始 PC、结束 PC、handler PC、异常类型），异常抛出时 JVM 查表决定跳转——
这是"结构化异常"的实现底座，也意味着 try 块内无异常时零开销。

**受检异常的代价在 API 设计层**：方法签名里的 `throws` 是"公开承诺"，
改异常类型会破坏所有调用方 → 驱动了两个反模式：
- **吞异常**：`catch (Exception e) { }` 空 catch——编译器逼你处理，你就假装处理；
- **异常泛滥**：底层每个方法都 `throws Exception`，受检形同虚设。
Spring 等框架选择全面转向**不受检异常**（`DataAccessException` 包装），
等于承认这场赌注在企业实践里部分落败。

## 3. 代码验证（demos/04_exception_handling.java）

demo 演示：① 受检 vs 不受检——把 `readConfig` 的 `throws IOException` 删掉会编译失败
（注释里给出报错）；② 异常表生效——`try` 中段抛异常，`finally` 仍执行、异常正确传播；
③ 吞异常反模式与 Spring 式包装（把受检包成不受检）的对照。

```bash
java demos/04_exception_handling.java
```

## 4. 代价与取舍

| 代价 | 说明 |
|------|------|
| 吞异常反模式 | 编译器逼你处理 → 空 catch/`throws Exception` 泛滥，比没检查更糟 |
| API 设计被绑架 | `throws` 是公开契约，改异常=破坏兼容；新增受检异常阻力巨大 |
| 隐式控制流 | 异常仍是非局部跳转——`catch` 到的可能来自调用栈深处 |
| 性能（有争议） | 异常**抛出**路径慢（构建栈迹）；无异常路径在现代 JVM 零开销 |
| 学习曲线 | 初学者先学"怎么让编译器闭嘴"，而非"怎么设计错误" |

**换来的**：受检异常确实拦住了"文件没关/网络失败没处理"这类真实失误——
Java IO 代码极少出现 C 式"忘查返回值"；异常对象携带完整**栈迹**（call stack），
排障信息远超错误码。它是"让错误可见"的一次真诚但代价高昂的尝试。

## 5. 对 Tenet 的启示

- ❌ **拒绝异常 try/catch**（架构文档拒绝清单已记，来源含 Java）：Java 的实践给出
  三重证据——隐式控制流、吞异常反模式、API 契约被 `throws` 绑架。
  Tenet 选 `Result + ?`（Rust 路线）：错误是**返回值**，路径显式、可穷举、可组合
- ✅ **吸收"错误要携带上下文"**：Java 异常的栈迹/消息是排障利器——Tenet 的 `Result`
  若带错误信息，应支持 `?` 自动附加"在哪一层失败"的上下文（类似 Rust `anyhow` 的
  `.context()` 思想）
- ✅ **吸收"资源自动关闭"的运行时支持**：Java `try-with-resources`（自动调用 close）
  证明"编译器帮你收尾"是可行的——Tenet 的引用计数天然做到内存回收，
  未来有 IO 资源时值得设计对称的"作用域结束自动 close"（呼应 01 号笔记的 💡）
- 💡 Java 的教训：**编译器强制 ≠ 好设计**——强制处理可预见错误的方向是对的，
  但要用"返回值穷举"（Result）而非"异常声明"（throws）来实现

**一句话**：Java 把"你必须处理错误"写进类型系统（受检异常），
诚意可嘉但把 API 设计拖进泥潭；Tenet 用 `Result + ?` 拿到同样的保证，
且不引入隐式控制流。
