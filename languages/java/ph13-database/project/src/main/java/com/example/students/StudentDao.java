package com.example.students;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;

/**
 * 基于 HikariCP 连接池的学生表访问层。
 * 核心心智：连接是昂贵的（TCP + 认证 + 会话初始化），池子预先建好常驻连接，
 * 业务「借了还、还了再借」——本类每个方法都从池借连接、try-with-resources 归还。
 */
public class StudentDao implements AutoCloseable {

    private final HikariDataSource dataSource;

    /** 建池即建连：maximumPoolSize 决定同时最多几条物理连接 */
    public StudentDao(String jdbcUrl, int maxPoolSize) {
        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        config.setUsername("sa");
        config.setPassword("");
        config.setMaximumPoolSize(maxPoolSize);
        this.dataSource = new HikariDataSource(config);
    }

    /** 从池借一条连接（业务层做多语句事务时用；用完必须 close 归还） */
    public Connection borrowConnection() throws SQLException {
        return dataSource.getConnection();
    }

    /** 在给定连接上入库（供业务层在同一个事务里多次写库） */
    public long insert(Connection conn, String name, String email, int grade) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(
                "INSERT INTO students(name, email, grade) VALUES (?, ?, ?)",
                Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, name);
            ps.setString(2, email);
            ps.setInt(3, grade);
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    /** 入库并回填数据库生成的自增主键 */
    public long insert(String name, String email, int grade) throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "INSERT INTO students(name, email, grade) VALUES (?, ?, ?)",
                     Statement.RETURN_GENERATED_KEYS)) {
            ps.setString(1, name);
            ps.setString(2, email);
            ps.setInt(3, grade);
            ps.executeUpdate();
            try (ResultSet keys = ps.getGeneratedKeys()) {
                keys.next();
                return keys.getLong(1);
            }
        }
    }

    public Optional<Student> findById(long id) throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT id, name, email, grade FROM students WHERE id = ?")) {
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? Optional.of(map(rs)) : Optional.empty();
            }
        }
    }

    /** 按邮箱查（V2 迁移建了 idx_students_email 索引，走 B+ 树定位而非全表扫描） */
    public Optional<Student> findByEmail(String email) throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT id, name, email, grade FROM students WHERE email = ?")) {
            ps.setString(1, email);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? Optional.of(map(rs)) : Optional.empty();
            }
        }
    }

    public List<Student> findAll() throws SQLException {
        List<Student> students = new ArrayList<>();
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "SELECT id, name, email, grade FROM students ORDER BY id");
             ResultSet rs = ps.executeQuery()) {
            while (rs.next()) {
                students.add(map(rs));
            }
        }
        return students;
    }

    /** 更新返回受影响行数：0 行表示目标不存在 */
    public int updateGrade(long id, int newGrade) throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(
                     "UPDATE students SET grade = ? WHERE id = ?")) {
            ps.setInt(1, newGrade);
            ps.setLong(2, id);
            return ps.executeUpdate();
        }
    }

    public int delete(long id) throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement("DELETE FROM students WHERE id = ?")) {
            ps.setLong(1, id);
            return ps.executeUpdate();
        }
    }

    public int count() throws SQLException {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement("SELECT COUNT(*) FROM students");
             ResultSet rs = ps.executeQuery()) {
            rs.next();
            return rs.getInt(1);
        }
    }

    /** 池的实时状态（供教学观察）：当前物理连接总数 / 活跃 / 空闲 */
    public String poolStats() {
        var mx = dataSource.getHikariPoolMXBean();
        return "total=" + mx.getTotalConnections()
                + ", active=" + mx.getActiveConnections()
                + ", idle=" + mx.getIdleConnections();
    }

    private static Student map(ResultSet rs) throws SQLException {
        return new Student(rs.getLong("id"), rs.getString("name"),
                rs.getString("email"), rs.getInt("grade"));
    }

    @Override
    public void close() {
        dataSource.close();   // 关池才真正断开全部物理连接
    }
}
