# ph02 所有权 示例

> 每个示例是主文档 `02-ownership.md` 第 6 章对应示例的完整可运行版。验证环境：rustc 1.92.0，单文件直接用 `rustc` 编译，无需 cargo。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-move-copy-clone.rs | move、Copy 与 Clone 三种赋值行为对比 | `rustc ex01-move-copy-clone.rs -o ex01` | `./ex01` |
| ex02-borrow-choice.rs | 函数传参三选：`&str` / `&mut String` / `String` | `rustc ex02-borrow-choice.rs -o ex02` | `./ex02` |
| ex03-string-str-slice.rs | `String`、`&str`、`&[T]` 的转换与切片求和 | `rustc ex03-string-str-slice.rs -o ex03` | `./ex03` |
| ex04-mut-borrow-nll.rs | 可变借用与 NLL：引用活到最后一次使用 | `rustc ex04-mut-borrow-nll.rs -o ex04` | `./ex04` |
| ex05-text-stats.rs | 文本统计器：行数/单词数/最长单词，全程零 clone | `rustc ex05-text-stats.rs -o ex05` | `./ex05`（EOF 结束输入） |

全部已在本环境用 `rustc 1.92.0` 编译运行验证（零警告）。ex05 为读取 stdin 的程序，可管道喂入测试：`printf 'hello world\nrust ownership\n' | ./ex05`。
