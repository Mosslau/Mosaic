package com.example.msdemo.common.api;

/**
 * 业务码常量。码义沿用 ph15：40100=未认证、40101=登录失败、40300=无权限、40901=用户名冲突
 * （注意与 ph14 相反，跨阶段对照代码勿混用）；ph16 微服务语义新增：
 * 40001=缺 Idempotency-Key、40400=资源不存在、50200=下游服务异常、50400=下游超时。
 * 约定：HTTP 状态码 = 业务码 / 100（40100→401、50200→502），网关与下游服务共用同一套契约。
 */
public final class BizCodes {

    public static final int OK = 0;
    public static final int BAD_REQUEST = 40000;
    public static final int MISSING_IDEMPOTENCY_KEY = 40001;
    public static final int UNAUTHENTICATED = 40100;
    public static final int LOGIN_FAILED = 40101;
    public static final int FORBIDDEN = 40300;
    public static final int NOT_FOUND = 40400;
    public static final int CONFLICT_USERNAME = 40901;
    public static final int INTERNAL_ERROR = 50000;
    public static final int DOWNSTREAM_ERROR = 50200;
    public static final int DOWNSTREAM_TIMEOUT = 50400;

    private BizCodes() {
    }
}
