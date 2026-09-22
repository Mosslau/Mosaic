// examples/ex04-multiplication-table.java —— 九九乘法表
// 对应主文档「6. 代码示例 / 示例 4」
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac ex04-multiplication-table.java
// 运行：java MultiplicationTable
// 说明：类名 MultiplicationTable 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，输出 9 行，首行 1×1=1，末行以 9×9=81 结尾
class MultiplicationTable {
    public static void main(String[] args) {
        for (int i = 1; i <= 9; i++) {
            for (int j = 1; j <= i; j++) {
                // %-2d：乘积左对齐占两位，保证个位数与两位数列对齐
                System.out.printf("%d×%d=%-2d  ", j, i, i * j);
            }
            System.out.println();
        }
    }
}
