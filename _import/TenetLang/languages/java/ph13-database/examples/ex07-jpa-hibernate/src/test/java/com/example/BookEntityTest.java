package com.example;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

import java.util.List;
import org.hibernate.Session;
import org.hibernate.SessionFactory;
import org.hibernate.cfg.Configuration;
import org.junit.jupiter.api.AfterAll;
import org.junit.jupiter.api.BeforeAll;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;

/**
 * Hibernate ORM 实测（HSQLDB 内存库，hbm2ddl 自动建表）。
 * 用原生 Configuration 引导：注解映射、零 persistence.xml——
 * 与 JPA 标准引导（Persistence.createEntityManagerFactory）等价，但更省依赖。
 * 注：启动日志有 HSQLDialect 版本提示（Hibernate 6.5 基线 HSQLDB 2.6.1），实测功能正常。
 */
class BookEntityTest {

    private static SessionFactory sessionFactory;

    @BeforeAll
    static void init() {
        Configuration cfg = new Configuration()
                .addAnnotatedClass(Book.class)
                .setProperty("hibernate.connection.url", "jdbc:hsqldb:mem:hibdb")
                .setProperty("hibernate.connection.username", "sa")
                .setProperty("hibernate.connection.password", "")
                // create-drop：启动建表、关闭删表——开发/测试专用，生产交给 Flyway（见 ex06）
                .setProperty("hibernate.hbm2ddl.auto", "create-drop");
        sessionFactory = cfg.buildSessionFactory();
    }

    @AfterAll
    static void close() {
        sessionFactory.close();
    }

    @Test
    @DisplayName("persist + find：ORM 替你写 INSERT 和 SELECT，自增主键回填")
    void persistAndFind() {
        try (Session s = sessionFactory.openSession()) {
            s.beginTransaction();
            Book b = new Book("Effective Java", "Joshua Bloch");
            s.persist(b);
            s.getTransaction().commit();

            assertNotNull(b.getId(), "IDENTITY 主键应回填进实体");

            Book found = s.find(Book.class, b.getId());
            assertEquals("Effective Java", found.getTitle());
            assertEquals("Joshua Bloch", found.getAuthor());
        }
    }

    @Test
    @DisplayName("脏检查（dirty checking）：托管对象改了字段，commit 时自动生成 UPDATE")
    void dirtyCheckingUpdate() {
        Long id;
        try (Session s = sessionFactory.openSession()) {
            s.beginTransaction();
            Book b = new Book("草稿", "mosslau");
            s.persist(b);
            id = b.getId();
            // 没有调用任何 update/save——托管状态下改属性即可
            b.setTitle("终稿");
            s.getTransaction().commit();   // Hibernate 比对快照，只把变化的列发 UPDATE
        }
        try (Session s = sessionFactory.openSession()) {
            assertEquals("终稿", s.find(Book.class, id).getTitle());
        }
    }

    @Test
    @DisplayName("JPQL 查询：面向对象而不是面向表（from Book 不是 from books）")
    void jpqlQuery() {
        try (Session s = sessionFactory.openSession()) {
            s.beginTransaction();
            s.persist(new Book("Java 编程思想", "Bruce Eckel"));
            s.persist(new Book("深入理解计算机系统", "Randal Bryant"));
            s.getTransaction().commit();

            List<Book> javaBooks = s.createQuery(
                    "from Book where title like :kw", Book.class)
                    .setParameter("kw", "%Java%")
                    .getResultList();

            assertEquals(1, javaBooks.size());
            assertEquals("Bruce Eckel", javaBooks.get(0).getAuthor());
            assertNull(s.find(Book.class, -1L), "不存在的主键返回 null");
        }
    }
}
