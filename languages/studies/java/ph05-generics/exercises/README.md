# ph05 泛型 练习

> 先自己做，再对照 sol-* 参考实现。每题标注难度（★~★★★）。
> 验证环境：OpenJDK 17.0.16。参考实现均用非 public 类（文件名 `sol-0X-*.java` 与类名不同，如 `sol-01-generic-box.java` 的类名是 `GenericBoxSol`），编译用文件名、运行用类名，如 `javac sol-01-generic-box.java` + `java GenericBoxSol`。

## 练习 1：泛型 Box（★）

**目标**：写单类型参数泛型类，掌握 `set/get` 与编译期类型安全，验证运行期类型擦除。
**要求**：
- 实现 `Box<T>`：`set` / `get` / `isEmpty` / `clear`（值置 null）/ `getOrElse(T fallback)`（空盒返回兜底值）
- main 中分别用 `Box<String>` 装字符串、`Box<Integer>` 装整数并打印
- 验证类型擦除：打印 `strBox.getClass() == intBox.getClass()`
- 验证空盒行为：`clear()` 后 `isEmpty()` 为 true、`getOrElse` 返回兜底值
- 在注释里说明"往 `Box<String>` 里 `set(42)` 为什么编译不通过"
**验收**：依次输出两个盒的值、「运行时 Class 相同: true」、clear 后 isEmpty=true、getOrElse 返回兜底值。

## 练习 2：泛型 Pair（★★）

**目标**：双类型参数 `K/V` + 泛型静态工厂方法 + 不可变更新，理解泛型方法调用时的类型推断。
**要求**：
- 实现 `Pair<K, V>`：`getKey` / `getValue` / `setValue` / `toString`（格式 `(key, value)`）
- 新增**泛型静态工厂** `static <K, V> Pair<K, V> of(K key, V value)`，main 里用 `Pair.of("Alice", 90)` 创建 Pair——不许写 `new Pair<...>(...)`
- 新增 `withValue(V newValue)`：返回改了 value 的**新** Pair，原 Pair 保持不变
- 实现泛型方法 `swapValues(Pair<?, V> a, Pair<?, V> b)` 交换两个 Pair 的 value
**验收**：`Pair.of("Alice", 90)` 打印 `(Alice, 90)`；withValue 后原对象仍 `(Alice, 90)`、新对象为 `(Alice, 95)`；swap 后 `a=(B, banana), b=(A, apple)`。

## 练习 3：泛型 Stack（★★★）

**目标**：用 `Object[]` 规避「不能 new T[]」限制，实现自动扩容与防泄漏出栈；写有界泛型方法。
**要求**：
- `Stack<T>` 内部存储用 `Object[]`（禁止用 `T[]` 强转数组）；初始容量 2，压满自动翻倍扩容
- `push` / `pop` / `peek` / `size` / `isEmpty`；`pop` 出栈后置空槽位（防内存泄漏）；空栈 `pop`/`peek` 抛 `IllegalStateException`
- `pop`/`peek` 返回处用 `@SuppressWarnings("unchecked")` 强转
- 写有界泛型方法 `static <T extends Number> double sum(Stack<T> stack)`：弹空并累加 `doubleValue()`
- main 验证：初始容量 2 压入 5 个元素不失败；`Stack<Integer>` 压 1..4 后 `sum` 得 10.0
**验收**：扩容后 size=5；LIFO 出栈顺序正确；`sum` 输出 `10.0`；空栈 pop 抛异常。

## 练习 4：泛型 Repository（★★★）

**目标**：泛型接口 + 泛型抽象基类 + 两个实体绑定具体类型，验证「一次定义、任意实体复用」。
**要求**：
- 泛型接口 `Repository<T, ID>`：`save(T)` / `findById(ID)` 返回 `Optional<T>` / `findAll()` / `deleteById(ID)` / `count()`——主键类型也泛型化，比固定 String 更通用
- 泛型抽象基类 `AbstractRepository<T, ID>`：用 `Map<ID, T>` 实现全部 CRUD；定义抽象方法 `idOf(T entity)` 让子类给出主键
- 两个实现类：`UserRepository`（实体 `User`，主键 String）与 `DeviceRepository`（实体 `Device`，主键 String）
- main 中分别增删查两类实体，验证两个仓库互不干扰
**验收**：User 仓库 save 两个、删除一个后 `count()` 为 1、`findById` 被删者为 empty；Device 仓库独立 save/查询命中；两仓库各自维护自己的数据。

> **提示**：练习 1~4 与主文档第 6 章示例 1~4 主题一致——先独立完成，再对照 `examples/` 中的示例检查。`sol-*` 为参考实现（头注释已注明），做完再看。
