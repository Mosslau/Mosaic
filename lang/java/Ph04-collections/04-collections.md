# Java 集合框架阶段

> 面向企业级后端、微服务和车联网数据平台，建立接口驱动、复杂度敏感的集合选择与使用能力。

## 1. 概述

Java 集合框架阶段的目标是：**接口与实现分离——List 是接口，ArrayList/LinkedList 是实现；对每种场景能说出为何选这个实现而非那个**。本阶段覆盖日常开发中全部核心集合接口和实现，是写出高性能、低 Bug Java 代码的前提。

| 核心维度 | 覆盖内容 |
|----------|---------|
| 线性集合 | List（ArrayList、LinkedList）、Queue（PriorityQueue）、Deque（ArrayDeque） |
| 集合与去重 | Set（HashSet、LinkedHashSet、TreeSet） |
| 键值映射 | Map（HashMap、LinkedHashMap、TreeMap） |
| 并发集合 | ConcurrentHashMap（读无锁、CAS 写） |
| 遍历陷阱 | ConcurrentModificationException、Iterator.remove()、removeIf |

本阶段不涉及 Stream API、泛型原理和自定义集合实现。

## 2. 来源与演变

Java 集合框架的设计演进反映了对类型安全、性能和并发模型的持续追求：

- **Java 1.0/1.1（1995-1997）**：仅有 Vector（线程安全动态数组）、Hashtable（线程安全哈希表）、Stack、Enumeration。Vector 和 Hashtable 所有方法用 synchronized 修饰，性能低，且元素类型为 Object，编译期无类型检查。
- **Java 2（Java 1.2, 1998）— 集合框架诞生**：引入 Collection、List、Set、Map 接口体系，以及 ArrayList、LinkedList、HashMap、HashSet、TreeMap 等核心实现。将接口和实现分离，同时提供 Collections 工具类（排序、二分查找、不可变包装等）。Vector 和 Hashtable 被标记为遗留类，但为兼容保留至今。
- **Java 5（2004）— 泛型**：集合框架全面泛型化（如 `List<String>` 替代 `List`），编译期类型检查消除了 ClassCastException，消除手写强制转换。增强 for 循环（for-each）进一步简化遍历语法。
- **Java 6（2006）— 双端队列**：新增 Deque 接口和 ArrayDeque 实现，推荐替代 Stack 作为 LIFO 栈，替代 LinkedList 作为 FIFO 队列。
- **Java 7（2011）— 钻石语法**：`new ArrayList<>()` 省略泛型参数重复，编译器从左侧推断。
- **Java 8（2014）— 函数式增强与并发重写**：HashMap 引入红黑树优化哈希冲突（桶链表长度 >= 8 且数组长度 >= 64 时树化，回退阈值 6）。新增 forEach、replaceAll、computeIfAbsent、merge 等默认方法。ConcurrentHashMap 完全重写——废弃分段锁，改为 CAS + synchronized 细粒度锁，读操作完全无锁。
- **Java 9（2017）— 不可变工厂方法**：`List.of()`、`Set.of()`、`Map.of()` 成为创建不可变集合的标准方式——返回的集合调用 add/put 直接抛 UnsupportedOperationException。

## 3. 语法与参数

### 3.1 接口与实现分离

集合框架的核心设计原则：接口定义行为契约，实现提供具体数据结构。使用时声明接口类型，只在构造时选择实现。

```java
List<String> list = new ArrayList<>();   // 接口引用，ArrayList 实现
Map<String, Integer> map = new HashMap<>();
Set<String> set = new HashSet<>();
```

选错实现不会编译失败，但运行性能可能差几十倍。例如 `list.get(500000)` 在 ArrayList 上是 O(1)，在 LinkedList 上是 O(n)。一旦写好了类型声明，更换实现只需改 `new` 那一个位置——调用代码完全不变。

### 3.2 List：ArrayList vs LinkedList

| 操作 | ArrayList | LinkedList |
|------|-----------|------------|
| get(int index) | O(1) | O(n) |
| add(E)（末尾追加） | O(1) 均摊 | O(1) |
| add(int index, E)（中间插入） | O(n) — 元素后移 | O(n) — 先遍历到位置 |
| remove(int index) | O(n) — 元素前移 | O(n) — 先遍历到位置 |
| 内存占用 | 连续数组，空间紧凑 | 双向链表，每个节点有两个指针额外开销 |

现代 Java 开发中 LinkedList 的使用已大幅减少——"中间插入 O(1)"需先遍历到位置（寻找本身 O(n)），作为队列/栈时 ArrayDeque 更快且内存更紧凑。

```java
List<String> list = new ArrayList<>();
list.add("Alice");
list.add("Bob");
list.get(0);               // "Alice"
list.set(0, "Charlie");    // 替换索引 0
list.remove("Bob");        // 删除第一个匹配的元素
list.remove(0);            // 删除索引 0 的元素
list.size();               // 元素数量
list.contains("Alice");    // 是否存在
list.isEmpty();            // 是否为空
```

初始化容量：`new ArrayList<>(256)` 可避免扩容带来的数组拷贝开销。默认初始容量 10，每次扩容为原来的 1.5 倍。

### 3.3 Set：HashSet / LinkedHashSet / TreeSet

Set 不允许重复元素——由 `equals()` 判断相等。HashSet 内部基于 HashMap 实现（元素作为 key，value 为固定常量 `PRESENT`），TreeSet 基于 TreeMap 实现。

```java
Set<String> hashSet = new HashSet<>();          // O(1) add/contains/remove，无顺序
Set<String> treeSet = new TreeSet<>();           // O(log n) add/contains/remove，自然顺序
Set<String> linkedSet = new LinkedHashSet<>();   // O(1) + 保持插入顺序
```

放入 HashSet 的对象必须正确重写 `hashCode()` 和 `equals()`（呼应 Ph03——不重写则两个内容相同的对象可能放入同一个 Set）。TreeSet 元素必须实现 Comparable 或构造时传入 Comparator，否则 `add` 时抛 ClassCastException。

Set 的批量操作来自 Collection 接口，支持并集、交集、差集：

```java
Set<Integer> a = new HashSet<>(Set.of(1, 2, 3, 4));
Set<Integer> b = new HashSet<>(Set.of(3, 4, 5, 6));

a.addAll(b);       // 并集：a = {1,2,3,4,5,6}
a.retainAll(b);    // 交集：a = {3,4}
a.removeAll(b);    // 差集：a = {1,2}——a 中除去 b 也有的
```

### 3.4 Map：HashMap / LinkedHashMap / TreeMap

Map 是键值对容器，键不能重复（equals 判断）。三个核心实现按照对顺序的需求选择：

```java
Map<String, Integer> hashMap = new HashMap<>();           // 无顺序保证，O(1)
Map<String, Integer> linkedMap = new LinkedHashMap<>();    // 保持插入顺序，O(1)
Map<String, Integer> treeMap = new TreeMap<>();            // 按键的自然顺序排序，O(log n)
```

常用 API：

```java
Map<String, Integer> map = new HashMap<>();
map.put("Alice", 90);
map.get("Alice");                       // 90
map.getOrDefault("Bob", 0);             // 0（不存在时的默认值）
map.containsKey("Alice");               // true
map.putIfAbsent("Alice", 100);          // 仅当 key 不存在时写入，返回旧值或 null
map.remove("Alice");
map.size();

// 遍历方式
for (Map.Entry<String, Integer> e : map.entrySet()) { /* key + value */ }
for (String key : map.keySet()) { /* keys */ }
for (Integer val : map.values()) { /* values */ }
```

LinkedHashMap 有三个关键构造参数——初始容量、负载因子和一个布尔值 `accessOrder`。当 `accessOrder=true` 时，每次 `get` 或 `put` 都会将该条目移到内部双向链表的末尾，从而实现 LRU（最近最少使用）淘汰策略。默认 `accessOrder=false` 仅保持插入顺序。

TreeMap 基于红黑树，迭代时的顺序由键的 `Comparable.compareTo()` 或构造时传入的 `Comparator.compare()` 决定。如果键的自然顺序与需求不符（如大小写不敏感的字符串排序），必须显式传入 Comparator。

### 3.5 Queue 与 Deque

Queue 是先进先出（FIFO）队列，Deque 是双端队列（两端均可出入）。日常开发中 ArrayDeque 是这两个接口的首选实现——比 LinkedList 更快，内存更紧凑。作为 LIFO 栈使用时，推荐用 `push()`/`pop()` 替代 Stack（Stack 继承 Vector，有 synchronized 开销）。

```java
Queue<String> queue = new ArrayDeque<>();
queue.offer("task1");       // 入队（队尾）
queue.offer("task2");
queue.poll();               // 出队（队首），空返 null
queue.peek();               // 查看队首，空返 null

Deque<String> deque = new ArrayDeque<>();
deque.offerFirst("left");   // 头部入队
deque.offerLast("right");   // 尾部入队
deque.pollFirst();          // 头部出队
deque.pollLast();           // 尾部出队
```

### 3.6 PriorityQueue

PriorityQueue 基于二叉堆实现，默认是最小堆（队首元素最小）。元素必须实现 Comparable 或构造时传入 Comparator。

```java
// 最小堆（默认）
PriorityQueue<Integer> minHeap = new PriorityQueue<>();
minHeap.offer(3);
minHeap.offer(1);
minHeap.offer(2);
System.out.println(minHeap.poll()); // 1（最小）

// 最大堆（传入反转比较器）
PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Comparator.reverseOrder());
maxHeap.offer(3);
maxHeap.offer(1);
maxHeap.offer(2);
System.out.println(maxHeap.poll()); // 3（最大）

// 自定义对象 + 自定义比较器（按优先级字段排序）
PriorityQueue<Task> taskQueue = new PriorityQueue<>(
    Comparator.comparingInt(Task::getPriority)
);
```

`offer()` 和 `poll()` 时间复杂度 O(log n)，`peek()` 时间复杂度 O(1)。**遍历不保证顺序**——for-each 遍历 PriorityQueue 的结果是堆的内部存储顺序，不是排序结果。要按优先级依次取出，只能用 `poll()` 循环。

### 3.7 ConcurrentHashMap

ConcurrentHashMap 是线程安全的 HashMap，适合高并发读写场景。与 Hashtable（全表锁）和 `Collections.synchronizedMap()`（整个 map 包装锁）不同，ConcurrentHashMap（Java 8+）使用 CAS + 局部 synchronized 锁定单个桶的首节点，读操作完全无锁。

```java
ConcurrentHashMap<String, Integer> map = new ConcurrentHashMap<>();
map.put("device-001", 85);
map.get("device-001");                          // 读操作：无锁，volatile 可见
map.computeIfAbsent("device-002", k -> 0);       // 原子初始化
map.merge("device-001", 1, Integer::sum);        // 原子累加
```

ConcurrentHashMap 不支持 null 键和值（与 HashMap 不同——null 在并发环境下无法区分"不存在"和"存为 null"）。`size()` 返回近似值而非精确计数（精确计数需遍历所有段，代价高）。

### 3.8 遍历修改与 ConcurrentModificationException

在 for-each 循环中直接修改集合会抛出 ConcurrentModificationException——这是集合的 fail-fast 机制：

```java
List<String> list = new ArrayList<>(List.of("A", "B", "C"));
for (String s : list) {
    if ("B".equals(s)) {
        list.remove(s);  // 运行时 ConcurrentModificationException
    }
}
```

fail-fast 的原理：集合内部维护一个 `modCount` 计数器，每次结构性修改（add/remove）时递增。迭代器创建时记录 `expectedModCount = modCount`，每次 `next()` 检查两者是否一致，不一致则立即抛异常。

三种正确的遍历中修改方式：

```java
// 方式 1：Iterator.remove()
Iterator<String> it = list.iterator();
while (it.hasNext()) {
    if ("B".equals(it.next())) it.remove();
}

// 方式 2：removeIf（Java 8+，最简洁，内部也是 Iterator）
list.removeIf(s -> "B".equals(s));

// 方式 3：先收集再批量删除
List<String> toRemove = new ArrayList<>();
for (String s : list) { if ("B".equals(s)) toRemove.add(s); }
list.removeAll(toRemove);
```

## 4. 底层原理

### 4.1 HashMap 哈希桶 + 链表 + 红黑树

HashMap 的核心结构是一个 `Node<K,V>[] table` 数组（桶），每个桶指向一个链表或红黑树的根节点。键值对放入流程：

1. 调用 `key.hashCode()` 获取哈希值，扰动函数 `h ^ (h >>> 16)` 将高位参与异或运算，降低低位相同的碰撞概率。
2. 计算桶索引：`(n - 1) & hash`，其中 n 为数组长度（始终为 2 的幂，便于用位运算替代取模）。
3. 目标桶为空时直接放入；桶中已有元素则遍历链表并用 `equals()` 比较——键相同则替换 value。
4. **树化**（Java 8+）：当某个桶的链表长度达到 `TREEIFY_THRESHOLD = 8` 且数组长度 >= `MIN_TREEIFY_CAPACITY = 64` 时，链表转为红黑树，将最坏情况查找从 O(n) 降为 O(log n)。当树中节点数降至 `UNTREEIFY_THRESHOLD = 6` 时回退为链表。
5. **扩容**：当 `size > capacity * loadFactor`（默认 16 * 0.75 = 12）时，容量翻倍（`oldCap << 1`），所有元素重新计算桶索引（rehash）。rehash 时利用 2 的幂特性——元素只可能停留在原位或移到 `原位置 + oldCap`，无需重新计算哈希。

负载因子 0.75 是时间与空间的折中。根据泊松分布，在负载因子为 0.75 时，单个桶内元素数量达到 8 个的概率小于千万分之一（`exp(-0.5) * pow(0.5, 8) / 8! ≈ 6.0e-8`），因此正常情况下链表不会触发树化。如果预知元素数量，通过 `new HashMap<>(expectedSize)` 指定初始容量可避免扩容开销。

### 4.2 ConcurrentHashMap 的 CAS 设计（Java 8+）

Java 7 的 ConcurrentHashMap 使用分段锁（Segment，每个 Segment 是一个独立的 ReentrantLock），默认并发级别 16。跨段操作需要获取多个锁，且每个 Segment 内部仍是小 HashEntry 数组。

Java 8 完全重写数据结构，与 HashMap 一致（Node 数组 + 链表 + 红黑树），但并发控制完全不同：

- **读操作**：完全无锁。Node 数组的引用和 Node 的 `val`/`next` 字段均声明为 `volatile`，写入后对其他线程立即可见。
- **桶为空时插入**：使用 `compareAndSwapObject`（CAS）尝试无锁插入。如果 CAS 成功则操作完成；如果 CAS 失败（说明有其他线程抢先），退化为 synchronized 锁定桶首节点后重试。
- **桶非空时写入**：对桶的首节点加 `synchronized` 锁，锁定范围仅限该桶，不阻塞其他桶的读写。
- **扩容迁移**：支持多线程协同迁移——发现正在扩容的桶时，线程会帮助将旧表数据迁移到新表，减少扩容停顿时间。

这一设计使 ConcurrentHashMap 的读性能接近纯 HashMap，高并发写场景远超 Hashtable 和 `Collections.synchronizedMap()`。

### 4.3 PriorityQueue 二叉堆

PriorityQueue 内部用 `Object[] queue` 存储二叉堆（完全二叉树），索引关系：节点 i 的左子节点在 `2i + 1`，右子节点在 `2i + 2`，父节点在 `(i - 1) / 2`。

- **offer(e)**：将元素放在数组末尾，执行 siftUp（上浮）——与父节点比较并交换，直到堆序恢复，O(log n)。
- **poll()**：取出 `queue[0]`（堆顶元素），将数组最后一个元素移到堆顶，执行 siftDown（下沉）——与两个子节点中较小的比较并交换，直到堆序恢复，O(log n)。
- **扩容**：元素数不足 64 时首次扩容到 64，之后每次扩容到原来的 2 倍（与 ArrayList 不同——ArrayList 是 1.5 倍）。

因为二叉堆内部只保证父节点小于子节点（最小堆），不保证兄弟节点之间的大小关系，所以 for-each 遍历的结果不是排序的。

## 5. 使用场景

| 场景 | 推荐选择 | 理由 |
|------|---------|------|
| 按索引随机访问 | ArrayList | O(1) get |
| 频繁尾部追加 | ArrayList | O(1) 均摊，内存紧凑 |
| 双向队列 / 栈 | ArrayDeque | 比 LinkedList 快，内存紧凑 |
| 去重且不关心顺序 | HashSet | O(1) add/contains |
| 去重且需排序 | TreeSet | O(log n) + 自然顺序 |
| 去重且保插入序 | LinkedHashSet | O(1) + 插入顺序 |
| 键值对无顺序需求 | HashMap | O(1) put/get |
| 键值对保插入顺序 | LinkedHashMap | O(1) + 插入顺序 |
| 键值对需按键排序 | TreeMap | O(log n) + 自然顺序 |
| 高并发读写键值对 | ConcurrentHashMap | 读无锁，CAS 写 |
| 任务调度 / TopK | PriorityQueue | O(log n) 取最值 |
| LRU 缓存 | LinkedHashMap（accessOrder=true） | 自动淘汰最久未访问条目 |
| 多线程共享映射 | ConcurrentHashMap | 线程安全，读近 HashMap 性能 |

不适合的使用方式：多线程共享 HashMap（用 ConcurrentHashMap）；用 Vector 替代 ArrayList（不需要同步时 Vector 的 synchronized 是纯开销）；用 Hashtable 替代 ConcurrentHashMap（全表锁 vs 局部锁，性能差一个数量级）；在 for-each 中直接 remove（用 removeIf 或 Iterator）；用 LinkedList 作为队列或栈（用 ArrayDeque 替代）。

## 6. 代码示例

### 示例 1：List 管理学生

```java
import java.util.*;

public class StudentManager {
    public static void main(String[] args) {
        List<String> students = new ArrayList<>();
        students.add("Alice");
        students.add("Bob");
        students.add("Charlie");

        System.out.println("学生列表: " + students);
        System.out.println("总人数: " + students.size());
        System.out.println("第一位: " + students.get(0));

        // 删除指定元素
        students.remove("Bob");
        System.out.println("删除 Bob 后: " + students);

        // 排序
        students.sort(Comparator.naturalOrder());
        System.out.println("按字母排序后:");
        for (String s : students) {
            System.out.println("  - " + s);
        }

        // 安全删除：removeIf — 遍历中修改不会抛异常
        students.add("Alex");
        students.removeIf(s -> s.startsWith("A"));
        System.out.println("删除 A 开头后: " + students);
    }
}
```

### 示例 2：Map 统计词频

```java
import java.util.*;

public class WordFrequency {
    public static void main(String[] args) {
        String text = "the quick brown fox jumps over the lazy dog the fox";
        String[] words = text.split(" ");

        Map<String, Integer> freq = new HashMap<>();
        for (String word : words) {
            freq.put(word, freq.getOrDefault(word, 0) + 1);
        }

        System.out.println("词频统计:");
        for (Map.Entry<String, Integer> entry : freq.entrySet()) {
            System.out.printf("  %-8s : %d%n", entry.getKey(), entry.getValue());
        }

        // 找最高频词
        String topWord = Collections.max(freq.entrySet(),
                Map.Entry.comparingByValue()).getKey();
        System.out.println("最高频词: " + topWord);
    }
}
```

### 示例 3：Set 去重

```java
import java.util.*;

public class SetDedup {
    public static void main(String[] args) {
        List<Integer> numbers = Arrays.asList(3, 1, 4, 1, 5, 9, 2, 6, 5, 3);

        // LinkedHashSet 去重并保持插入顺序
        Set<Integer> unique = new LinkedHashSet<>(numbers);
        System.out.println("去重(保持顺序): " + unique);

        // TreeSet 去重并自然排序
        Set<Integer> sorted = new TreeSet<>(numbers);
        System.out.println("去重(自然排序): " + sorted);

        // HashSet 批量操作：交集
        Set<Integer> other = new HashSet<>(Arrays.asList(1, 2, 3, 10, 11));
        unique.retainAll(other);
        System.out.println("与 {1,2,3,10,11} 的交集: " + unique);
    }
}
```

### 示例 4：PriorityQueue 任务调度

```java
import java.util.*;

public class TaskScheduler {
    static class Task {
        String name;
        int priority; // 数字越小优先级越高

        Task(String name, int priority) {
            this.name = name;
            this.priority = priority;
        }

        @Override
        public String toString() {
            return name + "(P" + priority + ")";
        }
    }

    public static void main(String[] args) {
        // 最小堆：按 priority 升序取出，priority 小的先处理
        PriorityQueue<Task> pq = new PriorityQueue<>(
                Comparator.comparingInt(t -> t.priority));

        pq.offer(new Task("紧急修复", 1));
        pq.offer(new Task("代码审查", 3));
        pq.offer(new Task("功能开发", 2));
        pq.offer(new Task("文档更新", 4));

        System.out.println("按优先级处理任务:");
        while (!pq.isEmpty()) {
            System.out.println("  处理: " + pq.poll());
        }

        // TopK 示例：保留最大的 3 个
        List<Integer> data = Arrays.asList(3, 1, 4, 1, 5, 9, 2, 6);
        PriorityQueue<Integer> minHeap = new PriorityQueue<>(3);
        for (int n : data) {
            minHeap.offer(n);
            if (minHeap.size() > 3) minHeap.poll();
        }
        System.out.println("最大的 3 个数: " + minHeap);
    }
}
```

### 示例 5：LRU Cache（基于 LinkedHashMap）

```java
import java.util.*;

public class LRUCache<K, V> extends LinkedHashMap<K, V> {
    private final int capacity;

    public LRUCache(int capacity) {
        // accessOrder=true：按访问顺序排列，最近访问的在末尾
        super(capacity, 0.75f, true);
        this.capacity = capacity;
    }

    @Override
    protected boolean removeEldestEntry(Map.Entry<K, V> eldest) {
        return size() > capacity; // 超限时淘汰最久未访问条目
    }

    public static void main(String[] args) {
        LRUCache<String, String> cache = new LRUCache<>(3);
        cache.put("A", "设备A状态");
        cache.put("B", "设备B状态");
        cache.put("C", "设备C状态");
        System.out.println("初始缓存: " + cache.keySet());  // [A, B, C]

        cache.get("A"); // 访问 A —— A 移到链表末尾，变最新
        cache.put("D", "设备D状态"); // 插入 D —— 淘汰最久未用的 B
        System.out.println("访问 A 插入 D 后: " + cache.keySet()); // [C, A, D]

        cache.put("E", "设备E状态"); // 淘汰 C
        System.out.println("插入 E 后: " + cache.keySet()); // [A, D, E]
    }
}
```

## 7. 总结

### 关键要点

1. **接口与实现分离**——声明用接口（List/Set/Map），构造选实现；更换实现不影响调用代码
2. **ArrayList 首选**——随机访问 O(1)，现代开发中 LinkedList 几乎被 ArrayDeque 取代
3. **HashSet 基于 HashMap**——内部值为固定常量，add/remove/contains 均为 O(1)
4. **HashMap 不保证顺序**——键排列取决于哈希分布；需要顺序用 LinkedHashMap（插入序）或 TreeMap（排序序）
5. **HashMap 红黑树优化**（Java 8+）——桶链表 >= 8 且数组 >= 64 时树化，查找 O(n) → O(log n)；回退阈值 6
6. **负载因子 0.75**——扩容阈值 = capacity * 0.75，泊松分布下桶元素 >= 8 概率低于千万分之一
7. **ConcurrentHashMap 读无锁**（Java 8+）——CAS + synchronized 局部锁，读性能接近 HashMap
8. **ConcurrentModificationException**——for-each 中修改集合触发 fail-fast（modCount 校验）；用 Iterator.remove() 或 removeIf 安全删除
9. **PriorityQueue 最小堆默认**——O(log n) 取最值，构造时传 Comparator.reverseOrder() 变最大堆
10. **LinkedHashMap 可做 LRU**——accessOrder=true + removeEldestEntry，自动淘汰最久未访问条目

### 跨语言集合框架对比

| 需求 | Java | Python | Go | C++ | Rust |
|------|------|--------|----|-----|------|
| 动态数组 | `ArrayList` | `list` | `slice` | `std::vector` | `Vec` |
| 哈希映射 | `HashMap` | `dict` | `map` | `std::unordered_map` | `HashMap` |
| 有序映射 | `LinkedHashMap`（插入序）/ `TreeMap`（排序） | `dict`（Python 3.7+ 保插入序） | N/A（需 slice + sort） | `std::map`（红黑树） | `BTreeMap`（B 树） |
| 哈希集合 | `HashSet` | `set` | N/A（用 `map[K]bool`） | `std::unordered_set` | `HashSet` |
| 二叉堆 | `PriorityQueue` | `heapq` | `container/heap` | `std::priority_queue` | `BinaryHeap` |
| 并发映射 | `ConcurrentHashMap` | N/A（无内置） | `sync.Map` | N/A（需外部锁） | `DashMap`（第三方） |

### 阶段验收标准

- 能按场景选择 List/Set/Map 的正确实现，并能解释 O() 复杂度依据
- 能解释 HashMap 的哈希桶 + 链表 + 红黑树结构和树化条件
- 能解释 ConcurrentHashMap（Java 8+）的 CAS 设计和读无锁原理
- 能避免遍历修改的错误，熟练使用 removeIf 和 Iterator.remove()
- 能用 PriorityQueue 实现任务调度和 TopK

### 进入下一阶段前

确保能完成以下练习：
- List 管理学生（ArrayList 增删改查、排序、安全删除）
- Map 统计词频（HashMap + getOrDefault，找最高频词）
- Set 去重（LinkedHashSet / TreeSet / HashSet 三选一，理解区别）
- PriorityQueue 任务调度（自定义比较器，理解最小堆/最大堆）
- LRU Cache（基于 LinkedHashMap accessOrder + removeEldestEntry）

### 推荐项目

- **LRU Cache**：基于 LinkedHashMap，accessOrder 模式 + removeEldestEntry，用于设备状态缓存
- **设备状态表**：ConcurrentHashMap 存储设备 ID → DeviceStatus，支持多线程并发读写

### 下一阶段

[泛型阶段](../Ph05-generics/05-generics.md)— 类型参数、通配符与类型擦除。
