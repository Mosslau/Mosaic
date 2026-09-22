# ph03 函数与模块化 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Python 3.13.12。每题都是「模块 + 主程序」的多文件结构，用子目录 `sol-0N-*/` 组织。

## 练习 1：数学工具模块（★）

**目标**：把数学函数拆分到独立模块，编写入口脚本调用。

**要求**：
- 新建 `math_tools.py`，实现 `is_prime(n)`（质数判断）、`factorial(n)`（阶乘）、`fibonacci(n)`（返回第 n 项，约定 F(0)=0、F(1)=1）
- 新建 `main.py`，`import math_tools` 并打印调用结果
- `main.py` 加 `if __name__ == "__main__"` 守卫，直接运行才执行打印

**验收**：
- `is_prime(7)` → `True`；`is_prime(10)` → `False`
- `factorial(5)` → `120`
- `fibonacci(10)` → `55`
- 直接运行 `python3 main.py` 输出与上面一致

## 练习 2：字符串工具模块（★★）

**目标**：实现字符串处理函数，支持命令行调用。

**要求**：
- 新建 `string_tools.py`，实现 `reverse(text)`、`char_stats(text)`（返回总字符/字母/数字/空格统计）、`to_upper(text)`、`to_lower(text)`
- 新建 `cli.py`，用 `sys.argv` 解析子命令，把命令名映射到 `string_tools` 里的函数
- 支持 `-h`/`--help` 显示用法；未知命令提示可用命令

**验收**：
- `python3 cli.py reverse "hello"` → `olleh`
- `python3 cli.py upper "hello"` → `HELLO`
- `python3 cli.py stats "abc 123"` 输出字母 3、数字 3、空格 1

## 练习 3：文件处理模块（★★）

**目标**：用函数封装文件读写，模块可导入也可直接运行。

**要求**：
- 新建 `file_tools.py`，实现 `read_lines(path)`（返回去掉换行符的行列表）、`write_lines(path, lines)`（每行追加换行符写入）、`count_words(path)`（按空白切分统计词数）、`count_lines(path)`
- 新建 `main.py`，读取一个文本文件并打印行数、词数
- `file_tools.py` 加 `if __name__ == "__main__"`：直接运行时对命令行传入的文件路径做统计

**验收**：
- 对内容为 `hello world\nfoo bar\n` 的文件，`count_lines` → 2，`count_words` → 4
- `read_lines(path)` 返回 `["hello world", "foo bar"]`
- `python3 main.py <文件路径>` 能正确打印统计信息

## 练习 4：拆分通讯录程序（★★★）

**目标**：把 ph02 的通讯录功能拆分为「数据操作模块 + UI 入口脚本」。

**要求**：
- 新建 `contacts.py`：只含数据操作，不写 `print`/`input`；实现 `add_contact(contacts, name, phone)`、`find_contact(contacts, name)`（未找到返回 `None`）、`delete_contact(contacts, name)`（返回是否删除成功）、`list_contacts(contacts)`（返回按姓名排序的 `(name, phone)` 列表）
- 新建 `main.py`：UI 入口脚本，负责交互循环（`add`/`find`/`delete`/`list`/`quit` 命令），调用 `contacts.py` 的函数
- 模块与入口职责分离：数据逻辑在 `contacts.py`，交互在 `main.py`

**验收**：
- `add_contact` 添加后 `find_contact` 能查到，`delete_contact` 删除后 `find_contact` 返回 `None`
- `list_contacts` 返回按姓名排序的结果
- `python3 main.py` 交互命令（或 `--demo` 演示）行为正确
