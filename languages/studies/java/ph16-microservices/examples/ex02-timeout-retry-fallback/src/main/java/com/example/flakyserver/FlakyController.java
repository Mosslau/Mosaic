package com.example.flakyserver;

import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

/**
 * 故障注入端点集合：按 key 计数，每个端点可调「前 N 次失败」。
 * /admin/hits 暴露真实命中次数 —— 测试用「下游被打了几次」验证重试次数，不猜时序。
 */
@RestController
public class FlakyController {

    private final Map<String, AtomicInteger> hits = new ConcurrentHashMap<>();

    private int hit(String key) {
        return hits.computeIfAbsent(key, k -> new AtomicInteger()).incrementAndGet();
    }

    /** 前 failBefore 次返回 500，之后返回 200 */
    @GetMapping("/flaky")
    public ResponseEntity<String> flaky(@RequestParam(defaultValue = "0") int failBefore) {
        int n = hit("flaky");
        if (n <= failBefore) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("transient error #" + n);
        }
        return ResponseEntity.ok("ok after " + n + " attempts");
    }

    /** 永远 500 */
    @GetMapping("/always-error")
    public ResponseEntity<String> alwaysError() {
        int n = hit("always-error");
        return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("permanent error #" + n);
    }

    /** 永远 404：客户端错误不应触发重试 */
    @GetMapping("/missing")
    public ResponseEntity<String> missing() {
        hit("missing");
        return ResponseEntity.status(HttpStatus.NOT_FOUND).body("no such resource");
    }

    /** 慢端点：配合调用方读超时制造「超时失败」 */
    @GetMapping("/slow")
    public String slow(@RequestParam(defaultValue = "900") long ms) throws InterruptedException {
        hit("slow");
        Thread.sleep(ms);
        return "slow ok";
    }

    /** POST 版 flaky：验证「非幂等请求不重试」 */
    @PostMapping("/flaky-post")
    public ResponseEntity<String> flakyPost(@RequestParam(defaultValue = "0") int failBefore,
                                            @RequestBody(required = false) String body) {
        int n = hit("flaky-post");
        if (n <= failBefore) {
            return ResponseEntity.status(HttpStatus.INTERNAL_SERVER_ERROR).body("transient error #" + n);
        }
        return ResponseEntity.ok("post ok after " + n + " attempts, body=" + body);
    }

    @GetMapping("/admin/hits")
    public Map<String, Integer> hits() {
        Map<String, Integer> snapshot = new ConcurrentHashMap<>();
        hits.forEach((k, v) -> snapshot.put(k, v.get()));
        return snapshot;
    }

    @PostMapping("/admin/reset")
    public Map<String, String> reset() {
        hits.clear();
        return Map.of("reset", "done");
    }
}
