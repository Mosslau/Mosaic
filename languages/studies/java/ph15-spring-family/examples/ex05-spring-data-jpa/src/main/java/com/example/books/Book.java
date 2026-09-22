package com.example.books;

import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;

/**
 * JPA 实体：@Entity + @Id 即映射为表（默认物理表名/列名按 snake_case：book_year）。
 * 教学点：实体只声明「形状」，不写任何 SQL——表由 Hibernate ddl-auto 生成，访问走 Repository。
 */
@Entity
public class Book {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    private String title;

    private String author;

    private int year;

    protected Book() {
        // JPA 规范要求无参构造（供 Hibernate 反射实例化）；业务创建走带参构造
    }

    public Book(String title, String author, int year) {
        this.title = title;
        this.author = author;
        this.year = year;
    }

    public Long getId() {
        return id;
    }

    public String getTitle() {
        return title;
    }

    public String getAuthor() {
        return author;
    }

    public int getYear() {
        return year;
    }
}
