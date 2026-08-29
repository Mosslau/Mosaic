# Java 泛型阶段

> 面向企业级后端、微服务和车联网数据平台，理解编译期类型安全机制与运行期类型擦除，掌握泛型类/方法/接口的设计能力。

## 1. 概述

Java 泛型阶段的目标是：**揭开 ph04 中 `List<String>` 和 `Map<String, Integer>` 背后的泛型机制**——让类、接口和方法在定义时不绑定具体类型，由编译器在使用时强制类型检查。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 泛型定义 | 泛型类 `Box<T>`、泛型方法 `<T> void sort`、泛型接口 `Comparable<T>` |
| 类型擦除 | 编译后泛型信息被擦除，`List<String>` 和 `List<Integer>` 运行时是同一个 Class |
| 通配符 | `?` 无界通配符、`? extends T` 上界（生产者）、`? super T` 下界（消费者） |
| PECS 原则 | Producer Extends, Consumer Super —— 决定何时用 extends 何时用 super |
| 限制与陷阱 | 不能 `new T()`、不能 `instanceof T`、不能创建泛型数组、原始类型警告 |

本阶段不涉及注解处理、反射泛型 API 和 Kotlin/Scala 的类型系统。

## 2. 来源与演变

Java 泛型是在「编译期类型安全」与「向后兼容」之间权衡的结果——选择了类型擦除方案：

- **Java 1.0 ~ 1.4（1995-2002）— 无泛型**：集合元素类型为 `Object`，取出时必须强制转换。一旦误存错误类型，`ClassCastException` 在运行时才暴露。
- **Java 5（2004）— 泛型引入**：集合框架全面泛型化，采用**类型擦除**（erasure）而非 C# 的运行期泛型——泛型信息仅存在于编译期，编译后 `<String>` 被擦除为 `Object`。代价是运行期拿不到类型参数，收益是旧 JVM 可运行新代码。
- **Java 7（2011）— 钻石语法**：`new ArrayList<>()` 省略右侧泛型参数，编译器从左侧推断。
- **Java 8/10（2014/2018）— 推断增强**：Lambda/Stream 的类型推断更智能，`var list = new ArrayList<String>()` 推导为 `ArrayList<String>`。

## 3. 语法与参数

### 3.1 泛型类

类名后声明类型参数，实例化时绑定具体类型。类型参数命名约定：`T`（Type）、`E`（Element）、`K/V`（Key/Value）、`R`（Return）、`S/U/V`（第二第三类型参数）。

```java
public class Box<T> {
    private T value;

    public void set(T value) { this.value = value; }
    public T get() { return value; }

    public static void main(String[] args) {
        Box<String> strBox = new Box<>();   // T 绑定为 String
        Box<Integer> intBox = new Box<>();  // T 绑定为 Integer
        System.out.println("OK");
    }
}
```

`Box<String>` 和 `Box<Integer>` 是同一个 `Box.class` 的不同参数化类型——这是与 C++ 模板单态化的根本区别。

### 3.2 泛型方法

类型参数写在返回值之前：`<T> 返回类型 方法名(参数)`。调用时编译器从实参推断 `T`，泛型方法可与泛型类独立——一个普通类中也可定义泛型静态方法。

```java
public static <T> T firstOrNull(List<T> list) {
    return list.isEmpty() ? null : list.get(0);
}
// 编译器从实参 List<String> 推断 T=String
String first = firstOrNull(Arrays.asList("a", "b"));
```

### 3.3 泛型接口

接口定义时声明类型参数，实现类可绑定具体类型或保持泛型：

```java
// 泛型接口
interface Comparable<T> {
    int compareTo(T o);
}

// 实现时绑定具体类型
class User implements Comparable<User> {
    public int compareTo(User other) { return this.name.compareTo(other.name); }
}

// 实现类也保持泛型
class Node<T> implements Comparable<Node<T>> {
    T data;
    public int compareTo(Node<T> other) { /* ... */ }
}
```

ph04 集合框架中的 `Comparable<T>`、`Iterable<T>`、`List<T>`、`Map<K,V>` 全部遵循此模式。

### 3.4 类型参数边界

用 `extends` 限定类型参数上界——`T` 必须是给定类或接口的子类型。注意泛型 `extends` 同时表示类继承和接口实现。

```java
class NumericBox<T extends Number> {
    private T value;
    public double doubleValue() { return value.doubleValue(); }
}

NumericBox<Integer> ok  = new NumericBox<>();  // OK
NumericBox<Double>  ok2 = new NumericBox<>();  // OK
// NumericBox<String> err;                       // 编译错误
```

多重边界用 `&` 连接：`<T extends Comparable<T> & Serializable>`——先类后接口，最多一个类。

### 3.5 通配符 `?`：无界、上界 extends、下界 super

通配符用于**方法参数**中表达「不关心具体类型」的意图，不能用于类定义或实例化：

| 通配符 | 语义 | 能读吗 | 能写吗 | 典型场景 |
|--------|------|--------|--------|---------|
| `?` | 未知类型 | 读为 Object | 不能写（除 null） | 不关心元素类型的通用操作 |
| `? extends T` | T 或其子类 | 读为 T | 不能写 | 从集合中**取**数据（生产者） |
| `? super T` | T 或其父类 | 读为 Object | 可以写入 T | 向集合中**放**数据（消费者） |

```java
// ? extends T：读安全，写不安全
void printNumbers(List<? extends Number> list) {
    for (Number n : list) System.out.println(n);  // 读 OK
    // list.add(42);  // 编译错误：可能是 List<Double>
}

// ? super T：写安全，读受限（只能保证读到 Object）
void addIntegers(List<? super Integer> list) {
    list.add(1); list.add(2);                   // 写 OK
    Object obj = list.get(0);                   // 读 OK（Object）
    // Integer x = list.get(0);                 // 编译错误
}
```

### 3.6 PECS 原则：Producer Extends, Consumer Super

Joshua Bloch 在《Effective Java》中提出的最高原则：

| 角色 | 操作 | 通配符 | 为什么 |
|------|------|--------|--------|
| Producer（生产者） | 从结构中**读取**数据 | `? extends T` | 读出来的至少是 T，可以安全消费 |
| Consumer（消费者） | 向结构中**写入**数据 | `? super T` | 写入 T 对容器是安全的（容器接受 T 或其父类） |
| 既读又写 | 修改已有元素 | 不用通配符，直接用 `<T>` | 读和写需要同一具体类型 |
| 既不读也不写 | 仅遍历/contains/size | `?` 无界 | 不关心元素类型 |

`Collections.copy(List<? super T> dest, List<? extends T> src)` 是 PECS 的经典范例——dest 是消费者用 super，src 是生产者用 extends。

### 3.7 原始类型（Raw Type）

不带类型参数的泛型类称为原始类型——仅在向后兼容 Java 1.4 代码时使用，**新代码中不应出现**：

```java
List list = new ArrayList();     // 原始类型：绕过泛型检查
list.add("hello");
list.add(123);                   // 编译不报错，运行才崩溃
String s = (String) list.get(1); // ClassCastException

// 正确写法
List<String> list2 = new ArrayList<>();
list2.add("hello");
// list2.add(123);               // 编译期直接拒绝
```

编译器会为原始类型产生 `unchecked` 警告。`@SuppressWarnings("unchecked")` 仅在确认安全的强制转换处使用，且注解范围尽可能小。

## 4. 底层原理

### 4.1 类型擦除机制

Java 泛型通过**编译期类型擦除**实现——泛型信息仅在编译阶段存在，编译后的字节码中不包含类型参数。擦除规则：

1. **无界类型参数** `<T>` → 擦除为 `Object`：`Box<T>` 编译后 `value` 字段类型为 `Object`
2. **有界类型参数** `<T extends Number>` → 擦除为边界类型 `Number`：`NumericBox<T>` 编译后 `value` 字段类型为 `Number`
3. **方法中的类型参数** → 擦除为边界类型或 `Object`

```java
// 源码
class Box<T> { private T value; public T get() { return value; } }

// 反编译（javap -c）后等价于
class Box { private Object value; public Object get() { return value; } }
```

编译器在**调用方**自动插入强制转换（checkcast 字节码指令）：`Box<String> b = new Box<>(); b.set("hi"); String s = b.get();` 编译后等价于 `Box b = new Box(); b.set("hi"); String s = (String) b.get();`——checkcast 由编译器生成。

这就是 `List<String>` 和 `List<Integer>` 运行时 `getClass()` 返回同一个 `ArrayList.class` 的原因——泛型信息被擦除了。

### 4.2 类型擦除的四大限制

| 限制 | 原因 | 典型编译错误 | 标准规避方式 |
|------|------|-------------|-------------|
| 不能 `new T()` | 运行时不知道 T 是什么类 | `error: type parameter T cannot be instantiated directly` | 传入 `Class<T>` 或 `Supplier<T>` |
| 不能 `instanceof T` | 运行时泛型信息不存在 | `error: illegal generic type for instanceof` | 用 `instanceof` 擦除后的类型（如 Object） |
| 不能创建泛型数组 `new T[n]` | 数组在运行时持有具体类型 | `error: generic array creation` | 创建 `Object[]` 后强转 `(T[])` |
| 不能 `static` 字段使用类型参数 | 静态字段在类级别共享 | `error: non-static type variable T cannot be referenced from a static context` | 用泛型方法替代 |

规避手法：`Class<T>` 反射代替 `new T()`；`Object[]` + `(T[])` 强转代替 `new T[n]`（见示例 3）；`instanceof` 擦除后类型代替 `instanceof T`。

### 4.3 桥接方法（Bridge Method）

子类指定父类泛型接口的具体类型参数后，编译器生成桥接方法保证多态：

```java
class Node<T> {
    private T data;
    public void setData(T data) { this.data = data; }
}

class StringNode extends Node<String> {
    @Override
    public void setData(String data) { super.setData(data); }
}
```

类型擦除后 `Node.setData(Object)` 和 `StringNode.setData(String)` 签名不同。编译器生成桥接方法 `StringNode.setData(Object)` { `this.setData((String) arg);` }，确保通过 `Node` 引用调用时多态正确。

## 5. 使用场景

| 场景 | 推荐方案 | 理由 |
|------|---------|------|
| 泛型工具类（容器/缓存） | 泛型类 `<T>` | 类型安全，一次定义多类型复用 |
| 算法排序/查找 | 泛型方法 `<T extends Comparable<T>>` | 对可比较类型通用 |
| 只遍历不修改集合 | `? extends T` | 明确只读意图，类型安全 |
| 只向集合添加元素 | `? super T` | 接受 T 可存入的任何父类容器 |
| 复制/转换集合元素 | PECS：src 用 extends，dest 用 super | `Collections.copy` 的经典设计 |
| 通用仓库/DAO | 泛型接口 `Repository<T>` | 对每个实体类型复写 CRUD 签名 |
| 结果封装（成/败） | `Result<T>` | 消除 null 返回和异常过抛 |
| 泛型工厂方法 | `<T> T create(Class<T> clazz)` | 创建时无需强转 |

常见反模式：原始类型混用（heap pollution）；试图将 `List<String>` 赋给 `List<Object>`（泛型不协变）；在不需要类型参数的纯静态工具中加泛型。

## 6. 代码示例

### 示例 1：泛型 Box

```java
public class GenericBox {
    static class Box<T> {
        private T value;

        public void set(T value) { this.value = value; }
        public T get() { return value; }
        public boolean isEmpty() { return value == null; }
    }

    public static void main(String[] args) {
        Box<String> strBox = new Box<>();
        strBox.set("Hello Generics");
        System.out.println("strBox: " + strBox.get());

        Box<Integer> intBox = new Box<>();
        intBox.set(42);
        System.out.println("intBox: " + intBox.get());

        // Box<String> 和 Box<Integer> 运行时是同一个 Class
        System.out.println("运行时 Class 相同: " +
                (strBox.getClass() == intBox.getClass()));
    }
}
```

### 示例 2：泛型 Pair

```java
public class GenericPair {
    static class Pair<K, V> {
        private K key;
        private V value;

        public Pair(K key, V value) { this.key = key; this.value = value; }
        public K getKey() { return key; }
        public V getValue() { return value; }
        public void setValue(V value) { this.value = value; }

        @Override
        public String toString() { return "(" + key + ", " + value + ")"; }
    }

    // 泛型方法：交换两个 Pair 的值（不关心 key 类型）
    static <V> void swapValues(Pair<?, V> a, Pair<?, V> b) {
        V temp = a.getValue();
        a.setValue(b.getValue());
        b.setValue(temp);
    }

    public static void main(String[] args) {
        Pair<String, Integer> score = new Pair<>("Alice", 90);
        System.out.println("成绩: " + score);

        Pair<String, String> a = new Pair<>("A", "apple");
        Pair<String, String> b = new Pair<>("B", "banana");
        swapValues(a, b);
        System.out.println("交换后: a=" + a + ", b=" + b);
    }
}
```

### 示例 3：泛型 Stack

```java
public class GenericStack {
    static class Stack<T> {
        private Object[] elements = new Object[16];  // 不能 new T[]
        private int size = 0;

        public void push(T item) { elements[size++] = item; }

        @SuppressWarnings("unchecked")
        public T pop() {
            T item = (T) elements[--size];  // 类型擦除后的必要强转
            elements[size] = null;          // 避免内存泄漏
            return item;
        }

        @SuppressWarnings("unchecked")
        public T peek() { return (T) elements[size - 1]; }

        public boolean isEmpty() { return size == 0; }
        public int size() { return size; }
    }

    public static void main(String[] args) {
        Stack<String> stack = new Stack<>();
        stack.push("请求1-登录");
        stack.push("请求2-查询");
        stack.push("请求3-更新");

        System.out.println("栈顶: " + stack.peek());
        while (!stack.isEmpty()) {
            System.out.println("处理: " + stack.pop());
        }
    }
}
```

### 示例 4：泛型 Repository

```java
import java.util.*;

public class GenericRepository {
    // 泛型接口：定义数据访问契约
    interface Repository<T> {
        void save(T entity);
        Optional<T> findById(String id);
        List<T> findAll();
        void deleteById(String id);
    }

    static class User { String id, name;
        User(String i, String n) { id = i; name = n; }
        public String toString() { return "User{id=" + id + ", name=" + name + "}"; }
    }

    // 实现时绑定具体类型
    static class UserRepository implements Repository<User> {
        private final Map<String, User> store = new HashMap<>();
        public void save(User u) { store.put(u.id, u); }
        public Optional<User> findById(String id) { return Optional.ofNullable(store.get(id)); }
        public List<User> findAll() { return new ArrayList<>(store.values()); }
        public void deleteById(String id) { store.remove(id); }
    }

    public static void main(String[] args) {
        Repository<User> repo = new UserRepository();
        repo.save(new User("u1", "Alice"));
        repo.save(new User("u2", "Bob"));
        System.out.println("全部用户: " + repo.findAll());
        System.out.println("查找 u2: " + repo.findById("u2").orElse(null));
        repo.deleteById("u1");
        System.out.println("删除后: " + repo.findAll());
    }
}
```

### 示例 5：PECS 演示

```java
import java.util.*;

public class PecsDemo {
    // Producer Extends: src 只读（生产者）
    static double sumOfList(List<? extends Number> list) {
        double sum = 0.0;
        for (Number n : list) sum += n.doubleValue();
        return sum;
    }

    // Consumer Super: dest 只写（消费者）
    static void addNumbers(List<? super Integer> list) {
        for (int i = 1; i <= 3; i++) list.add(i);
    }

    // PECS 组合：src 是生产者(extends)，dest 是消费者(super)
    static <T> void copyAll(List<? extends T> src, List<? super T> dest) {
        for (T item : src) dest.add(item);
    }

    public static void main(String[] args) {
        // ? extends T：可接收多种子类型
        System.out.println("sum(ints): " + sumOfList(Arrays.asList(1, 2, 3)));
        System.out.println("sum(doubles): " + sumOfList(Arrays.asList(1.5, 2.5, 3.5)));

        // ? super T：可写入多种父类容器
        List<Number> numbers = new ArrayList<>();
        addNumbers(numbers);
        System.out.println("addNumbers: " + numbers);

        // PECS 组合
        List<Integer> src = Arrays.asList(10, 20, 30);
        List<Number> dest = new ArrayList<>();
        copyAll(src, dest);
        System.out.println("copyAll: " + dest);
    }
}
```

### 示例 6：泛型 Result 封装

```java
import java.util.function.Function;

public class ResultDemo {
    static class Result<T> {
        private final T data;
        private final String error;

        private Result(T d, String e) { data = d; error = e; }
        public static <T> Result<T> success(T data) { return new Result<>(data, null); }
        public static <T> Result<T> failure(String error) { return new Result<>(null, error); }
        public boolean isSuccess() { return error == null; }
        public T getData() {
            if (error != null) throw new IllegalStateException("失败: " + error);
            return data;
        }

        public <U> Result<U> map(Function<T, U> f) {
            return isSuccess() ? success(f.apply(data)) : failure(error);
        }
        public String toString() { return isSuccess() ? "Success(" + data + ")" : "Failure(" + error + ")"; }
    }

    static Result<String> getDeviceStatus(String id) {
        if (id == null || id.isEmpty()) return Result.failure("设备ID不能为空");
        if (id.startsWith("err")) return Result.failure("设备不存在: " + id);
        return Result.success("在线");
    }

    public static void main(String[] args) {
        System.out.println("device-001: " + getDeviceStatus("device-001"));
        System.out.println("err-device: " + getDeviceStatus("err-device"));
        System.out.println("空ID:     " + getDeviceStatus(""));
        System.out.println("map 后:   " + getDeviceStatus("device-001").map(String::length));
    }
}
```

## 7. 总结

### 关键要点

1. **泛型 = 编译期类型安全**——编译器阻止 `List<String>` 中放入 `Integer`，消除运行时 ClassCastException
2. **类型擦除**——泛型信息仅在编译期存在，运行时 `List<String>` 和 `List<Integer>` 是同一个 `Class`；编译器在返回值处自动插入 checkcast 指令保证类型安全
3. **PECS 原则**——Producer（从集合取数据）用 `? extends T`；Consumer（向集合放数据）用 `? super T`；既要取又要放用 `<T>`
4. **类型擦除四大限制**——不能 `new T()`（用 `Class<T>` 反射）；不能 `instanceof T`；不能 `new T[n]`（用 `Object[]` + 强转）；不能 `static` 字段引用 T
5. **桥接方法**——编译器为泛型子类生成签名擦除后的桥接方法，保持多态正确
6. **Java 泛型不协变**——`List<Integer>` 不是 `List<Number>` 的子类型；与之对比，Java 数组是协变的（运行时抛 ArrayStoreException）
7. **原始类型陷阱**——`List` 绕过所有泛型检查，仅用于兼容 Java 1.4 旧代码；新代码一律禁止

### 跨语言对比：泛型

| 维度 | Java | C++ | Rust | Go（1.18+） |
|------|------|-----|------|------------|
| 实现方式 | 类型擦除（编译后消失） | 模板单态化（每实例生成独立代码） | 单态化 + trait bound | 单态化（字典传递方案） |
| 运行时类型信息 | 无（擦除） | 有（每个实例是独立类型） | 有（编译期展开） | 有（接口表） |
| 类型约束 | `extends` 上界 | `typename` + concept（C++20） | trait bound `T: Trait` | interface 约束 |
| 代码膨胀 | 否（一份字节码） | 是（每类型一份） | 是（每类型一份） | 轻微 |
| 基本类型参数 | 不能（需装箱） | 可以（`vector<int>`） | 可以（`Vec<i32>`） | 可以（`[]int`） |
| 通配符/变体 | `? extends/super` 声明处不变 | 隐式（调用时推导） | 无（生命周期替代部分场景） | 无 |

Java 的类型擦除是「用运行期能力换向后兼容」的权衡——旧 JVM 可直接运行泛型化库，代价是无法在运行时反射获取泛型参数。

### 阶段验收标准

- 能写泛型类、泛型方法和泛型接口，理解 `<T>` 在三种位置的语法
- 能解释类型擦除：擦除规则、checkcast 插入、运行期 Class 相同
- 能使用 `? extends T`（生产者）和 `? super T`（消费者），解释 PECS 原则
- 能识别四大限制（new T/instanceof T/new T[]/static T）并写出规避方式
- 能识别原始类型并解释其风险

### 进入下一阶段前

确保能完成以下练习：
- 泛型 Box（单类型参数，展示运行时 Class 相同）
- 泛型 Pair（双类型参数 + 泛型方法 swapValues）
- 泛型 Stack（Object[] 规避泛型数组 + pop 强转）
- 泛型 Repository（泛型接口 + 实现类绑定具体类型）
- PECS 演示（`? extends` 只读 + `? super` 只写 + copyAll 组合）

### 推荐项目

- **泛型 Repository\<T\>**：定义 `save`/`findById`/`findAll`/`deleteById` 契约，对 User、Device、Vehicle 等实体各实现一个具体 Repository
- **泛型结果封装 Result\<T\>**：成功/失败统一封装，含 `map`/`flatMap` 方法，替代 null 返回和异常过抛

### 下一阶段

[异常处理阶段](../ph06-exception/06-exception.md) — checked/unchecked exception、try-with-resources、异常链与自定义异常。
