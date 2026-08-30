# ph02 函数与模块化 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17.0.0（gcc 兼容），标准 C99。编译统一加 `-Wall -Wextra -std=c99`。

## 练习 1：字符串工具库（★★）

**目标**：实现一组字符串处理函数。
**要求**：实现 `my_strlen`（求长度）、`my_strcpy`（复制）、`my_strcmp`（比较）三个函数，不准调用 `<string.h>` 里的 `strlen`/`strcpy`/`strcmp`；用 `main` 演示三个函数的效果。
**验收**：`my_strlen("hello")` 返回 5；`my_strcpy` 后目标字符串与源相同；`my_strcmp("abc","abc")` 返回 0、`my_strcmp("abc","abd")` 返回非 0。

## 练习 2：数组排序工具库（★★）

**目标**：把排序算法封装成可复用函数。
**要求**：实现 `bubble_sort(int arr[], int n)` 和 `select_sort(int arr[], int n)` 两个函数；在 `main` 中对同一数组分别调用并打印排序结果。
**验收**：对 `{5, 2, 8, 1, 9}` 排序后输出 `1 2 5 8 9`。

## 练习 3：递归阶乘与斐波那契（★★）

**目标**：用递归实现阶乘与斐波那契数列。
**要求**：分别写 `factorial` 和 `fib` 函数；处理负数输入（阶乘返回 -1 或报错）；在 `main` 中读入 n 并输出两个结果。
**验收**：输入 `5` 输出 `5! = 120` 和 `fib(5) = 5`。

## 练习 4：把单文件程序拆成多个 .c/.h（★★★）

**目标**：把一个单文件计算器程序拆成多文件项目。
**要求**：拆成 `calculator.h`（函数声明 + include guard）、`calculator.c`（函数实现）、`main.c`（入口）；用一条 gcc 命令编译三个文件。
**验收**：`gcc -Wall -Wextra -std=c99 main.c calculator.c -o calc` 编译零警告，运行后 `add(3, 4)` 输出 7。
