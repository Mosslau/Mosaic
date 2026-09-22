// exercises/sol-02-service-handmade-test.java —— 练习 2 参考实现：手工 fake 替身测 Service
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + JUnit Jupiter 5.10.1（本机离线模式 mvn -o）
// 验证状态：已验证（pom 与下述全部源码放入临时工程后 mvn -o clean test, BUILD SUCCESS）
// 实测结果：Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// ---------------------------------------------------------------------------
// 本练习的 pom.xml（写入工程根目录 pom.xml）: 与 sol-01 相同（junit-jupiter 5.10.1 + surefire 3.2.5），
// 本练习不需要任何 mock 框架 —— 替身是手工写的接口实现。
//
// 测试辅助类（src/test/java/com/example/FakeUserRepository.java）:
//
//   package com.example;
//   import java.util.HashMap;
//   import java.util.Map;
//   import java.util.Optional;
//
//   /** 手工 fake：内存 Map 实现的「数据库」，id 为 0 时自动分配。零框架依赖。 */
//   final class FakeUserRepository implements UserRepository {
//       final Map<Long, User> store = new HashMap<>();
//       final Map<String, Long> emailToId = new HashMap<>();
//       private long nextId = 1;
//
//       @Override public Optional<User> findById(long id) { return Optional.ofNullable(store.get(id)); }
//       @Override public boolean existsByEmail(String email) { return emailToId.containsKey(email); }
//       @Override public void save(User user) {
//           long id = user.id() == 0 ? nextId++ : user.id();
//           User stored = new User(id, user.name(), user.email());
//           store.put(id, stored);
//           emailToId.put(stored.email(), id);
//       }
//   }
//
// 测试类（src/test/java/com/example/UserServiceFakeTest.java）:
//
//   package com.example;
//   import org.junit.jupiter.api.BeforeEach;
//   import org.junit.jupiter.api.Test;
//   import java.util.Optional;
//   import static org.junit.jupiter.api.Assertions.assertEquals;
//   import static org.junit.jupiter.api.Assertions.assertThrows;
//   import static org.junit.jupiter.api.Assertions.assertTrue;
//
//   class UserServiceFakeTest {
//       private FakeUserRepository fake;
//       private UserService service;
//
//       @BeforeEach void setUp() {
//           fake = new FakeUserRepository();
//           service = new UserService(fake);
//       }
//
//       @Test void greeting_returnsHello_whenUserExists() {
//           fake.store.put(1L, new User(1L, "mosslau", "m@x.com"));
//           assertEquals("Hello, mosslau!", service.greeting(1L));
//       }
//       @Test void greeting_throws_whenUserMissing() {
//           assertEquals("用户不存在: 99",
//                   assertThrows(IllegalArgumentException.class, () -> service.greeting(99L)).getMessage());
//       }
//       @Test void register_savesNewUser_thenFindable() {
//           service.register(new User(0L, "new", "new@x.com"));
//           Optional<User> saved = fake.findById(1L);   // fake 自动分配 id=1
//           assertTrue(saved.isPresent());
//           assertEquals("new", saved.get().name());
//       }
//       @Test void register_rejectsDuplicateEmail() {
//           fake.emailToId.put("dup@x.com", 1L);
//           assertThrows(IllegalArgumentException.class,
//                   () -> service.register(new User(0L, "dup", "dup@x.com")));
//           assertEquals(0, fake.store.size(), "重复邮箱不应落库");
//       }
//       @Test void register_keepsProvidedId() {
//           service.register(new User(42L, "fixed", "fixed@x.com"));
//           assertEquals("fixed", fake.findById(42L).orElseThrow().name());
//       }
//   }
//
// 目录结构（src/main/java/com/example/）:
//   User.java / UserRepository.java / UserService.java —— 直接取自主文档 3.3 的
//   examples/ex03-mockito（接口与方法签名完全一致，本文件里的 User.java 与之等价）；
//   本练习的核心是「手工 fake 替身 + 状态验证」，业务类不是重点，抄 ex03 即可
// 编译/运行命令（工程根目录）:
//   1. mvn clean test
//       # 实测: Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
// 要点：
//   - fake 是「能工作的替身」：内存 Map 真的存了数据，测试用 fake 的内部状态做断言 —— 这叫状态验证
//   - 与 Mockito 的差别（练习 3）：mock 是「规定返回值 + 验证交互」（行为验证），fake 是「真实现 + 看状态」
//   - 工程里 fake 通常放 src/test/java，不污染生产代码；接口抽象（依赖倒置）是替身能插进来的前提
// ---------------------------------------------------------------------------
package com.example;

import java.util.Optional;

/** 用户实体（record）。id 为 0 表示「未分配」，由存储层落库时分配。 */
public record User(long id, String name, String email) {
}
