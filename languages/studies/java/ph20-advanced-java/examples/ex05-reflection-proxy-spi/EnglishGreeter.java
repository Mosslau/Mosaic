/*
 * examples/ex05-reflection-proxy-spi/EnglishGreeter.java —— SPI 实现 B（public + 无参构造）
 */
public final class EnglishGreeter implements Greeter {
    @Override
    public String greet(String who) {
        return "Hello, " + who;
    }
}
