package com.example;

import java.io.BufferedInputStream;
import java.io.BufferedOutputStream;
import java.io.IOException;
import java.net.Socket;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.List;

/**
 * 零依赖的 Redis 客户端：直接在本机 Socket 上讲 RESP2 协议。
 * 教学目的——Jedis/Lettuce 的底层就是这件事：
 *   请求  = *N\r\n + 每个参数 $<len>\r\n<bytes>\r\n   （批量字符串数组）
 *   响应  = +简单串 / -错误 / :整数 / $批量串 / *数组  （首字节定类型）
 */
public class RespClient implements AutoCloseable {

    private final Socket socket;
    private final BufferedInputStream in;
    private final BufferedOutputStream out;

    public RespClient(String host, int port) throws IOException {
        this.socket = new Socket(host, port);
        this.in = new BufferedInputStream(socket.getInputStream());
        this.out = new BufferedOutputStream(socket.getOutputStream());
    }

    /** 发送一条命令并读回响应（同步一问一答，Redis 协议就是这么简单） */
    public Object command(String... args) throws IOException {
        StringBuilder sb = new StringBuilder();
        sb.append('*').append(args.length).append("\r\n");
        for (String arg : args) {
            byte[] bytes = arg.getBytes(StandardCharsets.UTF_8);
            sb.append('$').append(bytes.length).append("\r\n");
            out.write(sb.toString().getBytes(StandardCharsets.UTF_8));
            sb.setLength(0);
            out.write(bytes);
            out.write("\r\n".getBytes(StandardCharsets.UTF_8));
        }
        out.flush();
        return readReply();
    }

    public String set(String key, String value) throws IOException {
        return (String) command("SET", key, value);   // +OK
    }

    public String get(String key) throws IOException {
        return (String) command("GET", key);          // $n 批量串；不存在为 null
    }

    public long del(String key) throws IOException {
        return (Long) command("DEL", key);            // :n 整数
    }

    public long expire(String key, int seconds) throws IOException {
        return (Long) command("EXPIRE", key, String.valueOf(seconds));
    }

    public long ttl(String key) throws IOException {
        return (Long) command("TTL", key);            // 剩余秒数；-1 无过期；-2 不存在
    }

    public String ping() throws IOException {
        return (String) command("PING");              // +PONG
    }

    /** 按首字节解析 RESP 响应（递归处理数组） */
    private Object readReply() throws IOException {
        int type = in.read();
        if (type == -1) {
            throw new IOException("连接被服务端关闭");
        }
        return switch ((char) type) {
            case '+' -> readLine();                              // 简单字符串
            case '-' -> throw new IOException("Redis 错误: " + readLine());
            case ':' -> Long.parseLong(readLine());              // 整数
            case '$' -> {                                        // 批量字符串
                int len = Integer.parseInt(readLine());
                if (len == -1) {
                    yield null;                                  // nil（键不存在）
                }
                byte[] buf = in.readNBytes(len);
                in.readNBytes(2);                                // 吃掉结尾 \r\n
                yield new String(buf, StandardCharsets.UTF_8);
            }
            case '*' -> {                                        // 数组
                int count = Integer.parseInt(readLine());
                List<Object> items = new ArrayList<>(count);
                for (int i = 0; i < count; i++) {
                    items.add(readReply());
                }
                yield items;
            }
            default -> throw new IOException("未知 RESP 类型字节: " + (char) type);
        };
    }

    private String readLine() throws IOException {
        StringBuilder sb = new StringBuilder();
        int prev = -1;
        int c;
        while ((c = in.read()) != -1) {
            if (prev == '\r' && c == '\n') {
                return sb.substring(0, sb.length() - 1);
            }
            sb.append((char) c);
            prev = c;
        }
        throw new IOException("读响应时连接中断");
    }

    @Override
    public void close() throws IOException {
        socket.close();
    }
}
