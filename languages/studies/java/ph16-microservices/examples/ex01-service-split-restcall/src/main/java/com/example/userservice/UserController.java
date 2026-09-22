package com.example.userservice;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/**
 * 用户查询端点。id=99 是「慢用户」（sleep 1500ms），用于给 order-service 制造下游超时场景。
 * 真实微服务里这张表在独立数据库里（服务数据私有，见主文档 3.1），示例为聚焦调用语义用内存 Map。
 */
@RestController
public class UserController {

    private static final long SLOW_USER_ID = 99L;
    private static final long SLOW_USER_DELAY_MS = 1500L;

    private static final Map<Long, UserDto> USERS = Map.of(
            1L, new UserDto(1L, "张三", "杭州"),
            2L, new UserDto(2L, "李四", "上海"),
            SLOW_USER_ID, new UserDto(SLOW_USER_ID, "慢用户", "北京"));

    @GetMapping("/users/{id}")
    public ResponseEntity<UserDto> get(@PathVariable long id) throws InterruptedException {
        if (id == SLOW_USER_ID) {
            Thread.sleep(SLOW_USER_DELAY_MS);   // 模拟下游慢调用：order-service 读超时 800ms 会先于它返回
        }
        UserDto user = USERS.get(id);
        return user == null ? ResponseEntity.notFound().build() : ResponseEntity.ok(user);
    }
}
