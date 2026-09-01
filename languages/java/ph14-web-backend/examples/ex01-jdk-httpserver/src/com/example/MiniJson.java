// examples/ex01-jdk-httpserver/src/com/example/MiniJson.java —— 教学用最小 JSON 序列化/解析
// 验证环境：OpenJDK 17.0.18（javac -version → 17.0.18），零第三方依赖
// 验证状态：已验证（与 RestServer.java 一同编译运行）
// ---------------------------------------------------------------------------
// 教学点：完整 JSON 库（Jackson/Gson）的引入与序列化话题属于序列化专题，本阶段演示
// 「REST 需要 JSON」时用手写最小实现撑住：只支持 REST 演示要用的
// {"k":"v"} 对象、[ ... ] 数组、数字与字符串。真实工程请用 Jackson（见 ex04）。
// 本类刻意简化：不支持嵌套对象、转义只处理最常用的一对，聚焦「解析手工 JSON」的教学。
package com.example;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/** 最小 JSON 工具：够 REST 演示用，不追求完整标准。 */
final class MiniJson {

    private MiniJson() {}

    /** 把 REST 响应对象转成 JSON 字符串（支持 Map / List / Number / String / Boolean / null）。 */
    static String toJson(Object value) {
        if (value == null) return "null";
        if (value instanceof String s) return quote(s);
        if (value instanceof Number || value instanceof Boolean) return value.toString();
        if (value instanceof Map<?, ?> map) {
            StringBuilder sb = new StringBuilder("{");
            boolean first = true;
            for (Map.Entry<?, ?> e : map.entrySet()) {
                if (!first) sb.append(",");
                first = false;
                sb.append(quote(String.valueOf(e.getKey()))).append(":").append(toJson(e.getValue()));
            }
            return sb.append("}").toString();
        }
        if (value instanceof List<?> list) {
            StringBuilder sb = new StringBuilder("[");
            boolean first = true;
            for (Object item : list) {
                if (!first) sb.append(",");
                first = false;
                sb.append(toJson(item));
            }
            return sb.append("]").toString();
        }
        throw new IllegalArgumentException("unsupported type: " + value.getClass());
    }

    /** 解析 {"k":"v", ...} 顶层对象，返回有序 Map；只支持字符串/数字值（本演示够用）。 */
    static Map<String, String> parseObject(String json) {
        Map<String, String> result = new LinkedHashMap<>();
        String s = json.trim();
        if (!s.startsWith("{") || !s.endsWith("}")) {
            throw new IllegalArgumentException("not an object: " + json);
        }
        String inner = s.substring(1, s.length() - 1).trim();
        if (inner.isEmpty()) return result;
        for (String pair : splitTopLevel(inner)) {
            int colon = pair.indexOf(':');
            if (colon < 0) throw new IllegalArgumentException("no colon in: " + pair);
            String key = unquote(pair.substring(0, colon).trim());
            String rawVal = pair.substring(colon + 1).trim();
            result.put(key, unquote(rawVal));
        }
        return result;
    }

    private static List<String> splitTopLevel(String s) {
        List<String> parts = new ArrayList<>();
        int depth = 0;
        StringBuilder cur = new StringBuilder();
        boolean inStr = false;
        for (int i = 0; i < s.length(); i++) {
            char c = s.charAt(i);
            if (c == '"' && (i == 0 || s.charAt(i - 1) != '\\')) inStr = !inStr;
            if (!inStr) {
                if (c == '{' || c == '[') depth++;
                else if (c == '}' || c == ']') depth--;
                else if (c == ',' && depth == 0) {
                    parts.add(cur.toString());
                    cur.setLength(0);
                    continue;
                }
            }
            cur.append(c);
        }
        if (cur.length() > 0) parts.add(cur.toString());
        return parts;
    }

    private static String quote(String s) {
        return "\"" + s.replace("\\", "\\\\").replace("\"", "\\\"") + "\"";
    }

    private static String unquote(String raw) {
        if (raw.startsWith("\"") && raw.endsWith("\"")) {
            return raw.substring(1, raw.length() - 1).replace("\\\"", "\"").replace("\\\\", "\\");
        }
        return raw; // 数字值原样返回（本演示里当作字符串处理）
    }
}
