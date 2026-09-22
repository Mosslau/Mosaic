package com.example.books;

import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.List;
import java.util.Optional;

/**
 * Spring Data 仓库：只写接口，不写实现。
 * - 继承 JpaRepository<Book, Long>：getId 型 CRUD / findAll(Pageable) / deleteById 全部开箱
 * - 方法名即查询：Spring Data 启动时按「Subject + 谓词」推导 JPQL（findByTitleContaining 等）
 * - @Query 显式声明：方法名表达不了（或要手写 SQL/JPQL）时用
 * 「接口 + 命名约定 = 实现」是 Spring Data 的灵魂——ph13 手写的 DAO、ph14 手写的 VehicleStore
 * 在这里消失，但接口形状（findById 返回 Optional、按字段查）一脉相承。
 */
public interface BookRepository extends JpaRepository<Book, Long> {

    /** 派生查询：标题包含（不区分大小写） */
    List<Book> findByTitleContainingIgnoreCase(String keyword);

    /** 派生查询：是否存在某作者的书（exists 开头 → 布尔） */
    boolean existsByAuthor(String author);

    /** 派生查询：统计某年之后的藏书量（count 开头 → long） */
    long countByYearAfter(int year);

    /** 派生查询：按作者查并按出版年倒序（OrderBy + Desc 尾巴） */
    List<Book> findByAuthorOrderByYearDesc(String author);

    /** @Query 显式 JPQL：方法名表达不动的查询（年份下限 + 排序） */
    @Query("select b from Book b where b.year >= :minYear order by b.year desc")
    List<Book> findRecentBooks(@Param("minYear") int minYear);

    /** @Query 配 Optional：单本精确查询（title 唯一场景） */
    @Query("select b from Book b where b.title = :title")
    Optional<Book> findByExactTitle(@Param("title") String title);
}
