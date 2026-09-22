// examples/ex01-manual-javac.java —— 手动 javac 构建演示：多文件、包、-d 输出目录、-cp classpath
// 配套文件：ex01-helper.java（同包第二个源文件, 演示 javac 一次编译多个源文件）
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18）
// 验证状态：已验证（本机实测, 输出见 examples/README.md）
// 编译/运行命令：
//   1. 一次编译两个源文件到 build/（-d 指定输出目录, 自动按包建目录）
//      javac -d build ex01-manual-javac.java ex01-helper.java
//      java -cp build manual.ManualJavacDemo "mosslau"     # 实测输出: Hello, mosslau!
//   2. 演示 classpath 分离：helper 单独编译到 build-lib, 主程序用 -cp 引用编译好的类
//      javac -d build-lib ex01-helper.java
//      javac -d build-app -cp build-lib ex01-manual-javac.java
//      java -cp build-lib:build-app manual.ManualJavacDemo  # macOS/Linux 用冒号(:)分隔, Windows 用分号(;)
//   3. 产物清理：rm -rf build build-lib build-app
// 说明：类刻意不声明为 public（Java 规定 public 类必须与文件名同名, 非 public 类无此限制）,
//       这是本阶段示例统一采用 ex0X-*.java 命名的基础。
package manual;

class ManualJavacDemo {
    public static void main(String[] args) {
        String name = args.length > 0 ? args[0] : "Java";
        // Helper 与 ManualJavacDemo 同包不同文件——javac 要么一次编译两个源文件,
        // 要么先编译 helper 再让 javac 从 -cp 里解析它（步骤 2 演示的正是这条 classpath 拼接链路）
        System.out.println(Helper.greet(name));
    }
}
