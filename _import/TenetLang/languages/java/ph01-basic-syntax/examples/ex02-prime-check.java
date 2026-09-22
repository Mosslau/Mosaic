// examples/ex02-prime-check.java —— 判断素数：打印 1~100 内全部素数
// 对应主文档「6. 代码示例 / 示例 2」
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac ex02-prime-check.java
// 运行：java PrimeCheck
// 说明：类名 PrimeCheck 与文件名不同（非 public 类）；isPrime 是静态方法，方法属于 ph02 内容，此处模仿写法即可
// 已验证：本环境编译运行通过，输出以 2 3 5 7 11 开头、97 结尾，共 25 个素数
class PrimeCheck {
    // 试除到 √n 即可：若 n 有大于 √n 的因子，必有一个小于 √n 的因子
    static boolean isPrime(int n) {
        if (n < 2) return false;
        for (int i = 2; i * i <= n; i++) {
            if (n % i == 0) return false;
        }
        return true;
    }

    public static void main(String[] args) {
        System.out.print("1-100 的素数: ");
        for (int i = 1; i <= 100; i++) {
            if (isPrime(i)) {
                System.out.print(i + " ");
            }
        }
        System.out.println();
    }
}
