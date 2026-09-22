-- project/springboot-deploy-template/deploy/sql/init.sql
-- MySQL 首次启动初始化（docker-entrypoint-initdb.d 约定，仅在数据卷为空时执行）
-- 验证状态：未在本环境实际验证（需 docker 起 MySQL）
CREATE TABLE IF NOT EXISTS products (
    id          BIGINT PRIMARY KEY AUTO_INCREMENT,
    sku         VARCHAR(64)  NOT NULL UNIQUE,
    name        VARCHAR(128) NOT NULL,
    stock       INT          NOT NULL DEFAULT 0,
    version     INT          NOT NULL DEFAULT 0,
    created_at  TIMESTAMP    NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE = InnoDB DEFAULT CHARSET = utf8mb4;

INSERT INTO products (sku, name, stock) VALUES ('sku-demo-1', 'ph19 演示商品', 100);
