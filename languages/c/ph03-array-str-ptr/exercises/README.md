# ph03 数组、字符串、指针 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：Apple clang 17.0.0（gcc 兼容），标准 C99。编译统一加 `-Wall -Wextra -std=c99`。

## 练习 1：手写 strlen（★）

**目标**：理解字符串以 `\0` 结尾，用指针遍历求长度。
**要求**：实现 `size_t my_strlen(const char *s)`，不准用 `strlen`；用指针（不用下标）遍历。
**验收**：`my_strlen("hello")` 返回 5；`my_strlen("")` 返回 0。

## 练习 2：手写 strcpy（★★）

**目标**：理解字符串复制与 `\0` 的传递。
**要求**：实现 `char *my_strcpy(char *dst, const char *src)`，把 `\0` 一并复制，返回 `dst`；不准用 `strcpy`。
**验收**：复制后 `dst` 内容与 `src` 完全一致（含 `\0`）；用 `printf("%s", dst)` 能正确打印。

## 练习 3：手写 strcmp（★★）

**目标**：理解字典序比较与无符号字符比较。
**要求**：实现 `int my_strcmp(const char *s1, const char *s2)`，返回值的正负号与 `strcmp` 一致；比较时把字符转成 `unsigned char`（避免高位字符符号问题）；不准用 `strcmp`。
**验收**：`my_strcmp("abc","abc")==0`；`my_strcmp("abc","abd")<0`；`my_strcmp("xyz","abc")>0`。

## 练习 4：数组反转、字符串反转、查找子串（★★★）

**目标**：用双指针技巧处理反转，用朴素匹配查找子串。
**要求**：实现三个函数——`reverse_array(int *arr, size_t n)`、`reverse_string(char *s)`、`my_strstr(const char *str, const char *sub)`；`my_strstr` 找不到返回 `NULL`，找到返回子串首次出现位置的指针；空子串返回 `str`。
**验收**：`{1,2,3,4,5,6}` 反转后为 `6 5 4 3 2 1`；`"pointer"` 反转后为 `"retniop"`；在 `"hello world"` 中找 `"world"` 返回偏移 6 的位置。
