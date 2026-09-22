package com.example.books;

import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Service 层事务边界：批量导入两条后抛异常 → 仓库方法各自是原子操作，
 * 但「多步业务要么全成要么全滚」的边界必须由 Service 的 @Transactional 定义
 * （与 ex04 同一规则：运行时异常默认回滚）。
 */
@Service
public class BookService {

    private final BookRepository repository;

    public BookService(BookRepository repository) {
        this.repository = repository;
    }

    @Transactional
    public void importTwoThenFail(Book first, Book second) {
        repository.save(first);
        repository.save(second);
        throw new IllegalStateException("模拟导入中途失败");
    }
}
