// exercises/sol-02-multiplication-table.java —— 练习 2 参考实现：九九乘法表
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac sol-02-multiplication-table.java
// 运行：java Sol02MultiplicationTable
// 说明：类名 Sol02MultiplicationTable 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，输出 9 行，首行 1×1=1，末行以 9×9=81 结尾
class Sol02MultiplicationTable {
    public static void main(String[] args) {
        for (int i = 1; i <= 9; i++) {
            for (int j = 1; j <= i; j++) {
                // %-2d：左对齐占两位，让个位数与两位数列对齐
                System.out.printf("%d×%d=%-2d  ", j, i, i * j);
            }
            System.out.println();
        }
    }
}
