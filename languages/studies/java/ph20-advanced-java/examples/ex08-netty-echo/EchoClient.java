/*
 * examples/ex08-netty-echo/EchoClient.java
 * Netty Echo Client：连上 server 后发一条消息，收到逐字 echo 即 PASS。
 * 注意：为了演示「一个 channel 多条消息共享同一 handler」，这里每连接只发一条并退出。
 *
 * 验证环境：OpenJDK 17.0.18 + netty 4.1.137.Final
 * 编译：javac -encoding UTF-8 -cp "<jar 目录>/*" -d /tmp/tl20-cls EchoServer.java EchoClient.java
 * 运行：java -cp "/tmp/tl20-cls:<jar 目录>/*" EchoClient <host> <port>
 * 本机已实测：ECHO OK（返回内容与发送内容逐字节一致）
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

import java.nio.charset.StandardCharsets;

public final class EchoClient {

    public static void main(String[] args) throws Exception {
        String host = args.length > 0 ? args[0] : "127.0.0.1";
        int port = args.length > 1 ? Integer.parseInt(args[1]) : 18080;
        EventLoopGroup group = new NioEventLoopGroup();
        try {
            Bootstrap b = new Bootstrap();
            b.group(group)
                    .channel(NioSocketChannel.class)
                    .handler(new ChannelInitializer<SocketChannel>() {
                        @Override
                        protected void initChannel(SocketChannel ch) {
                            ch.pipeline().addLast(new ChannelInboundHandlerAdapter() {
                                @Override
                                public void channelRead(ChannelHandlerContext ctx, Object msg) {
                                    ByteBuf in = (ByteBuf) msg;
                                    String echo = in.toString(StandardCharsets.UTF_8);
                                    System.out.println("ECHO received: " + echo);
                                    System.out.println(echo.equals(PING) ? "PASS: ECHO OK" : "FAIL: 内容不一致");
                                    ctx.close();                    // 收到后关闭连接
                                }
                            });
                        }
                    });
            Channel ch = b.connect(host, port).sync().channel();
            System.out.println("sending: " + PING);
            ch.writeAndFlush(Unpooled.copiedBuffer(PING, StandardCharsets.UTF_8)).sync();
            ch.closeFuture().sync();                                 // 等服务器 echo 回并关闭
        } finally {
            group.shutdownGracefully().sync();
        }
    }

    private static final String PING = "hello netty " + System.currentTimeMillis();
}
