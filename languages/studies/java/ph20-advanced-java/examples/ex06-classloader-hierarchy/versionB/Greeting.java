/*
 * examples/ex06-classloader-hierarchy/versionB/Greeting.java —— 版本 B（同名同包，实现不同）
 * 编译（输出到目录 dirB）：javac -encoding UTF-8 -d <dirB> Greeting.java
 */
public class Greeting {
    public String greet() {
        return "version B: 另一个自定义 loader 加载的副本";
    }
}
