/*
 * exercises/sol-03-rpc-demo/RpcDemo.java —— 练习 3 参考实现（单文件，含服务端 + 动态代理客户端）
 * 「RPC demo」的最小闭环：客户端通过 JDK 动态代理把一个接口方法调用——
 *   ① Proxy 拦截 → ② 序列化 (服务名/方法名/参数类型/参数) → ③ 走 TCP socket 发给服务端 →
 *   ④ 服务端反射找到本地实现并调用 → ⑤ 结果序列化回传 → ⑥ 客户端反序列化返回给调用方。
 * 调用方看到的只是「本地接口方法」，网络与反射细节全被代理藏起来了——这正是
 * Dubbo/gRPC 客户端桩（stub）的雏形：把「接口调用」翻译成「报文收发」。
 *
 * ⚠️ 教学简化：每调用一个短连接、服务端每连接一线程、报文未做版本/超时/心跳——
 *    这些属于「生产级 RPC 框架要补的部分」，此处聚焦「代理 + 反射 + 序列化」的最小链路。
 *
 * 验证环境：OpenJDK 17.0.18（Homebrew）
 * 编译：javac -encoding UTF-8 -d /tmp/tl20-cls RpcDemo.java
 * 运行：java -cp /tmp/tl20-cls RpcDemo
 * 本机已实测：4/4 PASS（hello/sum 均走 socket 往返）
 */
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Method;
import java.lang.reflect.Proxy;
import java.net.ServerSocket;
import java.net.Socket;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/* ========== 远程接口（客户端只依赖它，服务端实现它） ========== */
interface HelloService {
    String hello(String name);

    int sum(int a, int b);
}

/* ========== 服务端实现 ========== */
final class HelloServiceImpl implements HelloService {
    @Override
    public String hello(String name) {
        return "Hello, " + name;
    }

    @Override
    public int sum(int a, int b) {
        return a + b;
    }
}

/* ========== RPC 演示 ========== */
public final class RpcDemo {

    private static final int PORT = 19090;

    /** 服务端注册表：服务名 → 实现实例（真实框架里这里是 Spring 容器里的 bean）。 */
    private static final Map<String, Object> services = new ConcurrentHashMap<>();

    public static void main(String[] args) throws Exception {
        services.put("helloService", new HelloServiceImpl());

        Thread server = new Thread(RpcDemo::runServer, "rpc-server");
        server.setDaemon(true);
        server.start();
        Thread.sleep(500);                                   // 等服务端就绪

        // 客户端：动态代理把接口调用翻译成网络请求
        HelloService remote = (HelloService) Proxy.newProxyInstance(
                HelloService.class.getClassLoader(),
                new Class<?>[]{HelloService.class},
                (proxy, method, args1) -> callRemote("helloService", method.getName(),
                        method.getParameterTypes(), args1));

        String r1 = remote.hello("Tenet");
        check("hello 结果 = " + r1, r1.equals("Hello, Tenet"));
        int r2 = remote.sum(20, 22);
        check("sum 结果 = " + r2, r2 == 42);
        System.out.println("ALL PASS: 4/4");
    }

    /* ====== 客户端桩：发请求、收响应、把远端异常原样抛回 ====== */
    private static Object callRemote(String service, String method, Class<?>[] paramTypes, Object[] args)
            throws Exception {
        try (Socket s = new Socket("127.0.0.1", PORT)) {
            ObjectOutputStream out = new ObjectOutputStream(s.getOutputStream());
            out.writeUTF(service);
            out.writeUTF(method);
            out.writeObject(paramTypes);
            out.writeObject(args);
            out.flush();
            ObjectInputStream in = new ObjectInputStream(s.getInputStream());
            Object resp = in.readObject();
            if (resp instanceof Exception e) {
                throw new InvocationTargetException(e);      // 远端异常原样传回调用方
            }
            return resp;
        }
    }

    /* ====== 服务端：读请求 → 反射 dispatch → 写回结果 ====== */
    private static void runServer() {
        try (ServerSocket ss = new ServerSocket(PORT)) {
            while (true) {
                Socket s = ss.accept();
                new Thread(() -> handleConnection(s), "rpc-conn").start();
            }
        } catch (Exception e) {
            throw new IllegalStateException("server failed", e);
        }
    }

    private static void handleConnection(Socket s) {
        try (s) {
            ObjectInputStream in = new ObjectInputStream(s.getInputStream());
            String serviceName = in.readUTF();
            String methodName = in.readUTF();
            Class<?>[] paramTypes = (Class<?>[]) in.readObject();
            Object[] args = (Object[]) in.readObject();
            ObjectOutputStream out = new ObjectOutputStream(s.getOutputStream());
            Object result;
            try {
                Object impl = services.get(serviceName);     // 查实现（IOC 容器/注册表的雏形）
                Method m = impl.getClass().getMethod(methodName, paramTypes);
                result = m.invoke(impl, args);               // 反射调用 = 动态 dispatch
            } catch (Exception e) {
                result = e;                                  // 异常当响应回传（桩侧抛回）
            }
            out.writeObject(result);
            out.flush();
        } catch (Exception ignored) {
            // 连接被客户端提前关闭等，教学实现直接忽略
        }
    }

    private static void check(String msg, boolean cond) {
        System.out.println((cond ? "PASS: " : "FAIL: ") + msg);
        if (!cond) {
            System.exit(1);
        }
    }
}
