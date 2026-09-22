package com.example;

import java.util.List;
import org.apache.ibatis.annotations.Param;

/** Mapper 接口：方法签名即数据访问契约，SQL 在同名 XML（UserMapper.xml）里 */
public interface UserMapper {

    long insert(User user);

    User findById(long id);

    List<User> findAll();

    int updateEmail(@Param("id") long id, @Param("email") String email);

    int delete(long id);
}
