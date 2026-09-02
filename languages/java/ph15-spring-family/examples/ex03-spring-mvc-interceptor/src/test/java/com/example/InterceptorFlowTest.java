package com.example;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.AutoConfigureMockMvc;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.web.servlet.MockMvc;

import static org.assertj.core.api.Assertions.assertThat;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

/**
 * ex03 测试：断言「Filter → 拦截器链 → Controller」的真实执行顺序（栈式收尾），
 * 以及拦截器短路（preHandle=false）时谁执行、谁不执行。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
@AutoConfigureMockMvc
class InterceptorFlowTest {

    @Autowired
    private MockMvc mockMvc;

    @BeforeEach
    void resetFlow() {
        OrderRecorder.FLOW.clear();
    }

    /** 正常请求：Filter 最外、pre 顺序执行、post/after 倒序收尾 */
    @Test
    void fullChainExecutesInStackOrder() throws Exception {
        mockMvc.perform(get("/api/hello").param("name", "Alice"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.echo").value("Alice"));

        assertThat(OrderRecorder.FLOW).containsExactly(
                "filter.before",
                "first.pre", "second.pre",
                "controller.hello",
                "second.post", "first.post",
                "second.after", "first.after",
                "filter.after"
        );
    }

    /** 短路：second.pre 返回 false → Controller 不执行、post 一律不执行，只有已放行的 first 收到 after */
    @Test
    void shortCircuitSkipsControllerAndPostHandle() throws Exception {
        mockMvc.perform(get("/api/hello").param("block", "true"))
                .andExpect(status().isForbidden());

        assertThat(OrderRecorder.FLOW).containsExactly(
                "filter.before",
                "first.pre", "second.pre", "second.pre.BLOCKED",
                "first.after",
                "filter.after"
        );
    }

    /** 未匹配拦截路径（非 /api/**）的请求不触发拦截器，但 Filter（/api/*）仍在外层 */
    @Test
    void interceptorsArePathScopedButFilterIsNotPathScoped() throws Exception {
        mockMvc.perform(get("/other/hello"))
                .andExpect(status().isNotFound());
        // /other/** 不在拦截器路径内，也不在 Filter 的 /api/* 内 —— 两者都不触发
        assertThat(OrderRecorder.FLOW).isEmpty();
    }
}
