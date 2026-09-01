# ph12 单元测试与工程质量 示例

> 每个示例是主文档「6. 代码示例」对应示例的完整可运行版，覆盖「JUnit 5 基础 → 参数化 → 替身（Mockito / 手工）→ AssertJ → 覆盖率」的完整链路。验证环境：**OpenJDK 17.0.18（`javac -version` → 17.0.18）+ Maven 3.9.12（`mvn -version` → 3.9.12）+ JUnit Jupiter 5.10.1**。

## 验证方式说明（重要）

本机 Maven 实测采用**离线模式 `mvn -o`**：本环境沙箱禁止写默认本地仓库 `~/.m2`（`Operation not permitted`），所需构件（junit-jupiter 5.10.1、mockito-core 5.11.0、assertj-core 3.25.3、jacoco-maven-plugin 0.8.11 等）取自本地仓库缓存；沙箱内构建用 `mvn -o -Dmaven.repo.local=/tmp/m2clone`（把本地仓库指向可写目录的克隆）。**在正常联网环境直接执行 `mvn test` 即可**（首次运行会从 Maven Central 下载，之后走本地缓存）。

ex03/ex05 的 pom 里带了「离线版本仲裁」注释的依赖（byte-buddy、objenesis）：Mockito 5.11.0 声明 byte-buddy 1.14.12 / objenesis 3.3、AssertJ 3.25.3 声明 byte-buddy 1.14.11，本机缓存只有 1.14.13 / 3.2，用直接依赖压过传递版本（机制见 ph11 主文档 4.3 依赖冲突仲裁）。**正常联网环境可删除这三项**，让 Mockito/AssertJ 自行拉取声明版本。

## 示例列表

| 目录/文件 | 验证状态 | 说明 | 测试命令（工程目录内） | 实测结果 |
|-----------|---------|------|------------------------|---------|
| ex01-junit5-basic/ | ✅ 已验证 | JUnit 5 断言（正常 + 错误路径）+ 生命周期（@BeforeEach/@AfterEach/@BeforeAll/@AfterAll）+ assertAll | `mvn test` | Tests run: **3** |
| ex02-parameterized/ | ✅ 已验证 | 参数化测试：@ValueSource / @NullAndEmptySource / @CsvSource / @MethodSource | `mvn test` | Tests run: **14** |
| ex03-mockito/ | ✅ 已验证 | Mockito：@Mock + when/thenReturn + thenThrow + verify/never/argThat | `mvn test` | Tests run: **5** |
| ex04-handmade-stub/ | ✅ 已验证 | 手工替身（零框架）：FixedClock stub + CountingClock spy + 边界值测试 | `mvn test` | Tests run: **6** |
| ex05-assertj/ | ✅ 已验证 | AssertJ 流式断言：hasSize/extracting/containsExactly/assertThatThrownBy | `mvn test` | Tests run: **5** |
| ex06-jacoco-coverage/ | ✅ 已验证 | JaCoCo 覆盖率：只测 add 不测 divide，报告显示覆盖率缺口 | `mvn test` 后开 target/site/jacoco/index.html | Tests run: **1**；指令覆盖率 **63.6%**（7/11）、行 2/3、方法 2/3 |
| ex07-testcontainers.md | ⚠️ 未在本环境验证 | Testcontainers 概念文档（需要 Docker 守护进程，本沙箱无） | —（概念 + 标准用法片段） | — |

## 验证记录（实测输出要点）

### ex01：JUnit 5 断言与生命周期

- `mvn test` → `Tests run: 3, Failures: 0, Errors: 0, Skipped: 0`
- 控制台按 beforeAll → beforeEach →（3 个测试各配 before/after）→ afterEach → afterAll 顺序打印 —— 生命周期顺序实测可见
- 错误路径测试用 `assertThrows(IllegalArgumentException.class, () -> calculator.divide(10, 0))`，并断言异常消息 `除数不能为 0`

### ex02：参数化测试

- `mvn test` → `Tests run: 14`（4 个参数化方法 × 3/3/4/4 组数据 = 14 次执行；surefire 把每次参数执行计为一个测试）
- **实测语义坑**：`@CsvSource` 中**裸空单元格 → null**、**引号包裹 `''` → 空串 `""`**——第一个版本写成 `"'',"`（第二格裸空）预期 null 失败，改为 `"'',''"` 后通过；这正是「参数化测试的数据语义要实测确认」的教材

### ex03：Mockito

- `mvn test` → `Tests run: 5`
- 覆盖：stub 正常返回值、stub 空 Optional（错误路径）、stub 抛异常（模拟数据库故障）、`verify(...)` 验证交互发生、`verify(repo, never()).save(...)` 验证「没有发生」、`argThat(...)` 参数匹配
- 首次运行有 JVM 提示 `Sharing is only supported for boot loader classes...`（Mockito inline mock maker 的已知无害提示）

### ex04：手工替身

- `mvn test` → `Tests run: 6`
- `Clock.FixedClock`（固定时间 stub）覆盖营业/非营业/两个边界小时（9:00 开、18:00 关）；`Clock.CountingClock`（计数 spy）验证 `now()` 每次判定恰好调用一次——**不用任何 mock 框架也能验证交互**
- 生产代码 `OpeningHours` 固定用 UTC 而非系统默认时区——演示「时间相关代码的时区必须显式决定」，否则测试在不同时区机器上结果不同

### ex05：AssertJ

- `mvn test` → `Tests run: 5`
- 链式断言 `assertThat(cart.items()).hasSize(2).extracting(Item::name).containsExactly(...)`；异常断言 `assertThatThrownBy(...).isInstanceOf(...).hasMessageContaining(...)`
- `items()` 的防御性拷贝（`List.copyOf`）被测试验证：向返回列表写数据抛 `UnsupportedOperationException`

### ex06：JaCoCo 覆盖率

- `mvn test`（Jacoco prepare-agent + report 两个 execution）→ `Tests run: 1`，报告生成在 `target/site/jacoco/index.html`
- `target/site/jacoco/jacoco.csv` 中 Calculator 一行实测：
  - 指令覆盖率 **7/11（63.6%）** —— add 的指令被覆盖，divide 的没有
  - 行覆盖率 2/3、方法覆盖率 2/3（divide 未测）
- 把 divide 补一个测试（含除零错误路径）后三类数字变 100%——可自行验证「覆盖率 = 测到的 ÷ 全部」

## 产物清理

每个 Maven 工程验证后 `target/` 为构建产物，提交前统一清理：

```bash
# 在 examples/ 目录执行
for d in ex01-junit5-basic ex02-parameterized ex03-mockito ex04-handmade-stub ex05-assertj ex06-jacoco-coverage; do
  (cd "$d" && mvn -o -q -Dmaven.repo.local=/tmp/m2clone clean)
done
```

（正常联网环境把 `mvn -o -q -Dmaven.repo.local=/tmp/m2clone clean` 换成 `mvn clean` 即可。）
