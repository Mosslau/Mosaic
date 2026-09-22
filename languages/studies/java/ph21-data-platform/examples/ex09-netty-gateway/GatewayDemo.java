// examples/ex09-netty-gateway/GatewayDemo.java —— 网关集成演示：JDK Socket 模拟采集端注册 + 心跳
// 验证环境：OpenJDK 17.0.18 + netty-all 4.1.49.Final(路径见 GatewayServer.java 头部)
// 命令：
//   javac -encoding UTF-8 -cp $NETTY -d /tmp/tl21-ex ./*.java
//   java -cp $NETTY:/tmp/tl21-ex GatewayDemo
// 其中 $NETTY 指向 netty-all-4.1.49.Final.jar。
//
// 采集端侧故意用纯 JDK Socket 而非 Netty client——证明「网关是 Netty、采集端协议是行文本」，
// 业务只依赖一行一命令的协议，不依赖底层实现(这正是接入层解耦的落点)。
import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.atomic.AtomicInteger;

public final class GatewayDemo {
    public static void main(String[] args) throws Exception {
        GatewayServer gateway = new GatewayServer();
        int port = gateway.start();

        AtomicInteger pass = new AtomicInteger();
        try (Socket s = new Socket("127.0.0.1", port)) {
            s.setSoTimeout(3000);
            Writer out = new OutputStreamWriter(s.getOutputStream(), StandardCharsets.UTF_8);
            BufferedReader in = new BufferedReader(new InputStreamReader(s.getInputStream(), StandardCharsets.UTF_8));

            check(pass, send(in, out, "REG|LSV0000001").startsWith("ACK"), "采集端 REG 注册被网关接受");
            check(pass, send(in, out, "HB|LSV0000001|10").startsWith("ACK"), "在线g心跳被接受");
            check(pass, send(in, out, "HB|LSV0000001|20").startsWith("ACK"), "心跳序号推进到 20");
            check(pass, send(in, out, "HB|LSV0000999|5").startsWith("ERR"), "未注册 SOURCE_ID 心跳被拒(先 REG 后 HB)");
            check(pass, send(in, out, "GARBAGE").startsWith("ERR"), "坏命令返回 ERR");
        } finally {
            gateway.stop();
        }
        check(pass, gateway.onlineCount() == 1, "在线表恰好 1 个数据源(未注册心跳不产生条目)");
        System.out.printf("ALL PASS: %d/6%n", pass.get());
    }

    private static String send(BufferedReader in, Writer out, String line) throws IOException {
        out.write(line + "\n");
        out.flush();
        return in.readLine();
    }

    private static void check(AtomicInteger pass, boolean ok, String label) {
        System.out.println((ok ? "PASS " : "FAIL ") + label);
        if (ok) {
            pass.incrementAndGet();
        }
    }
}
