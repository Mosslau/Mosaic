# ph07 标准库阶段练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★），建议按 1 → 2 → 3 → 4 顺序完成。

运行方式：每个参考实现是**独立的 Go module**（目录内自带 go.mod），先进入对应目录再运行（如 `cd sol-01-file-stats && go run . <文件路径>`）。请勿在 exercises/ 根目录执行 `go build ./...`——根目录没有 go.mod。

## 练习 1：文件统计工具（★）

**目标**：统计指定文本文件的行数、单词数、字节数，模仿 Unix `wc` 的输出格式。

**要求**：

- 命令行接收一个文件路径参数；参数缺失或文件打不开时给出清晰错误提示并非零退出
- 用 `bufio.Scanner` 逐行读取（不允许把整个文件一次性读入内存）
- 单词按空白切分统计（`strings.Fields`）
- 记得检查 `scanner.Err()`，扫描中途出错也要报告

**验收**：对一份已知内容的文件（如 3 行、共 10 个单词），输出行数/单词数与手工计数一致；对不存在的路径给出错误提示并以非零状态退出。

## 练习 2：JSON 配置解析器（★★）

**目标**：读取 JSON 配置文件，解析为结构体，并做必填项与取值范围校验。

**要求**：

- 配置至少包含：服务地址（host/port，嵌套对象）、日志级别、超时秒数
- 用结构体 tag 映射 JSON 字段；未导出字段不参与序列化
- 错误逐层用 `%w` 包装（读取失败 / 解析失败 / 校验失败三类要可区分）
- 校验规则示例：port 必须在 1~65535，log_level 必须是 debug/info/warn/error 之一
- 提供命令行参数指定配置文件路径

**验收**：合法配置打印解析结果；缺 port、port 为 0、log_level 非法、JSON 语法错误、文件不存在五种坏输入分别得到可区分的错误信息。

## 练习 3：HTTP API server（★★★）

**目标**：用 net/http 手写一个设备管理 API，返回 JSON，带方法校验与显式超时。

**要求**：

- `GET /devices` 返回全部设备列表；`GET /devices/{id}` 返回单个设备，不存在返回 404 JSON
- 非 GET 方法返回 405；响应统一带 `Content-Type: application/json`
- 用 `http.Server` 显式设置 ReadTimeout / WriteTimeout / IdleTimeout
- 设备数据用内存 map 即可（真实数据库属 ph10）
- **给核心 handler 补单元测试**：用 `net/http/httptest` 断言状态码与响应体（这是 Go 测 HTTP handler 的标准做法，不用真正起端口）

**验收**：`curl` 验证列表、单查、404、405 四种情形；`go test -v` 全部通过；`go vet` 零报告。

## 练习 4：命令行 Todo 工具（★★）

**目标**：支持 add / list / done 三个动作的 Todo CLI，JSON 文件持久化。

**要求**：

- `-add "内容"` 新增、`-list` 列出（带编号与完成标记）、`-done N` 把第 N 条标记完成
- 数据用 JSON 持久化到文件（`json.MarshalIndent` 美化输出），重启不丢
- `-done` 的编号越界要给出错误提示，不允许 panic
- 无参数时打印用法（`flag.PrintDefaults`）
- **给 load/save 与 done 逻辑补表驱动单元测试**（测试用 `t.TempDir()` 拿临时目录，不要污染真实存储文件）

**验收**：连续执行 add/add/done/list 后列表状态正确；`go test -v` 全部通过。

---

四个练习与 `sol-*` 参考实现一一对应（sol-01 ~ sol-04），全部做完再对照复盘。
