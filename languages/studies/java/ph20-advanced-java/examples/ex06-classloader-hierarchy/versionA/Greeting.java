/*
 * examples/ex06-classloader-hierarchy/versionA/Greeting.java —— 版本 A（与 versionB 同名同包不同实现）
 * 编译（输出到目录 dirA）：javac -encoding UTF-8 -d <dirA> Greeting.java
 */
public class Greeting {
    public String greet() {
        return "version A: 父加载器之前由自定义 loader 抢到";
    }
}
