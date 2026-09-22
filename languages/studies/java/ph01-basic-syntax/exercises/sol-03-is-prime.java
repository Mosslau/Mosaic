// exercises/sol-03-is-prime.java —— 练习 3 参考实现：判断素数
// 验证环境：OpenJDK 17.0.16（建议 JDK 17+）
// 编译：javac sol-03-is-prime.java
// 运行：java Sol03IsPrime
// 说明：类名 Sol03IsPrime 与文件名不同（非 public 类）
// 已验证：本环境编译运行通过，输出以 2 3 5 7 11 开头、97 结尾，共 25 个素数
class Sol03IsPrime {
    // 试除到 √n：若 n 有大于 √n 的因子，必有一个小于 √n 的因子
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
