// exercises/sol-01-process-diagnosis.java —— 练习 1 参考实现：持续运行的诊断目标程序
// 验证环境：OpenJDK 17.0.18；诊断工具 jps/jstat/jstack 为 JDK 自带
// 编译：javac sol-01-process-diagnosis.java
// 运行：java ProcessDiagnosisSol（注意是类名不是文件名；程序持续运行, 用 Ctrl-C 或 kill 结束）
// 验证状态：已验证：OpenJDK 17.0.18（jps/jstat/jstack 实测输出见 exercises/README.md 与下方注释）
// 运行前提：本程序故意无限循环保持进程存活, 供 jps/jstat/jstack 诊断；验证完必须 kill 清理
class ProcessDiagnosisSol {
    public static void main(String[] args) throws Exception {
        // 打印自身 PID：这是 jps/jstack/jstat 的入口, 也是练习 1 的目标之一
        System.out.println("PID = " + ProcessHandle.current().pid());
        long sum = 0;
        for (int i = 0; ; i++) {                       // 无限循环: 进程保持存活
            for (long j = 0; j < 1_000_000L; j++) sum += j;   // 一段计算, 让 main 线程处于 RUNNABLE
            if (i % 10 == 0) {
                System.out.println("第 " + i + " 轮计算完成, 累计 = " + sum);
            }
            Thread.sleep(200);
        }
    }
}
