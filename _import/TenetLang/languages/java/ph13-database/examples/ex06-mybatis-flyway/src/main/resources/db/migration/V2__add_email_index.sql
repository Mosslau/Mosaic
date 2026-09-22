-- V2：给 email 加索引（schema 演进 = 新增一个迁移文件，永不修改已执行的旧文件）
CREATE INDEX idx_users_email ON users(email);
