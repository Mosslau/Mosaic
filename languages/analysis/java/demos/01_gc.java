// 01 · 垃圾回收与自动内存管理演示
// 运行：java demos/01_gc.java            （JDK 11+ 单文件模式）
// 观察 GC：java -Xlog:gc demos/01_gc.java

import java.lang.ref.Cleaner;

class GcDemo {
    // 注意：单文件模式运行 java 01_gc.java 时，本类必须是文件里第一个顶层类
    static class Node {
        Node next;           // 单链表结点（用来造循环引用）
        final byte[] payload = new byte[64];  // 每个结点占点内存，方便观察 GC
    }

    public static void main(String[] args) {
        System.out.println("== 1. 你无法手动释放：new 出去的内存归运行时管 ==");
        System.out.println("   Java 没有 delete/free；System.gc() 只是'建议'，不是保证。");

        System.out.println("\n== 2. 循环引用也能被回收（可达性分析 vs 引用计数）==");
        for (int round = 0; round < 3; round++) {
            Node a = new Node();
            Node b = new Node();
            a.next = b;
            b.next = a;          // a↔b 成环，互相引用
            // round 结束 a、b 离开作用域 → 从 GC Roots 不可达 → 整环是垃圾
        }
        // 引用计数会因环内计数不为 0 而泄漏；可达性分析从 Roots 出发，环整体不可达即回收
        System.out.println("   3 轮互相引用的环已创建并离开作用域——它们都会被回收。");
        System.out.println("   用 -Xlog:gc 跑本文件，可看到真实的 GC 日志（见头注释）。");

        System.out.println("\n== 3. 释放时机不可控：Cleaner 只是'提醒'，不是保证 ==");
        Cleaner cleaner = Cleaner.create();
        // 模拟注册一个清理动作（真实场景注册文件句柄/内存映射等外部资源）
        cleaner.register(new Object(), () -> System.out.println("   (Cleaner 清理动作被注册)"));
        System.out.println("   Cleaner 动作在对象不可达后的某个时刻执行——你无法指定时机。");
        System.out.println("   这正说明：Java 连'外部资源'都要靠 try-with-resources 显式关闭，");
        System.out.println("   内存交给 GC，文件/连接自己管（见笔记 01 §4）。");

        System.out.println("\n== 结束：看内存自动回收后的进程仍健康运行 ==");
    }
}
