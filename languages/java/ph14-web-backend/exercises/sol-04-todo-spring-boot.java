// exercises/sol-04-todo-spring-boot.java —— 练习 4 参考实现：Spring Boot Todo API + MockMvc 测试
// 验证环境：OpenJDK 17.0.18 + Maven 3.9.12 + Spring Boot 3.3.0 + JUnit Jupiter 5.10.2
// 验证状态：已验证（本机离线 mvn -o test，BUILD SUCCESS）
// 实测结果：Tests run: 6, Failures: 0, Errors: 0, Skipped: 0
//   （createTodo / listTodos / markDone / deleteTodo / validateTitle / uploadFile 六用例全过；
//     validateTitle 断言 400 + 业务码 40004，由控制器内联 @ExceptionHandler 兜底）
// ---------------------------------------------------------------------------
// 本练习的 pom.xml 与三个源文件（写入标准 Maven 工程）：
//   src/main/java/com/example/App.java            —— @SpringBootApplication 启动类
//   src/main/java/com/example/TodoController.java —— 本文件内容
//   src/main/java/com/example/ApiResponse.java    —— 统一响应（同 examples/ex05，含 ok/error 两个静态工厂）
//   src/test/java/com/example/TodoControllerTest.java —— 测试类（见文末注释）
//
// pom.xml 直接复制 ../examples/ex04-spring-boot-rest/pom.xml（含离线版本仲裁注释）即可，
// artifactId 改成 sol04-todo-spring-boot；再补 src/main/resources/application.properties：
//   server.port=18088
//
// 编译与测试：mvn -o -Dmaven.repo.local=/tmp/m2clone test
// 运行：mvn -o -Dmaven.repo.local=/tmp/m2clone spring-boot:run（端口 18088）
//
// 教学点：练习 1 用手写 HttpServer 实现了 Todo 的四个 HTTP 方法，这里用 Spring Boot 重做
// 同一件事——对比两种写法的代码量差异，体会框架替你做了什么（参数绑定、JSON 序列化、
// 状态码、请求体解析）。MockMvc 让「不占端口也能测 HTTP 语义」。
package com.example;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

@RestController
@RequestMapping("/api/todos")
public class TodoController {

    /** 创建请求体：title 必填（非空）。 */
    public record CreateTodoRequest(String title) {}

    /** Todo 资源：record 不可变，id 由服务端分配。 */
    public record Todo(long id, String title, boolean done) {}

    /** 测试可重置的入口（教学演示用内存表；生产应注入数据层，见 ph13/ph15）。 */
    private final ConcurrentHashMap<Long, Todo> store = new ConcurrentHashMap<>();
    private final AtomicLong seq = new AtomicLong(1);

    void clear() {
        store.clear();
        seq.set(1);
    }

    @GetMapping
    public ApiResponse<List<Todo>> list() {
        return ApiResponse.ok(new ArrayList<>(store.values()));
    }

    @PostMapping
    @ResponseStatus(HttpStatus.CREATED)
    public ApiResponse<Todo> create(@RequestBody CreateTodoRequest req) {
        if (req.title() == null || req.title().isBlank()) {
            throw new TodoException("title 不能为空");
        }
        Todo todo = new Todo(seq.getAndIncrement(), req.title(), false);
        store.put(todo.id(), todo);
        return ApiResponse.ok(todo);
    }

    @PatchMapping("/{id}")
    public ApiResponse<Todo> markDone(@PathVariable long id) {
        Todo todo = store.get(id);
        if (todo == null) throw new TodoException("todo 不存在: " + id);
        Todo updated = new Todo(todo.id(), todo.title(), true);
        store.put(id, updated);
        return ApiResponse.ok(updated);
    }

    @DeleteMapping("/{id}")
    public ApiResponse<Void> delete(@PathVariable long id) {
        if (store.remove(id) == null) throw new TodoException("todo 不存在: " + id);
        return ApiResponse.ok(null);
    }

    /** 文件上传端点（roadmap 练习「文件上传」）：multipart/form-data，MultipartFile 接收文件。
        教学点：@RequestParam("file") MultipartFile 是 Spring 对 multipart 请求体的封装——
        拿文件名与大小即可，文件内容用 getBytes()/transferTo() 落盘（本示例只回显元数据）。 */
    @PostMapping(value = "/upload", consumes = org.springframework.http.MediaType.MULTIPART_FORM_DATA_VALUE)
    public ApiResponse<java.util.Map<String, Object>> upload(
            @org.springframework.web.bind.annotation.RequestParam("file")
            org.springframework.web.multipart.MultipartFile file) throws java.io.IOException {
        var meta = new java.util.LinkedHashMap<String, Object>();
        meta.put("name", file.getOriginalFilename());
        meta.put("size", file.getSize());
        return ApiResponse.ok(meta);
    }

    /** 业务异常：本练习先用单控制器的 @ExceptionHandler 内联转 400；
        练习 5 用 @RestControllerAdvice 把它集中到全局——同一思想的两种粒度。 */
    public static class TodoException extends RuntimeException {
        public TodoException(String message) {
            super(message);
        }
    }

    /** 内联异常处理：TodoException → 400 + 业务码 40004（sol-05 改为全局统一）。 */
    @org.springframework.web.bind.annotation.ExceptionHandler(TodoException.class)
    @org.springframework.web.bind.annotation.ResponseStatus(HttpStatus.BAD_REQUEST)
    public ApiResponse<Void> handleTodo(TodoException ex) {
        return ApiResponse.error(40004, ex.getMessage());
    }
}

// ---------------------------------------------------------------------------
// 测试类 src/test/java/com/example/TodoControllerTest.java：
//
//   package com.example;
//   import org.junit.jupiter.api.Test;
//   import org.springframework.beans.factory.annotation.Autowired;
//   import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
//   import org.springframework.http.MediaType;
//   import org.springframework.test.web.servlet.MockMvc;
//   import org.junit.jupiter.api.BeforeEach;
//   import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.*;
//   import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;
//
//   @WebMvcTest(TodoController.class)
//   class TodoControllerTest {
//       @Autowired private MockMvc mockMvc;
//       @Autowired private TodoController controller;  // Spring 管理的 Controller 实例
//
//       @BeforeEach void resetStore() {
//           // @WebMvcTest 的 Controller 是同一个实例，内存表会跨测试累积——
//           // 每个测试前重置，保证 id 从 1 开始、断言确定（真实工程用 mock 数据源替代）
//           controller.clear();
//       }
//
//       @Test void createTodo() throws Exception {
//           mockMvc.perform(post("/api/todos").contentType(MediaType.APPLICATION_JSON)
//                           .content("{\"title\":\"write tests\"}"))
//                   .andExpect(status().isCreated())
//                   .andExpect(jsonPath("$.code").value(0))
//                   .andExpect(jsonPath("$.data.id").value(1))
//                   .andExpect(jsonPath("$.data.title").value("write tests"))
//                   .andExpect(jsonPath("$.data.done").value(false));
//       }
//
//       @Test void validateTitle() throws Exception {
//           // 控制器内联 @ExceptionHandler 把 TodoException 转成 400 + 业务码 40004；
//           // 练习 5 用 @RestControllerAdvice 把它集中到全局——两题接起来是完整闭环
//           mockMvc.perform(post("/api/todos").contentType(MediaType.APPLICATION_JSON)
//                           .content("{\"title\":\"  \"}"))
//                   .andExpect(status().isBadRequest())
//                   .andExpect(jsonPath("$.code").value(40004));
//       }
//
//       @Test void listTodos() throws Exception {
//           mockMvc.perform(get("/api/todos")).andExpect(status().isOk())
//                   .andExpect(jsonPath("$.data").isArray());
//       }
//
//       @Test void markDone() throws Exception {
//           mockMvc.perform(post("/api/todos").contentType(MediaType.APPLICATION_JSON)
//                           .content("{\"title\":\"a\"}"));
//           mockMvc.perform(patch("/api/todos/1")).andExpect(status().isOk())
//                   .andExpect(jsonPath("$.data.done").value(true));
//       }
//
//       @Test void deleteTodo() throws Exception {
//           mockMvc.perform(post("/api/todos").contentType(MediaType.APPLICATION_JSON)
//                           .content("{\"title\":\"b\"}"));
//           mockMvc.perform(delete("/api/todos/1")).andExpect(status().isOk())
//                   .andExpect(jsonPath("$.code").value(0));
//       }
//
//       @Test void uploadFile() throws Exception {
//           // 文件上传：MockMultipartFile 模拟 multipart 请求体（roadmap 练习「文件上传」）
//           var file = new org.springframework.mock.web.MockMultipartFile(
//                   "file", "data.txt", "text/plain", "hello world".getBytes());
//           mockMvc.perform(multipart("/api/todos/upload").file(file))
//                   .andExpect(status().isOk())
//                   .andExpect(jsonPath("$.code").value(0))
//                   .andExpect(jsonPath("$.data.name").value("data.txt"))
//                   .andExpect(jsonPath("$.data.size").value(11));
//       }
//   }
//
// 说明：TodoException 用控制器内联 @ExceptionHandler 转成 400 + 业务码 40004
// （不写它的话 Spring 默认把未处理异常当 500，且 MockMvc 无容器兜底、异常直接上抛）。
// 练习 5 用 @RestControllerAdvice 把它集中到全局——两题接起来就是完整闭环。
// clear() 是「内存表跨测试累积」的最小解法：真实工程用注入的仓库 + Mock 隔离。
