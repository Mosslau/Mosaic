// examples/ex03-jwt-handmade/src/com/example/JwtDemo.java —— 手写 JWT：HMAC-SHA256 签名 + 验签
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖（javax.crypto 是 JDK 内建）
// 验证状态：已验证（本机实测）
// 验证命令：javac -d out src/com/example/JwtDemo.java && java -cp out com.example.JwtDemo
// 实测结果（本机输出）：
//   header.decoded   = {"alg":"HS256","typ":"JWT"}
//   payload.decoded  = {"sub":"alice","iat":<秒>,"exp":<秒>}（3 分钟有效期）
//   verify(合法 token) = true；verify(篡改 sub) = false；verify(已过期) = false；verify(非法输入) = false
//   token 形如 eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.<payload>.<signature> 三段以 . 分隔
// ---------------------------------------------------------------------------
// 教学点：JWT = Header.Payload.Signature，Signature = HMAC-SHA256(header.payload, 密钥)。
// 本文件手写全部步骤（base64url 编码、MAC 计算、过期校验），让你看清「签名到底签了什么」；
// 生产环境用成熟库（如 ex06 的 jjwt）——手写是为了理解，不是推荐生产手写。
package com.example;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.Base64;

/** 手写 JWT 的签发与验签（HMAC-SHA256，HS256）。 */
public final class JwtDemo {

    private static final Base64.Encoder B64URL = Base64.getUrlEncoder().withoutPadding();
    private static final Base64.Decoder B64URL_DEC = Base64.getUrlDecoder();

    public static void main(String[] args) throws Exception {
        // 密钥至少 32 字节（HS256 要求），生产从环境变量/配置注入，不硬编码
        byte[] secret = "0123456789abcdef0123456789abcdef".getBytes(StandardCharsets.UTF_8);

        // 1. 签发：3 分钟有效期的 token
        long now = Instant.now().getEpochSecond();
        String token = sign(secret, "alice", now, now + 180);
        System.out.println("token = " + token);
        System.out.println("header.decoded = " + decode(token.split("\\.")[0]));
        System.out.println("payload.decoded = " + decode(token.split("\\.")[1]));

        // 2. 验签：合法 token 应通过
        System.out.println("verify(合法 token) = " + verify(secret, token));

        // 3. 篡改检测：把 payload 里的 sub 从 alice 改成 bob，签名不变 → 验签失败
        String[] parts = token.split("\\.");
        String tampered = parts[0] + "." + tamperSubject(parts[1]) + "." + parts[2];
        System.out.println("verify(篡改 sub)  = " + verify(secret, tampered));

        // 4. 过期检测：签发 -10 秒（已过期 10 秒）→ 验签失败
        String expired = sign(secret, "alice", now - 100, now - 10);
        System.out.println("verify(已过期)     = " + verify(secret, expired));

        // 5. 非法 base64 → 验签失败（Base64 解码抛异常被捕获）
        System.out.println("verify(非法输入)   = " + verify(secret, "not-a-jwt"));
    }

    /** 签发：header.payload.signature。签名对象是「header.payload」这个完整字符串。 */
    static String sign(byte[] secret, String subject, long iat, long exp) throws Exception {
        String header = b64("{\"alg\":\"HS256\",\"typ\":\"JWT\"}");
        String payload = b64("{\"sub\":\"" + subject + "\",\"iat\":" + iat + ",\"exp\":" + exp + "}");
        String signingInput = header + "." + payload;
        return signingInput + "." + b64(hmacSha256(secret, signingInput));
    }

    /** 验签：重新计算签名比对 + exp 过期校验。任何一步失败返回 false。 */
    static boolean verify(byte[] secret, String token) {
        try {
            String[] parts = token.split("\\.");
            if (parts.length != 3) return false;
            String expected = b64(hmacSha256(secret, parts[0] + "." + parts[1]));
            if (!constantTimeEquals(expected, parts[2])) return false; // 防时序攻击
            String payloadJson = new String(B64URL_DEC.decode(parts[1]), StandardCharsets.UTF_8);
            long exp = extractExp(payloadJson);
            return exp > Instant.now().getEpochSecond(); // 过期则拒绝
        } catch (Exception e) {
            return false; // 任何格式问题（非法 base64、缺段）都视为无效
        }
    }

    // ---- 工具 ----

    /** HMAC-SHA256 计算：这是签名的核心，签的是 header.payload 字符串。 */
    private static byte[] hmacSha256(byte[] secret, String data) throws Exception {
        Mac mac = Mac.getInstance("HmacSHA256");
        mac.init(new SecretKeySpec(secret, "HmacSHA256"));
        return mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
    }

    private static String b64(byte[] raw) {
        return B64URL.encodeToString(raw);
    }

    private static String b64(String s) {
        return b64(s.getBytes(StandardCharsets.UTF_8));
    }

    private static String decode(String b64url) {
        return new String(B64URL_DEC.decode(b64url), StandardCharsets.UTF_8);
    }

    /** 常量时间比较：长度不同直接失败，长度相同逐字节异或，避免提前返回泄露差异。 */
    private static boolean constantTimeEquals(String a, String b) {
        if (a.length() != b.length()) return false;
        byte[] x = a.getBytes(StandardCharsets.UTF_8);
        byte[] y = b.getBytes(StandardCharsets.UTF_8);
        int diff = 0;
        for (int i = 0; i < x.length; i++) diff |= x[i] ^ y[i];
        return diff == 0;
    }

    /** 从 payload JSON 中取 exp 字段（教学用最简解析；完整 JSON 解析见序列化专题）。 */
    private static long extractExp(String payloadJson) {
        int idx = payloadJson.indexOf("\"exp\":");
        if (idx < 0) return -1;
        int start = idx + 6;
        int end = start;
        while (end < payloadJson.length() && Character.isDigit(payloadJson.charAt(end))) end++;
        return Long.parseLong(payloadJson.substring(start, end));
    }

    /** 篡改演示：把 payload 里的 sub 值 alice 换成 bob（保持 JSON 结构，仅演示签名不匹配）。 */
    private static String tamperSubject(String payloadB64) {
        String json = decode(payloadB64);
        return b64(json.replace("\"alice\"", "\"bob\""));
    }
}
