package com.example;

import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

/** 被拦截的业务端点（方法名 hello 会被拦截器记进日志，证明「拦截器确实包在 Controller 外层」） */
@RestController
public class HelloController {

    @GetMapping("/api/hello")
    public Map<String, String> hello(@RequestParam(defaultValue = "world") String name) {
        OrderRecorder.record("controller.hello");
        return Map.of("echo", name);
    }
}
