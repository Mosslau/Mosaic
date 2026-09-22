package com.example.security;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;

/**
 * 统一错误 JSON：Security 的 401/403 也要走统一响应结构（roadmap 必会概念），
 * 否则 Filter 层拒绝的请求会返回容器默认的空白/HTML 错误页，破坏接口契约。
 */
public final class JsonErrors {

    private JsonErrors() {
    }

    public static void write(HttpServletResponse response, ObjectMapper mapper, int httpStatus, int code, String message)
            throws IOException {
        response.setStatus(httpStatus);
        response.setContentType("application/json;charset=UTF-8");
        var body = new java.util.LinkedHashMap<String, Object>();
        body.put("code", code);
        body.put("message", message);
        body.put("data", null); // Map.of 不允许 null 值，统一响应壳的 data 允许为 null
        mapper.writeValue(response.getWriter(), body);
    }
}
