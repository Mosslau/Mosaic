// examples/ex01-helper.java —— ex01 的配套源文件：同包第二个文件, 演示多文件编译与 classpath
// 与 ex01-manual-javac.java 一起使用（单独编译到 build-lib 后再由主程序 -cp 引用）
// 验证环境：OpenJDK 17.0.18；验证状态：已验证（编译/运行命令见 ex01-manual-javac.java 文件头）
package manual;

class Helper {
    public static String greet(String name) {
        return "Hello, " + name + "!";
    }
}
