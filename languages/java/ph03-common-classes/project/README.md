# ph03 阶段项目：验证码生成器

## 需求

对应 Roadmap「ph03 Java 常用类阶段」推荐项目第一个。实现一个可配置的验证码生成器：支持三种字符集（纯数字 / 纯字母 / 混合），可指定长度，支持批量生成。核心目标是练熟 `StringBuilder`（拼接）、`Random`（随机取样）、枚举（表达字符集）、封装（生成逻辑集中在 `CaptchaGenerator` 类，`CaptchaApp` 只做命令行入口）。

## 功能清单

- [ ] 支持三种字符集：纯数字（`digits`）、纯字母（`letters`）、混合（`mixed`）
- [ ] 混合字符集去除易混淆字符 `I`/`O`/`0`/`1`，降低人工辨识成本
- [ ] 可配置验证码长度（`length`）
- [ ] 可配置批量生成数量（`count`）
- [ ] 字符集用枚举 `CaptchaGenerator.Charset` 表达，生成逻辑封装在 `CaptchaGenerator` 类
- [ ] CLI 入口 `CaptchaApp` 支持命令行参数 `[长度] [数量] [字符集]`，缺省用默认值（6 位、5 个、混合）

## 验收标准

- `javac CaptchaGenerator.java CaptchaApp.java` 编译零错误
- `java CaptchaApp` 输出 5 个 6 位混合验证码
- `java CaptchaApp 8 3 digits` 输出 3 个 8 位纯数字验证码
- `java CaptchaApp 4 2 letters` 输出 2 个 4 位纯字母验证码
- `mixed` 字符集生成的验证码不含 `I`/`O`/`0`/`1`

## 扩展方向（可选）

- 用 `SecureRandom` 替代 `Random`，生成密码学安全的验证码 —— 涉及安全主题，属后续阶段
- 为验证码加校验逻辑（生成时保存、提交时比对），把「生成」和「校验」拆成两个类 —— OOP 建模的深化（ph02 已打基础）
- 加失效时间与防暴力破解限制 —— 并发与安全主题，属后续阶段
- 支持更多字符集（如纯大写、十六进制）—— 扩展枚举即可

## 验证环境

OpenJDK 17.0.16。

```bash
# 1. 编译
javac CaptchaGenerator.java CaptchaApp.java
# 2. 运行（无参，默认 6 位 / 5 个 / 混合）
java CaptchaApp
# 3. 运行（带参：8 位 / 3 个 / 纯数字）
java CaptchaApp 8 3 digits
```

已在本环境用 OpenJDK 17.0.16 编译运行验证（零错误，三种字符集与批量生成均符合预期）。
