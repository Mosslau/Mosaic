# ph01 基础语法 示例

> 每个示例是主文档 `01-basic-syntax.md` 第 6 章对应示例的完整可运行版。验证环境：rustc 1.92.0，单文件直接用 `rustc` 编译，无需 cargo。

| 文件 | 说明 | 编译 | 运行 |
|------|------|------|------|
| ex01-guessing-game.rs | 猜数字游戏：固定答案，match 比较大小 | `rustc ex01-guessing-game.rs -o ex01` | `./ex01` |
| ex02-temperature-converter.rs | 温度转换器：摄氏/华氏互转，match 选方向 | `rustc ex02-temperature-converter.rs -o ex02` | `./ex02` |
| ex03-multiplication-table.rs | 九九乘法表：嵌套 for + 格式化输出 | `rustc ex03-multiplication-table.rs -o ex03` | `./ex03` |
| ex04-is-prime.rs | 素数判断：while 试除到 √n | `rustc ex04-is-prime.rs -o ex04` | `./ex04` |

全部已在本环境编译运行验证（`rustc` 零警告）。ex01 为交互程序，可管道喂入测试：`echo 42 | ./ex01`。
