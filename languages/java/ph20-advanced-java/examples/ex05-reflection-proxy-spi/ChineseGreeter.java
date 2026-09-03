/*
 * examples/ex05-reflection-proxy-spi/ChineseGreeter.java —— SPI 实现 A（默认包，public + 无参构造）
 */
public final class ChineseGreeter implements Greeter {
    @Override
    public String greet(String who) {
        return "你好，" + who;
    }
}
