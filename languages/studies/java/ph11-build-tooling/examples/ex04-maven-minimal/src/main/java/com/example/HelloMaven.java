// examples/ex04-maven-minimal/src/main/java/com/example/HelloMaven.java —— 最小 Maven 工程的唯一类
// 目录结构约定（Maven 的「约定优于配置」）：主代码必须在 src/main/java, 测试在 src/test/java
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12；验证状态：已验证
// 编译/运行命令（工程根目录 examples/ex04-maven-minimal/）:
//   1. mvn clean package                # 实测 BUILD SUCCESS, 产物 target/hello-maven.jar（2552 字节）
//   2. java -jar target/hello-maven.jar # 实测输出: hello maven
//   3. 查看清单：unzip -p target/hello-maven.jar META-INF/MANIFEST.MF 含 "Main-Class: com.example.HelloMaven"
//   4. 产物清理：mvn clean
package com.example;

public class HelloMaven {
    public static void main(String[] args) {
        System.out.println("hello maven");
    }
}
