// examples/ex02-servlet-tomcat/src/main/java/com/example/Main.java —— 嵌入式 Tomcat 启动器
// 验证环境：OpenJDK 17.0.18 + Tomcat 10.1.31（tomcat-embed-core）
// 验证状态：已验证（本机实测，见 README）
// ---------------------------------------------------------------------------
// 教学点：生产里 Tomcat 是独立进程（Servlet 容器），这里用「嵌入式」模式在 main 里
// 直接 new Tomcat() 起服务——这正是 Spring Boot 内嵌 Tomcat 的底层机制。
// addContext + addServlet + addServletMapping 三件套 = 把 Servlet 挂到容器上；
// 用注解 @WebServlet 时 Tomcat 会自动扫描注册，addServletMappingDecoded 是为了显式演示。
package com.example;

import org.apache.catalina.Context;
import org.apache.catalina.startup.Tomcat;

import java.io.File;

/** 嵌入式 Tomcat：main 方法里启动一个带 EchoServlet 的 HTTP 服务。 */
public final class Main {

    public static void main(String[] args) throws Exception {
        int port = args.length > 0 ? Integer.parseInt(args[0]) : 18081;
        Tomcat tomcat = new Tomcat();
        tomcat.setPort(port);
        tomcat.getConnector(); // 显式初始化连接器

        Context ctx = tomcat.addContext("", new File(".").getAbsolutePath());
        // 显式注册 Servlet + 映射：addServlet 绑定实例，addServletMappingDecoded 指定 URL 模式。
        // 生产部署（war 进独立 Tomcat）时用 @WebServlet 注解即可自动注册；嵌入式从 classpath
        // 起服务没有 WEB-INF/classes 布局，注解扫描不触发，故这里显式注册（等效于注解做的事）。
        Tomcat.addServlet(ctx, "echo", new EchoServlet());
        ctx.addServletMappingDecoded("/echo/*", "echo");
        tomcat.start();
        System.out.println("embedded Tomcat listening on http://127.0.0.1:" + port + "/echo/hello");
        tomcat.getServer().await(); // 阻塞直到关闭
    }
}
