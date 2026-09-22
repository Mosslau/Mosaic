package com.example.students;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.List;

/**
 * 学生管理业务层：单条注册 + 批量导入。
 * 事务边界由业务定义：批量导入 = 整批「同生同死」——任何一条失败（重复邮箱、非法数据）
 * 都整体回滚，不允许半批入库。这是「事务边界必须由业务定义」的实战落点。
 */
public class StudentService {

    /** 批量导入的一行输入（id 由数据库生成，导入前未知） */
    public record StudentInput(String name, String email, int grade) {}

    private final StudentDao dao;

    public StudentService(StudentDao dao) {
        this.dao = dao;
    }

    /** 单条注册：Java 层业务校验快速失败，落库交给 DAO（数据库约束兜底） */
    public long register(String name, String email, int grade) throws SQLException {
        validate(name, email, grade);
        return dao.insert(name, email, grade);
    }

    /**
     * 批量导入（一个事务）：全部成功才 commit，任何一条失败整体 rollback。
     *
     * @throws IllegalArgumentException 任一输入不合法（业务校验，未开始写库）
     * @throws SQLException             数据库失败（如重复邮箱触发 UNIQUE 约束，已整体回滚）
     */
    public int importStudents(List<StudentInput> inputs) throws SQLException {
        for (StudentInput in : inputs) {
            validate(in.name(), in.email(), in.grade());   // 先全部校验，快速失败
        }
        boolean prevAutoCommit;
        try (Connection conn = dao.borrowConnection()) {
            prevAutoCommit = conn.getAutoCommit();
            conn.setAutoCommit(false);   // —— 批量导入的事务从这里开始
            try {
                int imported = 0;
                for (StudentInput in : inputs) {
                    dao.insert(conn, in.name(), in.email(), in.grade());
                    imported++;
                }
                conn.commit();   // —— 全部成功，一次落盘
                return imported;
            } catch (SQLException | RuntimeException e) {
                conn.rollback();   // —— 任何一条失败，撤销本批次全部写入
                throw e;
            } finally {
                conn.setAutoCommit(prevAutoCommit);   // 恢复现场，连接归还后可复用
            }
        }
    }

    private static void validate(String name, String email, int grade) {
        if (name == null || name.isBlank()) {
            throw new IllegalArgumentException("姓名不能为空");
        }
        if (email == null || email.isBlank() || !email.contains("@")) {
            throw new IllegalArgumentException("邮箱格式不合法: " + email);
        }
        if (grade < 1 || grade > 6) {
            throw new IllegalArgumentException("年级必须在 1~6 之间: " + grade);
        }
    }
}
