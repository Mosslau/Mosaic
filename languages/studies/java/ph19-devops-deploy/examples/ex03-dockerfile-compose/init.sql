-- examples/ex03-dockerfile-compose/init.sql
-- MySQL 首次启动自动初始化（官方镜像约定：/docker-entrypoint-initdb.d 下的 .sql 只在数据卷为空时执行一次）
-- 教学点：schema 随代码走（与 pom.xml 一起评审/版本化），不要手工 ssh 上去建表
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
