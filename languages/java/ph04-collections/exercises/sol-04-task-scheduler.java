// exercises/sol-04-task-scheduler.java —— 练习 4 PriorityQueue 任务调度参考实现
// 验证环境：OpenJDK 17.0.16
// 编译：javac sol-04-task-scheduler.java
// 运行：java TaskScheduler
// 验证状态：已验证：OpenJDK 17.0.16
import java.util.Comparator;
import java.util.PriorityQueue;

class TaskScheduler {
    // 任务：name + priority，priority 越小越紧急
    static class Task {
        String name;
        int priority;

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
        // 最小堆：按 priority 升序取出
        PriorityQueue<Task> queue = new PriorityQueue<>(Comparator.comparingInt(t -> t.priority));
        queue.offer(new Task("紧急修复", 1));
        queue.offer(new Task("功能开发", 2));
        queue.offer(new Task("代码审查", 3));
        queue.offer(new Task("文档更新", 4));

        // for-each 遍历的是堆的内部数组顺序，不保证有序
        System.out.println("for-each 遍历（无序）: " + queue);

        System.out.println("按优先级处理:");
        while (!queue.isEmpty()) {
            System.out.println("  处理: " + queue.poll());
            // 顺序：紧急修复(P1) → 功能开发(P2) → 代码审查(P3) → 文档更新(P4)
        }

        // 最大堆：Comparator.reverseOrder() 反转自然顺序
        PriorityQueue<Integer> maxHeap = new PriorityQueue<>(Comparator.reverseOrder());
        for (int n : new int[] {3, 1, 4, 1, 5, 9, 2, 6}) {
            maxHeap.offer(n);
        }
        System.out.println("最大的 3 个数:");
        for (int i = 0; i < 3; i++) {
            System.out.println("  " + maxHeap.poll());          // 9, 6, 5
        }
    }
}
