package com.ninebot.dataagent.config;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import javax.sql.DataSource;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.boot.CommandLineRunner;
import org.springframework.context.annotation.Configuration;
import org.springframework.core.io.ClassPathResource;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.datasource.init.ResourceDatabasePopulator;

/** PostgreSQL 控制面数据源、JdbcTemplate 和表结构初始化配置。 */
@Configuration
@EnableConfigurationProperties(PersistenceProperties.class)
public class PersistenceConfiguration {
    @Bean
    @ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
    DataSource controlPlaneDataSource(PersistenceProperties properties) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(properties.getJdbcUrl());
        config.setUsername(properties.getUsername());
        config.setPassword(properties.getPassword());
        config.setMaximumPoolSize(Math.max(1, properties.getPoolSize()));
        config.setPoolName("data-agent-control-plane");
        config.setConnectionTimeout(5_000);
        config.setValidationTimeout(3_000);
        return new HikariDataSource(config);
    }

    @Bean
    @ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
    JdbcTemplate controlPlaneJdbcTemplate(DataSource dataSource) {
        return new JdbcTemplate(dataSource);
    }

    @Bean
    @ConditionalOnProperty(prefix = "agent.persistence", name = "mode", havingValue = "postgres")
    CommandLineRunner controlPlaneSchemaInitializer(DataSource dataSource) {
        return args -> new ResourceDatabasePopulator(
                false, false, "UTF-8", new ClassPathResource("db/migration/V1__control_plane.sql"))
                .execute(dataSource);
    }
}
