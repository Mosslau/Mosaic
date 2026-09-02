package com.example.rbac;

import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.servlet.http.HttpServletResponse;

import java.io.IOException;
import java.util.LinkedHashMap;

/** Security Filter 层的 401/403 统一 JSON（ApiResponse 形状，code/message/data） */
public final class JsonErrors {

    private JsonErrors() {
    }

    public static void write(HttpServletResponse response, ObjectMapper mapper, int httpStatus, int code, String message)
            throws IOException {
        response.setStatus(httpStatus);
        response.setContentType("application/json;charset=UTF-8");
        var body = new LinkedHashMap<String, Object>();
        body.put("code", code);
        body.put("message", message);
        body.put("data", null);
        mapper.writeValue(response.getWriter(), body);
    }
}
