/*
 * examples/ex05-reflection-proxy-spi/Greeter.java
 * SPI 演示用服务接口：实现方按「META-INF/services/Greeter」登记，调用方只依赖本接口。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 */
public interface Greeter {
    String greet(String who);
}
