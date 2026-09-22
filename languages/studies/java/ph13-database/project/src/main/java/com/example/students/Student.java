package com.example.students;

/** 学生实体：record 不可变，天然适合做「从 ResultSet 映射出来的数据」 */
public record Student(long id, String name, String email, int grade) {}
