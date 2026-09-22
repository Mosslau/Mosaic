// examples/ex09-netty-gateway/GatewayServer.java —— Netty 车载长连接网关(接入服务底层形态)
// 验证环境：OpenJDK 17.0.18 + netty-all 4.1.49.Final(本机 jar 位于
//   ~/.m2/repository.bak/io/netty/netty-all/4.1.49.Final/netty-all-4.1.49.Final.jar，
//   无 mvn 环境可用 `mvn dependency:copy` 或从 Maven Central 手动拉同名 jar)。
//
// 教学点(兑现 ph20 Netty 预告)：车端 TCP 长连接网关 = Netty 的典型舞台。本类演示两个核心：
//   1. 主从 Reactor：bossGroup 负责 accept，workerGroup 负责每条连接的读写；
//      同一连接的全部事件绑定到同一 EventLoop → handler 无需加锁(ph20 ex08 已实测过 echo)；
//   2. pipeline 挂 codec：LineBasedFrameDecoder 处理粘包/半包(车端一行一帧)，
//      StringDecoder/StringEncoder 完成 ByteBuf ↔ String，业务 handler 收到完整行。
//
// 协议(教学简化版，一行一命令，`\n` 结尾)：
//   REG|<VIN>            —— 连接注册(车辆上线)
//   HB|<VIN>|<seq>       —— 心跳 + 遥测序号推进
//   网关回 ACK|<原文> 或 ERR|<原因>；实时在线表用 ConcurrentHashMap 维护。
import io.netty.bootstrap.ServerBootstrap;
import io.netty.channel.Channel;
import io.netty.channel.ChannelHandlerContext;
import io.netty.channel.ChannelInitializer;
import io.netty.channel.ChannelOption;
import io.netty.channel.SimpleChannelInboundHandler;
import io.netty.channel.nio.NioEventLoopGroup;
import io.netty.channel.socket.SocketChannel;
import io.netty.channel.socket.nio.NioServerSocketChannel;
import io.netty.handler.codec.LineBasedFrameDecoder;
import io.netty.handler.codec.string.StringDecoder;
import io.netty.handler.codec.string.StringEncoder;

import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.ConcurrentHashMap;

public final class GatewayServer {
    /** 在线表：VIN → 最近心跳 seq。仅在事件线程写，但可被管理线程读(弱一致可接受)。 */
    private final ConcurrentHashMap<String, Long> online = new ConcurrentHashMap<>();
    private NioEventLoopGroup boss;
    private NioEventLoopGroup worker;
    private Channel serverChannel;

    /** 启动网关并绑定到随机空闲端口，返回实际端口号(便于测试免冲突)。 */
    public int start() throws InterruptedException {
        boss = new NioEventLoopGroup(1);                 // boss：只 accept
        worker = new NioEventLoopGroup(2);               // worker：读写(生产按 CPU 核数定)
        try {
            ServerBootstrap b = new ServerBootstrap();
            b.group(boss, worker)
             .channel(NioServerSocketChannel.class)
             .childOption(ChannelOption.TCP_NODELAY, true)
             .childHandler(new ChannelInitializer<SocketChannel>() {
                 @Override protected void initChannel(SocketChannel ch) {
                     ch.pipeline()
                       .addLast(new LineBasedFrameDecoder(4096))        // 按 \n 切帧：消化粘包/半包
                       .addLast(new StringDecoder(StandardCharsets.UTF_8))
                       .addLast(new StringEncoder(StandardCharsets.UTF_8))
                       .addLast(new GatewayHandler());
                 }
             });
            serverChannel = b.bind(0).sync().channel();   // bind 端口 0 = 随机端口
            return ((InetSocketAddress) serverChannel.localAddress()).getPort();
        } catch (InterruptedException e) {
            stop();
            throw e;
        }
    }

    public void stop() {
        if (serverChannel != null) {
            serverChannel.close();
        }
        if (boss != null) {
            boss.shutdownGracefully();
        }
        if (worker != null) {
            worker.shutdownGracefully();
        }
    }

    public int onlineCount() { return online.size(); }

    private final class GatewayHandler extends SimpleChannelInboundHandler<String> {
        @Override protected void channelRead0(ChannelHandlerContext ctx, String line) {
            // 同一连接的读写全在同一个 EventLoop 线程上 → 这里无需再加锁
            String[] p = line.split("\\|");
            String reply;
            if (p.length == 2 && "REG".equals(p[0]) && p[1].startsWith("LSV")) {
                online.put(p[1], 0L);
                reply = "ACK|REG " + p[1];
            } else if (p.length == 3 && "HB".equals(p[0]) && online.containsKey(p[1])) {
                long seq = Long.parseLong(p[2]);
                online.put(p[1], Math.max(online.getOrDefault(p[1], 0L), seq));   // 心跳推进
                reply = "ACK|HB " + p[1] + " " + seq;
            } else {
                reply = "ERR|bad-command:" + line;
            }
            ctx.writeAndFlush(reply + "\n");
        }

        @Override public void channelInactive(ChannelHandlerContext ctx) {
            // 断连需从在线表摘除；为演示简单这里不追踪 channel→vin 映射，
            // 真实网关用 ChannelGroup + attribute(vin) 做精确下线，见主文档 4.1。
        }
    }
}
