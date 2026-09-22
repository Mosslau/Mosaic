package com.example.msdemo.user.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.security.SecureRandom;
import java.util.HexFormat;

/**
 * 口令哈希工具：手写 SHA-256 加盐（教学简化——未引入 Spring Security 故没有 BCrypt，
 * 生产请用 BCrypt/Argon2 这类带 cost 的慢哈希；SHA-256 快哈希抗离线爆破能力弱）。
 */
public final class Passwords {

    private static final SecureRandom RANDOM = new SecureRandom();

    private Passwords() {
    }

    public static String newSalt() {
        byte[] salt = new byte[16];
        RANDOM.nextBytes(salt);
        return HexFormat.of().formatHex(salt);
    }

    public static String hash(String salt, String rawPassword) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            byte[] hashed = digest.digest((salt + ":" + rawPassword).getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(hashed);
        } catch (NoSuchAlgorithmException e) {
            throw new IllegalStateException("SHA-256 unavailable", e);
        }
    }

    public static boolean matches(String salt, String rawPassword, String expectedHash) {
        return hash(salt, rawPassword).equals(expectedHash);
    }
}
