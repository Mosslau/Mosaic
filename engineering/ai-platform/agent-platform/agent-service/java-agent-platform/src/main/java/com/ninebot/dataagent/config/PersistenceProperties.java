package com.ninebot.dataagent.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

/**
 * 控制面持久化配置。
 *
 * <p>默认使用内存实现，保证开发者在没有 PostgreSQL 时仍然可以启动服务；生产环境
 * 应将 {@code AGENT_PERSISTENCE_MODE} 设置为 {@code postgres}，并通过环境变量注入连接信息。</p>
 */
@ConfigurationProperties(prefix = "agent.persistence")
public class PersistenceProperties {
    private String mode = "memory";
    private String jdbcUrl = "jdbc:postgresql://127.0.0.1:5432/postgres";
    private String username = "postgres";
    private String password = "";
    private int poolSize = 10;

    public String getMode() { return mode; }
    public void setMode(String mode) { this.mode = mode; }
    public String getJdbcUrl() { return jdbcUrl; }
    public void setJdbcUrl(String jdbcUrl) { this.jdbcUrl = jdbcUrl; }
    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }
    public String getPassword() { return password; }
    public void setPassword(String password) { this.password = password; }
    public int getPoolSize() { return poolSize; }
    public void setPoolSize(int poolSize) { this.poolSize = poolSize; }
}
