/*
 * examples/ex08-netty-echo/EchoServer.java
 * Netty Echo Server（TCP）：演示 Netty 编程的核心三件套——
 *   ① EventLoopGroup 线程模型（boss 组管 accept、worker 组管读写，见主文档 4.3/3.9）；
 *   ② ServerBootstrap + ChannelInitializer 装配 pipeline；
 *   ③ 处理器链上「读到的 ByteBuf 原样写回」即完成 echo。
 *
 * 验证环境：OpenJDK 17.0.18 + netty 4.1.137.Final（从 Maven Central 拉取模块 jar，见 README）
 * 编译：javac -encoding UTF-8 -cp "<jar 目录>/*" -d /tmp/tl20-cls EchoServer.java EchoClient.java
 * 运行（终端 1）：java -cp "/tmp/tl20-cls:<jar 目录>/*" EchoServer 18080
 * 运行（终端 2）：java -cp "/tmp/tl20-cls:<jar 目录>/*" EchoClient 127.0.0.1 18080
 * 本机已实测：server 启动 + client 收到逐字 echo（输出 ECHO OK），两进程正常优雅退出
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

public final class EchoServer {

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 18080;
        EventLoopGroup boss = new NioEventLoopGroup(1);      // 1 个线程只负责 accept 新连接
        EventLoopGroup worker = new NioEventLoopGroup();     // 默认 2×CPU 个线程负责各连接的读写
        try {
            ServerBootstrap b = new ServerBootstrap();
            b.group(boss, worker)
                    .channel(NioServerSocketChannel.class)          // 基于 JDK NIO 的 ServerSocketChannel
                    .childHandler(new ChannelInitializer<SocketChannel>() {   // 每个新连接初始化一条 pipeline
                        @Override
                        protected void initChannel(SocketChannel ch) {
                            ch.pipeline().addLast(new ChannelInboundHandlerAdapter() {
                                @Override
                                public void channelRead(ChannelHandlerContext ctx, Object msg) {
                                    ctx.writeAndFlush(msg);        // echo：读到的数据原样写回（无需 new ByteBuf）
                                }
                            });
                        }
                    });
            ChannelFuture f = b.bind(port).sync();                  // 绑定并阻塞到完成
            System.out.println("EchoServer started on " + port);
            f.channel().closeFuture().sync();                       // 阻塞直到 server channel 关闭
        } finally {
            boss.shutdownGracefully().sync();                       // 优雅关闭两个线程组
            worker.shutdownGracefully().sync();
        }
    }
}
