// exercises/sol-03-jwt-handmade.java —— 练习 3 参考实现：手写 JWT 签发/验签（HMAC-SHA256）
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖（javax.crypto 是 JDK 内建）
// 验证状态：已验证（本机实测，javac + java）
// 实测结果（main 里断言全过，最后打印 JWT TESTS PASSED (6 assertions)）：
//   签发 token 三段以 . 分隔；header 解码 {"alg":"HS256","typ":"JWT"}
//   payload 解码含 sub/role/iat/exp；合法 token 验签通过并取回 role=admin
//   篡改 payload → 验签失败；换密钥 → 验签失败；过期 → 验签失败
// ---------------------------------------------------------------------------
// 教学点：与 examples/ex03 的差异——本题要「带自定义 claim（role）签发」+「验签后取回
// claim」+「过期时间由调用方传入」。理解这三件事，就理解了 JWT 的完整用法：
// 签发时把身份信息塞进 payload，验签通过后从 payload 读回（服务端不再查 session）。
//
// 编译与运行：
//   javac -d out src/com/example/HandmadeJwt.java
//   java -cp out com.example.HandmadeJwt
package com.example;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;
import java.util.LinkedHashMap;
import java.util.Map;

/** 手写 JWT（HS256）：支持自定义 claim 与调用方指定过期时间。 */
public final class HandmadeJwt {

    private static final Base64.Encoder B64URL = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder B64URL_DEC = Base64.getUrlDecoder();

    /** 签发：claims 里的键值会进 payload，exp 由 ttlSeconds 换算（相对当前时间）。 */
    static String issue(byte[] secret, Map<String, Object> claims, long ttlSeconds) throws Exception {
        long now = Instant.now().getEpochSecond();
        StringBuilder payload = new StringBuilder("{\"iat\":").append(now)
                .append(",\"exp\":").append(now + ttlSeconds);
        for (Map.Entry<String, Object> e : claims.entrySet()) {
            payload.append(",\"").append(e.getKey()).append("\":\"")
                    .append(e.getValue()).append("\"");
        }
        payload.append("}");
        String header = b64("{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        String body = b64(payload.toString());
        String signingInput = header + "." + body;
        return signingInput + "." + b64(hmacSha256(secret, signingInput));
    }

    /** 验签 + 过期检查 + 按 key 取 claim 值（取不到返回 null）。 */
    static String verifyAndGet(byte[] secret, String token, String claimKey) {
        try {
            String[] parts = token.split("\\.");
            if (parts.length != 3) return null;
            String expected = b64(hmacSha256(secret, parts[0] + "." + parts[1]));
            if (!constantTimeEquals(expected, parts[2])) return null; // 签名不符
            String payloadJson = new String(B64URL_DEC.decode(parts[1]), StandardCharsets.UTF_8);
            long exp = extractLong(payloadJson, "exp");
            if (exp <= Instant.now().getEpochSecond()) return null;  // 已过期
            return extractString(payloadJson, claimKey);
        } catch (Exception e) {
            return null; // 格式问题一律视为无效
        }
    }

    // ---- 工具 ----

    private static byte[] hmacSha256(byte[] secret, String data) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret, "HmacSHA256"));
        return mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
    }

    private static String b64(String s) {
        return b64(s.getBytes(StandardCharsets.UTF_8));
    }

    private static String b64(byte[] raw) {
        return B64URL.encodeToString(raw);
    }

    private static boolean constantTimeEquals(String a, String b) {
        if (a.length() != b.length()) return false;
        byte[] x = a.getBytes(StandardCharsets.UTF_8);
        byte[] y = b.getBytes(StandardCharsets.UTF_8);
        int diff = 0;
        for (int i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
        return diff == 0;
    }

    private static long extractLong(String json, String key) {
        int idx = json.indexOf("\"" + key + "\":");
        if (idx < 0) return -1;
        int start = idx + key.length() + 3;
        int end = start;
        while (end < json.length() && Character.isDigit(json.charAt(end))) end++;
        return Long.parseLong(json.substring(start, end));
    }

    private static String extractString(String json, String key) {
        int idx = json.indexOf("\"" + key + "\":\"");
        if (idx < 0) return null;
        int start = idx + key.length() + 4;
        int end = json.indexOf('"', start);
        return end < 0 ? null : json.substring(start, end);
    }

    // ---- 测试入口（教学演示用断言替代 JUnit，保持零依赖） ----

    public static void main(String[] args) throws Exception {
        byte[] secret = "0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8);
        byte[] otherSecret = "ffffffffffffffffffffffffffffffff".getBytes(StandardCharsets.UTF_8);
        int passed = 0;

        Map<String, Object> claims = new LinkedHashMap<>();
        claims.put("sub", "alice");
        claims.put("role", "admin");
        String token = issue(secret, claims, 3600);

        passed += check(token.split("\\.").length == 3, "token 应为三段");
        passed += check("admin".equals(verifyAndGet(secret, token, "role")), "验签通过并取回 role=admin");
        passed += check("alice".equals(verifyAndGet(secret, token, "sub")), "取回 sub=alice");

        String tampered = token.substring(0, token.lastIndexOf('.')) + "." + "YQ"; // 改签名
        passed += check(verifyAndGet(secret, tampered, "role") == null, "篡改签名 → 验签失败");

        passed += check(verifyAndGet(otherSecret, token, "role") == null, "换密钥 → 验签失败");

        String expired = issue(secret, claims, -10); // 已过期 10 秒
        passed += check(verifyAndGet(secret, expired, "role") == null, "过期 token → 验签失败");

        System.out.println("JWT TESTS PASSED (" + passed + " assertions)");
    }

    private static int check(boolean cond, String label) {
        if (!cond) throw new AssertionError(label + " 失败");
        System.out.println("[ok] " + label);
        return 1;
    }
}
