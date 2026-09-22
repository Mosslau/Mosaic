/*
 * exercises/sol-04-netty-tcp/UpperClient.java —— 练习 4 参考实现（客户端）
 * 连上 UpperServer 后逐行发送文本，逐行读取大写回显并断言——验证多行往返与按行 codec。
 *
 * 验证环境：OpenJDK 17.0.18 + netty 4.1.137.Final
 * 编译：javac -encoding UTF-8 -cp "<jar 目录>/*" -d /tmp/tl20-cls UpperServer.java UpperClient.java
 * 运行：java -cp "/tmp/tl20-cls:<jar 目录>/*" UpperClient <host> <port>
 * 本机已实测：PASS 3/3
 */
import io.netty.bootstrap.Bootstrap;
import io.netty.buffer.ByteBuf;
import io.netty.buffer.Unpooled;
import io.netty.channel.Channel;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelInboundHandlerAdapter;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioSocketChannel;
import io.netty.handler.codec.LineBasedFrameDecoder;
import io.netty.handler.codec.string.StringDecoder;
import io.netty.handler.codec.string.StringEncoder;

import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.Queue;

public final class UpperClient {

    private static final String[] LINES = {"hello tenet", "netty line codec", "bye"};
    private static final Queue<String> expected = new ArrayDeque<>(java.util.Arrays.asList(LINES));
    private static int passes = 0;

    public static void main(String[] args) throws Exception {
        String host = args.length > 0 ? args[0] : "127.0.0.1";
        int port = args.length > 1 ? Integer.parseInt(args[1]) : 18081;
        EventLoopGroup group = new NioEventLoopGroup();
        try {
            Bootstrap b = new Bootstrap();
            b.group(group)
                    .channel(NioSocketChannel.class)
                    .handler(new ChannelInitializer<SocketChannel>() {
                        @Override
                        protected void initChannel(SocketChannel ch) {
                            ch.pipeline()
                                    .addLast(new LineBasedFrameDecoder(8192))
                                    .addLast(new StringDecoder(StandardCharsets.UTF_8))
                                    .addLast(new StringEncoder(StandardCharsets.UTF_8))
                                    .addLast(new ChannelInboundHandlerAdapter() {
                                        @Override
                                        public void channelRead(ChannelHandlerContext ctx, Object msg) {
                                            String echo = ((String) msg).trim();
                                            String want = expected.poll();
                                            check(echo.equals(want.toUpperCase()),
                                                    "收到「" + echo + "」== 期望「" + want.toUpperCase() + "」");
                                            if (expected.isEmpty()) {
                                                ctx.close();       // 全部收到，关闭连接
                                            }
                                        }
                                    });
                        }
                    });
            Channel ch = b.connect(host, port).sync().channel();
            for (String line : LINES) {
                ch.writeAndFlush(line + "\n");                    // 逐行发送
            }
            ch.closeFuture().sync();
        } finally {
            group.shutdownGracefully().sync();
        }
        System.out.println(passes == LINES.length ? "ALL PASS: 3/3" : "ALL PASS 失败");
    }

    private static void check(boolean cond, String msg) {
        System.out.println((cond ? "PASS: " : "FAIL: ") + msg);
        if (cond) {
            passes++;
        } else {
            System.exit(1);
        }
    }
}
