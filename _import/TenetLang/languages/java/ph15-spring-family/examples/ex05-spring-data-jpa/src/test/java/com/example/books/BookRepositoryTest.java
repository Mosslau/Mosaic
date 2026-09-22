package com.example.books;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

/**
 * ex05 测试：Spring Data JPA 的行为实测——开箱 CRUD / 方法名派生查询 / @Query JPQL /
 * 分页排序 / Service 层事务回滚。
 * 验证命令：mvn -o -Dmaven.repo.local=/tmp/m2clone test
 */
@SpringBootTest
class BookRepositoryTest {

    @Autowired
    private BookRepository repository;

    @Autowired
    private BookService bookService;

    @BeforeEach
    void seed() {
        repository.deleteAll();
        repository.saveAll(List.of(
                new Book("Spring 实战", "Craig Walls", 2014),
                new Book("Java 编程思想", "Bruce Eckel", 2006),
                new Book("深入理解 Java 虚拟机", "周志明", 2013),
                new Book("Effective Java", "Joshua Bloch", 2018)
        ));
    }

    /** JpaRepository 开箱 CRUD：save 回填 id、findAll 全量、deleteById 可删 */
    @Test
    void crudWorksOutOfTheBox() {
        assertThat(repository.findAll()).hasSize(4);
        Book saved = repository.save(new Book("Clean Code", "Robert C. Martin", 2008));
        assertThat(saved.getId()).isNotNull(); // 主键由数据库回填
        assertThat(repository.findAll()).hasSize(5);
        repository.deleteById(saved.getId());
        assertThat(repository.findAll()).hasSize(4);
    }

    /** 方法名派生查询：findByXxxContaining / existsByXxx / countByXxx 自动翻译成 SQL */
    @Test
    void derivedQueriesFromMethodNames() {
        List<Book> containing = repository.findByTitleContainingIgnoreCase("java");
        assertThat(containing).extracting(Book::getTitle)
                .containsExactlyInAnyOrder("Java 编程思想", "深入理解 Java 虚拟机", "Effective Java");

        assertThat(repository.existsByAuthor("Bruce Eckel")).isTrue();
        assertThat(repository.existsByAuthor("Nobody")).isFalse();

        assertThat(repository.countByYearAfter(2010)).isEqualTo(3); // 2013/2014/2018

        List<Book> byAuthor = repository.findByAuthorOrderByYearDesc("Craig Walls");
        assertThat(byAuthor).extracting(Book::getTitle).containsExactly("Spring 实战");
    }

    /** @Query 显式 JPQL：方法名表达不动的查询（>= 下限 + 排序）与 Optional 单查 */
    @Test
    void explicitJpqlQueries() {
        List<Book> recent = repository.findRecentBooks(2012);
        assertThat(recent).extracting(Book::getTitle)
                .containsExactly("Effective Java", "Spring 实战", "深入理解 Java 虚拟机"); // year desc

        assertThat(repository.findByExactTitle("Spring 实战")).isPresent();
        assertThat(repository.findByExactTitle("不存在的书")).isEmpty();
    }

    /** 分页 + 排序：findAll(Pageable) 返回 Page（含总数），不整表拉回内存 */
    @Test
    void paginationAndSorting() {
        Page<Book> page = repository.findAll(
                PageRequest.of(0, 2, Sort.by(Sort.Direction.DESC, "year")));
        assertThat(page.getTotalElements()).isEqualTo(4); // 总条数由 COUNT 查询得出
        assertThat(page.getContent()).extracting(Book::getTitle)
                .containsExactly("Effective Java", "Spring 实战"); // 前两新
        Page<Book> page2 = repository.findAll(PageRequest.of(1, 2, Sort.by(Sort.Direction.DESC, "year")));
        assertThat(page2.getContent()).extracting(Book::getTitle)
                .containsExactly("深入理解 Java 虚拟机", "Java 编程思想"); // 后两旧
    }

    /** Service 层事务：两本书的导入要么全成要么全滚（运行时异常默认回滚，见 ex04 规则） */
    @Test
    void serviceTransactionRollsBackBothInserts() {
        assertThatThrownBy(() -> bookService.importTwoThenFail(
                new Book("书 A", "作者甲", 2020), new Book("书 B", "作者乙", 2021)))
                .isInstanceOf(IllegalStateException.class);

        assertThat(repository.findAll()).hasSize(4); // seed 的 4 本之外没有任何残留
    }
}
