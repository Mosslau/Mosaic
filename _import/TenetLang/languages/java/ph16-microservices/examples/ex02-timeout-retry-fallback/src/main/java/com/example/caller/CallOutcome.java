package com.example.caller;

/** 一次远程调用的完整结局（成功/失败/降级），attempts 是实测重试次数 */
public record CallOutcome(Kind kind, int httpStatus, String body, int attempts, String lastError) {

    public enum Kind { SUCCESS, CLIENT_ERROR, FALLBACK }

    public static CallOutcome success(int status, String body, int attempts) {
        return new CallOutcome(Kind.SUCCESS, status, body, attempts, null);
    }

    public static CallOutcome clientError(int status, String body, int attempts) {
        return new CallOutcome(Kind.CLIENT_ERROR, status, body, attempts, null);
    }

    public static CallOutcome fallback(String fallbackBody, int attempts, String lastError) {
        return new CallOutcome(Kind.FALLBACK, 0, fallbackBody, attempts, lastError);
    }
}
