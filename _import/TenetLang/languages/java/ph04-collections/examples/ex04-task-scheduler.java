// examples/ex04-task-scheduler.java —— PriorityQueue 任务调度：最小堆按优先级依次处理 + TopK 选取
// 对应主文档「6. 代码示例 / 示例 4」
// 验证环境：OpenJDK 17.0.16
// 编译：javac ex04-task-scheduler.java
// 运行：java TaskScheduler
// 已验证：本环境编译零错误，运行输出符合注释中的期望值（TopK 打印顺序不保证）
import java.util.*;

class TaskScheduler {
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

        System.out.println("按优先级处理任务:");   // poll 依次弹出堆顶，保证优先级顺序
        while (!pq.isEmpty()) {
            System.out.println("  处理: " + pq.poll());
        }

        // TopK 示例：保留最大的 3 个（小堆，堆顶是当前最小，超长就淘汰堆顶）
        List<Integer> data = Arrays.asList(3, 1, 4, 1, 5, 9, 2, 6);
        PriorityQueue<Integer> minHeap = new PriorityQueue<>(3);
        for (int n : data) {
            minHeap.offer(n);
            if (minHeap.size() > 3) minHeap.poll();
        }
        System.out.println("最大的 3 个数: " + minHeap);
        // 集合内容固定为 {5, 6, 9}；直接打印是堆的内部数组顺序，不保证排序
    }
}
