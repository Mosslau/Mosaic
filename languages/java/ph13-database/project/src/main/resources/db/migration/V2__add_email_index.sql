-- V2：给 email 加索引（按邮箱查询高频；schema 演进 = 新增迁移文件，永不修改已执行的旧文件）
CREATE INDEX idx_students_email ON students(email);
