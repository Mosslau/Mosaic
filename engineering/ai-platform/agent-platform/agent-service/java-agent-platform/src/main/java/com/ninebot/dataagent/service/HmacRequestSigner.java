package com.ninebot.dataagent.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.net.URLDecoder;
import java.net.URLEncoder;
import java.util.ArrayList;
import java.util.Base64;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;

/** Shared DATA_AGENT-HMAC-SHA256 protocol implementation for Java callers. */
public final class HmacRequestSigner {
    public static final String VERSION = "DATA_AGENT-HMAC-SHA256";

    private HmacRequestSigner() {}

    public static Map<String, String> headers(
            String method, String path, String query, byte[] body, String accessKey, String secretKey) {
        String timestamp = Long.toString(System.currentTimeMillis() / 1000);
        String nonce = UUID.randomUUID().toString().replace("-", "");
        String bodyHash = sha256(body);
        String canonical = String.join(
                "\n", VERSION, accessKey, timestamp, nonce, method.toUpperCase(),
                path.isEmpty() ? "/" : path, canonicalQuery(query), bodyHash);
        String signature = hmacSha256(canonical, secretKey);
        Map<String, String> result = new LinkedHashMap<>();
        result.put("X-Access-Key", accessKey);
        result.put("X-Timestamp", timestamp);
        result.put("X-Nonce", nonce);
        result.put("X-Content-SHA256", bodyHash);
        result.put("X-Signature-Version", VERSION);
        result.put("X-Signature", signature);
        return result;
    }


    public static boolean verify(
            String signature, String method, String path, String query, byte[] body,
            String accessKey, String timestamp, String nonce, String contentHash, String secretKey) {
        if (signature == null || accessKey == null || timestamp == null || nonce == null
                || contentHash == null || secretKey == null || !contentHash.equals(sha256(body))) {
            return false;
        }
        try {
            long requestTime = Long.parseLong(timestamp);
            long now = System.currentTimeMillis() / 1000;
            if (Math.abs(now - requestTime) > 300) {
                return false;
            }
        } catch (NumberFormatException exception) {
            return false;
        }
        String canonical = String.join(
                "\n", VERSION, accessKey, timestamp, nonce, method.toUpperCase(),
                path.isEmpty() ? "/" : path, canonicalQuery(query), contentHash);
        return MessageDigest.isEqual(
                signature.getBytes(StandardCharsets.US_ASCII),
                hmacSha256(canonical, secretKey).getBytes(StandardCharsets.US_ASCII));
    }

    private static String canonicalQuery(String query) {
        if (query == null || query.isEmpty()) {
            return "";
        }
        List<String[]> pairs = new ArrayList<>();
        for (String item : query.split("&", -1)) {
            String[] parts = item.split("=", 2);
            String key = decode(parts[0]);
            String value = parts.length == 2 ? decode(parts[1]) : "";
            pairs.add(new String[] {key, value});
        }
        pairs.sort(Comparator.comparing((String[] pair) -> pair[0]).thenComparing(pair -> pair[1]));
        return pairs.stream()
                .map(pair -> encode(pair[0]) + "=" + encode(pair[1]))
                .collect(java.util.stream.Collectors.joining("&"));
    }

    private static String decode(String value) {
        return URLDecoder.decode(value, StandardCharsets.UTF_8);
    }

    private static String encode(String value) {
        return URLEncoder.encode(value, StandardCharsets.UTF_8);
    }

    private static String sha256(byte[] value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256").digest(value);
            return hex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }

    private static String hmacSha256(String value, String secret) {
        try {
            Mac mac = Mac.getInstance("HmacSHA256");
            mac.init(new SecretKeySpec(secret.getBytes(StandardCharsets.UTF_8), "HmacSHA256"));
            return Base64.getUrlEncoder().withoutPadding()
                    .encodeToString(mac.doFinal(value.getBytes(StandardCharsets.UTF_8)));
        } catch (Exception exception) {
            throw new IllegalStateException("HMAC-SHA256 signing failed", exception);
        }
    }

    private static String hex(byte[] bytes) {
        StringBuilder result = new StringBuilder(bytes.length * 2);
        for (byte value : bytes) {
            result.append(String.format("%02x", value & 0xff));
        }
        return result.toString();
    }
}
