// exercises/sol-03-service-mockito-test.java —— 练习 3 参考实现：Mockito 隔离外部依赖
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Mockito 5.11.0（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与下述全部源码放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// 实测结果：Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）:
//
//   <project xmlns="http://maven.apache.org/POM/4.0.0">
//     <modelVersion>4.0.0</modelVersion>
//     <groupId>com.example</groupId>
//     <artifactId>sol03-service-mockito</artifactId>
//     <version>1.0-SNAPSHOT</version>
//     <properties>
//       <maven.compiler.release>17</maven.compiler.release>
//       <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>
//     </properties>
//     <dependencies>
//       <dependency>
//         <groupId>org.junit.jupiter</groupId>
//         <artifactId>junit-jupiter</artifactId>
//         <version>5.10.1</version>
//         <scope>test</scope>
//       </dependency>
//       <dependency>
//         <groupId>org.mockito</groupId>
//         <artifactId>mockito-core</artifactId>
//         <version>5.11.0</version>
//         <scope>test</scope>
//       </dependency>
//       <dependency>
//         <groupId>org.mockito</groupId>
//         <artifactId>mockito-junit-jupiter</artifactId>
//         <version>5.11.0</version>
//         <scope>test</scope>
//       </dependency>
//       <!-- 离线版本仲裁：mockito 5.11.0 声明 byte-buddy 1.14.12 / objenesis 3.3，
//            本地缓存只有 1.14.13 / 3.2（机制见 ph11 4.3）；正常联网环境可删除这三项 -->
//       <dependency>
//         <groupId>net.bytebuddy</groupId>
//         <artifactId>byte-buddy</artifactId>
//         <version>1.14.13</version>
//         <scope>test</scope>
//       </dependency>
//       <dependency>
//         <groupId>net.bytebuddy</groupId>
//         <artifactId>byte-buddy-agent</artifactId>
//         <version>1.14.13</version>
//         <scope>test</scope>
//       </dependency>
//       <dependency>
//         <groupId>org.objenesis</groupId>
//         <artifactId>objenesis</artifactId>
//         <version>3.2</version>
//         <scope>test</scope>
//       </dependency>
//     </dependencies>
//     <build>
//       <plugins>
//         <plugin>
//           <groupId>org.apache.maven.plugins</groupId>
//           <artifactId>maven-surefire-plugin</artifactId>
//           <version>3.2.5</version>
//         </plugin>
//       </plugins>
//     </build>
//   </project>
//
// 业务类（src/main/java/com/example/，与练习 2 共用同一组设计）:
//   User.java        —— record User(long id, String name, String email)
//   UserRepository.java —— interface { Optional<User> findById(long); boolean existsByEmail(String); void save(User); }
//   UserService.java —— 构造器注入 repo；greeting(id) 用户存在返回问候否则抛 IllegalArgumentException；
//                       register(user) 邮箱重复抛异常否则 repo.save
//
// 测试类（src/test/java/com/example/UserServiceMockitoTest.java）:
//
//   package com.example;
//   import org.junit.jupiter.api.BeforeEach;
//   import org.junit.jupiter.api.Test;
//   import org.junit.jupiter.api.extension.ExtendWith;
//   import org.mockito.Mock;
//   import org.mockito.junit.jupiter.MockitoExtension;
//   import java.util.Optional;
//   import static org.junit.jupiter.api.Assertions.assertEquals;
//   import static org.junit.jupiter.api.Assertions.assertThrows;
//   import static org.mockito.ArgumentMatchers.any;
//   import static org.mockito.ArgumentMatchers.argThat;
//   import static org.mockito.Mockito.never;
//   import static org.mockito.Mockito.times;
//   import static org.mockito.Mockito.verify;
//   import static org.mockito.Mockito.when;
//
//   @ExtendWith(MockitoExtension.class)
//   class UserServiceMockitoTest {
//       @Mock private UserRepository repo;
//       private UserService service;
//
//       @BeforeEach void setUp() { service = new UserService(repo); }
//
//       @Test void greeting_returnsHello_whenUserExists() {
//           when(repo.findById(1L)).thenReturn(Optional.of(new User(1L, "mosslau", "m@x.com")));
//           assertEquals("Hello, mosslau!", service.greeting(1L));
//           verify(repo).findById(1L);
//       }
//       @Test void greeting_throws_whenUserMissing() {
//           when(repo.findById(99L)).thenReturn(Optional.empty());
//           assertEquals("用户不存在: 99",
//                   assertThrows(IllegalArgumentException.class, () -> service.greeting(99L)).getMessage());
//       }
//       @Test void register_rejectsDuplicateEmail_withoutSaving() {
//           when(repo.existsByEmail("dup@x.com")).thenReturn(true);
//           assertThrows(IllegalArgumentException.class,
//                   () -> service.register(new User(0L, "dup", "dup@x.com")));
//           verify(repo, never()).save(any());
//       }
//       @Test void register_savesWithNameMatch() {
//           when(repo.existsByEmail("new@x.com")).thenReturn(false);
//           service.register(new User(0L, "new", "new@x.com"));
//           verify(repo, times(1)).save(argThat(u -> u.name().equals("new")));
//       }
//       @Test void repositoryFailure_isPropagated() {
//           when(repo.findById(1L)).thenThrow(new RuntimeException("数据库连接失败"));
//           assertThrows(RuntimeException.class, () -> service.greeting(1L));
//       }
//   }
//
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - when(...).thenReturn(...) 是 stub（规定返回值）；verify(...) 是验证交互（行为验证）
//   - verify(repo, never()).save(...) 验证「没有发生」——比只看返回值更严格
//   - argThat(...) 做参数匹配，验证「以什么参数调用了」；thenThrow 模拟外部故障传播
//   - 为什么用 mock 而不是连真库：单元测试要快、要确定、要能覆盖错误路径（数据库挂掉这种场景连真库复现不了）
// ---------------------------------------------------------------------------
package com.example;

import java.util.Optional;

/** 业务服务：依赖 UserRepository（构造器注入），被测对象本身不含任何外部调用。 */
public class UserService {

    private final UserRepository repo;

    public UserService(UserRepository repo) {
        this.repo = repo;
    }

    public String greeting(long id) {
        return repo.findById(id)
                .map(u -> "Hello, " + u.name() + "!")
                .orElseThrow(() -> new IllegalArgumentException("用户不存在: " + id));
    }

    public void register(User user) {
        if (repo.existsByEmail(user.email())) {
            throw new IllegalArgumentException("邮箱已注册: " + user.email());
        }
        repo.save(user);
    }
}
