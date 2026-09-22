package com.example;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Table;

/**
 * JPA 实体：注解把 Java 类映射到表，属性映射到列。
 * ORM 的心智：你操作的是对象，Hibernate 负责生成 SQL。
 */
@Entity
@Table(name = "books")
public class Book {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false, length = 128)
    private String title;

    @Column(length = 64)
    private String author;

    /** JPA 要求实体有 protected/public 无参构造（代理与反射用） */
    protected Book() {}

    public Book(String title, String author) {
        this.title = title;
        this.author = author;
    }

    public Long getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    /** setter 开放给「变更」——托管状态下改字段，提交时 Hibernate 自动发 UPDATE（脏检查） */
    public void setTitle(String title) {
        this.title = title;
    }

    public String getAuthor() {
        return author;
    }
}
