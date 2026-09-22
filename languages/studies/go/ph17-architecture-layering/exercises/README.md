# ph17 架构设计与代码分层练习

> 先自己做，再对照 `sol-*` 参考实现。每题标注难度（★~★★★）。四题与 roadmap §17 对齐：练习 1 ↔「重构 Todo API 分层」、练习 2 ↔「抽象存储接口」、练习 3 ↔「给 service 层写单元测试」、练习 4 ↔ 学习内容「错误码、接口边界（统一错误结构 + 边界映射）」。roadmap 推荐项目「分层 Web API 模板 / 节点管理服务」由本阶段 project/ 落地（选了后者）。
> 参考实现零第三方依赖，验证环境 go1.25.6（darwin/arm64），每条验收都能用 `go build ./... && go test ./... && go vet ./...` 检查——注意：参考实现已标注「已验证」（go1.25.6 本机实测 vet/build/test 全绿）；练习验收以你自己本机跑出的结果为准。

## 练习 1：重构 Todo API 分层（★★）

**目标**：把下面的单体 HTTP Todo 程序重构为 handler/service/repository（store）三层：业务规则（标题非空、存在才可切换/删除）全部移出 HTTP 层，存储从"全局 map 直接摊在 handler 里"收进独立的 repository，main 只做组装。

**要求**：
- 每个文件头注释写明验证环境与命令（参照 examples/ex01-three-layer 的文件头），整体标注「已验证」（go1.25.6 本机实测）
- handler 里不允许再出现"规则判断"（如 `title == ""` 的校验、`done[id] = !done[id]` 之外再夹业务）；出现规则就移到 service
- service 不感知 HTTP（不 import net/http、不出现状态码/JSON）
- repository 不感知业务规则，只做存与取

**起点代码（main.go，改造前；先在本机 `go build` 跑通再动手重构，已验证可构建）**：

```go
package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"strings"
	"sync"
)

// 存储、业务、HTTP 三者全部揉在一层：三个全局变量 + 六个闭包函数。

var (
	mu    sync.Mutex
	todos = map[string]string{} // id -> title
	done  = map[string]bool{}   // id -> 是否完成
	seq   = 0
)

func nextID() string {
	seq++
	return fmt.Sprintf("t%d", seq)
}

func handleList(w http.ResponseWriter, r *http.Request) {
	mu.Lock()
	defer mu.Unlock()
	out := []map[string]any{}
	for id, title := range todos {
		out = append(out, map[string]any{"id": id, "title": title, "done": done[id]})
	}
	_ = json.NewEncoder(w).Encode(out)
}

func handleCreate(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Title string `json:"title"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		http.Error(w, "bad json", http.StatusBadRequest)
		return
	}
	title := strings.TrimSpace(body.Title)
	if title == "" { // 业务规则混在 HTTP 层
		http.Error(w, "title required", http.StatusBadRequest)
		return
	}
	mu.Lock()
	id := nextID()
	todos[id] = title
	done[id] = false
	mu.Unlock()
	w.WriteHeader(http.StatusCreated)
}

func handleToggle(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/todos/toggle/")
	mu.Lock()
	defer mu.Unlock()
	if _, ok := todos[id]; !ok { // 存储判空直接写在 handler
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	done[id] = !done[id]
	w.WriteHeader(http.StatusNoContent)
}

func handleDelete(w http.ResponseWriter, r *http.Request) {
	id := strings.TrimPrefix(r.URL.Path, "/todos/delete/")
	mu.Lock()
	defer mu.Unlock()
	if _, ok := todos[id]; !ok {
		http.Error(w, "not found", http.StatusNotFound)
		return
	}
	delete(todos, id)
	delete(done, id)
	w.WriteHeader(http.StatusNoContent)
}

func main() {
	http.HandleFunc("GET /todos", handleList)
	http.HandleFunc("POST /todos", handleCreate)
	http.HandleFunc("POST /todos/toggle/", handleToggle)
	http.HandleFunc("POST /todos/delete/", handleDelete)
	_ = http.ListenAndServe(":18090", nil)
}
```

**验收**：
- 目录呈 `main.go + internal/{handler,service,store,todo}` 形态，包间 import 方向无环、单向向内
- 业务规则（标题非空、优先级合法等如果你加了）只在 service 出现一次
- `go build ./... && go vet ./...` 通过；`go test ./...` 至少能空跑通过（可顺带给 service 补两个规则单测，为练习 3 热身）

**提示**：sol-01-layered-todo 目录（带优先级字段的版本，避免照抄 examples/ex01）；先画出"谁 import 谁"再动手；对比起点代码里 `handleToggle` 直接读 map 与重构后 `service.Toggle → store.Get/Save` 的差异，体会每一层各回答什么问题。

## 练习 2：抽象存储接口（★★★）

**目标**：在练习 1 的分层结果上，把 service 对具体存储的依赖抽象成接口，让"内存 map"与"JSON 文件持久化"两种实现可以只改 main 一处就整体切换——验证 repository 真的隔离了存储细节。

**要求**：
- Store 接口定义在**消费方（service 包）**内，只含 service 用得到的方法（Get/Save/Delete/List 之类），方法签名不得出现具体存储类型
- 提供两种实现：内存 map（重启丢数据）与 JSON 文件（写操作后落盘，重启仍在）；两个实现都不 import service 包
- service 代码里不允许出现具体存储类型的名字；main 用一处 switch 选实现，并用 `var _ service.Store = (*xxx)(nil)` 做编译期断言
- "数据不存在"的哨兵错误放领域包（service 与实现都能引用），service 用 errors.Is 判断而不是字符串比较

**验收**：
- 给文件实现写往返测试：写两条 → 重新打开 → 数据仍在；删除后重开也生效（sol-02 有参考写法，用 `t.TempDir()`）
- 同一份 service 代码分别用两种存储跑通：内存版重启即空，文件版重启数据还在（对比运行即可证明"接口隔离了存储"）
- `go build ./... && go test ./... && go vet ./...` 通过

**提示**：sol-02-store-interface 目录（CLI 形态，`-store mem|file` 切换）；难点在"哨兵放哪"——放实现包会让 service import 实现（依赖方向反转），放领域包则两边都干净；文件实现的落盘顺序要排序，否则每次写入文件 diff 都乱跳。

## 练习 3：给 service 层写单元测试（★★★）

**目标**：给 service 层写表驱动单测，覆盖它的业务规则，全程不起 HTTP 服务器、不连真实存储——用测试替身（stub/fake）实现 Store 接口注入。

**要求**：
- 测试文件放在 service 包的**外部包**（`package service_test`），只通过导出 API 测试——这样能防住"测试偷用未导出的实现细节"
- 至少覆盖：非法输入（空 id / 空标题 / 全空白）→ 明确的哨兵错误；重复 id → 冲突错误且不覆盖原记录；标题去空白后落库；切换不存在的 todo → 领域 not-found 语义；存储层故障（替身注入 error）→ 原样透出不被吞
- 断言一律用 errors.Is / errors.As，不用 `err.Error() == "..."` 字符串比较
- 替身也要写 `var _ service.Store = (*stub)(nil)`，让接口签名变化立刻编译失败

**验收**：
- 每条规则至少一个用例；同类多条规则合成一个表驱动用例（t.Run 子测试）
- 跑 `go test -v ./...` 能看到每个子测试名，能说出每条规则对应哪个子测试
- `go test ./... && go vet ./...` 通过

**提示**：sol-03-service-unit-tests 目录；先列"规则清单"再写用例（每条规则一行），比对着代码盲写更不容易漏；stub 的 `getErr/saveErr` 字段是注入故障的开关——想想"存储坏了"这个用例为什么值得测（分层之后，service 的职责边界就是靠这类用例钉死的）。

## 练习 4：统一错误码与边界映射（★★）

**目标**：把分层服务的错误统一成"带稳定业务码的领域错误 + 边界处唯一映射"，让 handler 不再散落 if-else 猜错误，并让映射函数脱离服务器可单测。

**要求**：
- 领域错误携带稳定对外 Code（如 `ORDER_NOT_FOUND`）与给调用方的 Message；包装底层错误时根因必须保留（实现 Unwrap）
- service 只返回领域错误（不写 http 状态码）；HTTP 状态码只出现在一个映射函数里（如 `httperr.Map(err) (int, Body)`，Body 为 `{code, message}` 统一结构）
- 未知错误类型 / 未列出的 Code 一律兜底 500，且响应体不泄漏内部错误细节
- 单测覆盖：Code→状态码查表、包装链可被 errors.As 穿透、未知错误兜底 500

**验收**：
- 业务规则错误与未知错误走同一条映射路径，映射函数是纯函数（无副作用、可单测）
- `go test ./... && go vet ./...` 通过；能说清为什么"service 不知道 404 是什么"是一种优点
- 顺带思考（不要求写代码）：错误结构 `{code,message}` 一旦对外发布，字段只增不删——这与 roadmap §18 API 设计与兼容性阶段的联系是什么

**提示**：sol-04-error-codes 目录（订单支付/取消两条规则 + errs/orders/httperr 三包）；映射层用 errors.As 取回领域错误再 switch Code，别在 handler 里逐个错误类型判断；"根因链可追溯"用 `errors.Is(err, 存储哨兵)` 的测试钉住，防止有人把包装改成 `fmt.Errorf("%v", err)` 丢掉根因。

## 完成标准

- [ ] 练习 1~4 全部独立完成，每题先写自己的实现再对照 `sol-*` 复盘
- [ ] 每题都能跑通 `go build ./... && go test ./... && go vet ./...`（在你自己的 go1.25.x 环境）
- [ ] 能不看笔记说清：每层职责判定、接口为什么定义在使用方、哨兵/Code/包装链三者各管什么
- [ ] 完成后再动手 project/（综合项目：节点管理服务）
