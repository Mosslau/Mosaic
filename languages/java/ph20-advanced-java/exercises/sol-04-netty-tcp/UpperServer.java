/*
 * exercises/sol-04-netty-tcp/UpperServer.java —— 练习 4 参考实现（服务端）
 * ex08 只做了原始 ByteBuf 的 echo；本题要求一个可服务多个客户端、按「行」处理的 TCP server。
 * 解法 = ex08 的骨架 + 两行 codec 装配：
 *   LineBasedFrameDecoder(8192)  按 \n 把字节流切成一帧一行
 *   StringDecoder/StringEncoder  ByteBuf ↔ String 互转（来自 netty-codec）
 * 于是业务 handler 直接收到 String、返回 String——这就是 Netty「把字节细节交给 codec 链」的用法。
 *
 * 验证环境：OpenJDK 17.0.18 + netty 4.1.137.Final（jar 拉取步骤见 examples/ex08-netty-echo/README.md）
 * 编译：javac -encoding UTF-8 -cp "<jar 目录>/*" -d /tmp/tl20-cls UpperServer.java UpperClient.java
 * 运行（终端 1）：java -cp "/tmp/tl20-cls:<jar 目录>/*" UpperServer 18081
 * 运行（终端 2）：java -cp "/tmp/tl20-cls:<jar 目录>/*" UpperClient 127.0.0.1 18081
 * 本机已实测：client 发 3 行，server 逐行回大写，全部逐字匹配（PASS 3/3）
 */
import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.ChannelFuture;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelInboundHandlerAdapter;
import io.netty.channel.EventLoopGroup;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.codec.LineBasedFrameDecoder;
import io.netty.handler.codec.string.StringDecoder;
import io.netty.handler.codec.string.StringEncoder;

import java.nio.charset.StandardCharsets;

public final class UpperServer {

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 18081;
        EventLoopGroup boss = new NioEventLoopGroup(1);
        EventLoopGroup worker = new NioEventLoopGroup();
        try {
            ServerBootstrap b = new ServerBootstrap();
            b.group(boss, worker)
                    .channel(NioServerSocketChannel.class)
                    .childHandler(new ChannelInitializer<SocketChannel>() {
                        @Override
                        protected void initChannel(SocketChannel ch) {
                            ch.pipeline()
                                    .addLast(new LineBasedFrameDecoder(8192))   // 按行切帧（粘包/半包交给它）
                                    .addLast(new StringDecoder(StandardCharsets.UTF_8))
                                    .addLast(new StringEncoder(StandardCharsets.UTF_8))
                                    .addLast(new ChannelInboundHandlerAdapter() {
                                        @Override
                                        public void channelRead(ChannelHandlerContext ctx, Object msg) {
                                            String line = (String) msg;         // 已经是完整一行 String
                                            ctx.writeAndFlush(line.toUpperCase() + "\n");  // 大写回写
                                        }
                                    });
                        }
                    });
            ChannelFuture f = b.bind(port).sync();
            System.out.println("UpperServer started on " + port + "（发来的每一行将原样转大写回传）");
            f.channel().closeFuture().sync();
        } finally {
            boss.shutdownGracefully().sync();
            worker.shutdownGracefully().sync();
        }
    }
}
