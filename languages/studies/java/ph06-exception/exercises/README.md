# ph06 异常处理 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.16。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同，如 `sol-01-safe-division.java` 的类名是 `SafeDivisionSol`），编译用文件名、运行用类名，如 `javac sol-01-safe-division.java` + `java SafeDivisionSol`。

## 练习 1：安全除法（★）

**目标**：用 `try/catch ArithmeticException` 捕获除零，验证「异常路径不崩溃 + 返回兜底值」。
**要求**：
- 实现 `safeDivide(int a, int b)`：除零时返回兜底值 0 并打印原因；正常除法返回商
- 重载 `safeDivide(int a, int b, int fallback)`：允许调用方自定义兜底值
- 实现 `parseAndDivide(String aStr, String bStr)`：把字符串解析为整数再相除，`NumberFormatException` 与 `ArithmeticException` 都单独捕获并打印原因，失败返回 0
- 在注释里说明：为什么 `10 / 0` 抛 `ArithmeticException` 而不是返回某种特殊值
**验收**：`10 / 2` 输出 5；`10 / 0` 输出兜底值并打印原因；`parseAndDivide("abc", "2")` 打印非法数字格式原因并返回 0；程序运行结束无未捕获异常。

## 练习 2：文件读取异常（★★）

**目标**：用 try-with-resources 读取文件并统计行数，区分「文件不存在」与「读取中途失败」。
**要求**：
- 实现 `countLines(String path)`：用 `BufferedReader` 逐行读取，返回行数
- **必须用 try-with-resources**，不允许出现手动 `close()`
- 文件不存在时打印原因并返回 -1；读取中途失败打印原因并返回 -2；正常返回行数
- 单独捕获 `FileNotFoundException` 与 `IOException`（多 catch），并在注释里解释为什么前者必须写在前面
- main 中先用 `FileWriter` 生成一个 3 行测试文件再读取；再读一个不存在的文件
**验收**：3 行测试文件返回 3；不存在文件返回 -1 且程序不崩溃；源码中无手动 `close()`；能对照主文档 3.5 节说明 try-with-resources 相比 finally 的优势。

## 练习 3：登录异常（★★）

**目标**：自定义业务异常携带错误码 + 账户锁定状态，与 `IllegalArgumentException` 区分。
**要求**：
- 定义 `LoginError` 枚举（如 `WRONG_PASSWORD`、`ACCOUNT_LOCKED`）与 `LoginException`（携带错误码与 message）
- `LoginService.login(username, password)`：用户名/密码为空抛 `IllegalArgumentException`；凭据错误抛 `LoginException(WRONG_PASSWORD)`；连续 3 次错误后锁定账户，之后任何尝试（含正确密码）抛 `LoginException(ACCOUNT_LOCKED)`
- 锁定状态在 Service 实例内维护；登录成功后重置失败计数
- 业务异常与参数异常在 main 中**分开 catch**，打印不同前缀
**验收**：连续 3 次错误密码后正确密码也登录失败（账户锁定）；锁定信息含错误码；空用户名抛 `IllegalArgumentException` 而非 `LoginException`。

## 练习 4：参数校验异常（★★★）

**目标**：实现 `requireXxx` 风格校验工具，在方法入口最前完成防御性校验（fail fast）。
**要求**：
- 实现校验工具类 `Validator`：`requireNonEmpty(String, field)`、`requireNotNull(Object, field)`、`requirePositive(int/double, field)`、`requireInRange(int, min, max, field)`——全部抛 `IllegalArgumentException` 且消息含字段名
- 用校验工具实现 `OrderService.createOrder(String buyerName, int itemCount, double pricePerItem)`：买家姓名非空、商品数量在 [1, 100]、单价为正
- 校验放在方法**第一行开始**（任何业务逻辑之前）
- 在注释里说明：为什么参数校验用 unchecked `IllegalArgumentException` 而不是 checked 异常
**验收**：空买家、数量 101、单价 0 三种非法入参分别抛 `IllegalArgumentException` 且消息含字段名；合法入参（张三、3、9.9）返回订单创建成功。

> **提示**：练习 1/2/3 与主文档第 6 章示例 1/2/4 主题一致，练习 4 的 `requireXxx` 风格来自主文档 4.3 节「边界转换」提到的校验思路——先独立完成，再对照 `examples/` 检查。`sol-*` 为参考实现（头注释已注明），做完再看。
