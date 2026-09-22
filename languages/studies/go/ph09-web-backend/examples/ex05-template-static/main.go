// 来源：09-web-backend.md 第 6 章示例 5 —— 模板渲染 + 静态文件
// 一句话说明：html/template 渲染设备状态页（自动 HTML 转义防 XSS）+ 表单 POST 添加设备
// + http.FileServer 提供 /static 静态资源——"给人看的页面"用模板，"给程序看的"用 JSON。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go run .
//	open http://127.0.0.1:18080/devices       # 模板页面
//	open http://127.0.0.1:18080/static/style.css  # 静态文件
//	curl -s -X POST http://127.0.0.1:18080/devices -d 'device_id=car-009&status=online&speed=88.5'
//
// 测试：
//
//	go test -v ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"html/template"
	"log"
	"net/http"
	"strconv"
	"sync"
)

// Device 页面数据模型
type Device struct {
	ID     string
	Status string
	Speed  float64
}

// store 内存存储（Mutex 保护，同 ex01/ex03）
type store struct {
	mu    sync.RWMutex
	items map[string]Device
}

func newStore() *store {
	return &store{items: map[string]Device{
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
		"car-002": {ID: "car-002", Status: "offline", Speed: 0},
	}}
}

// tmpl 解析一次、请求时复用（template.Must：启动期失败直接 panic，比运行时才发现好）
var tmpl = template.Must(template.ParseFiles("templates/devices.html"))

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("模板示例监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux(newStore())); err != nil {
		log.Fatal(err)
	}
}

func newMux(s *store) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("GET /devices", handleList(s))
	mux.HandleFunc("POST /devices", handleCreate(s)) // 表单提交（urlencoded），不是 JSON
	// 静态文件：StripPrefix 剥掉 /static 前缀后交给 FileServer 找 static/ 目录下的文件
	mux.Handle("/static/", http.StripPrefix("/static/", http.FileServer(http.Dir("static"))))
	return mux
}

func handleList(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		s.mu.RLock()
		list := make([]Device, 0, len(s.items))
		for _, d := range s.items {
			list = append(list, d)
		}
		s.mu.RUnlock()
		// Execute 把数据填充进模板写回响应；模板错误也要处理（不能静默）
		if err := tmpl.Execute(w, list); err != nil {
			log.Printf("模板渲染失败: %v", err)
			http.Error(w, "模板渲染失败", http.StatusInternalServerError)
		}
	}
}

func handleCreate(s *store) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		// 表单参数用 ParseForm + r.FormValue；校验仍手写
		if err := r.ParseForm(); err != nil {
			http.Error(w, "表单解析失败", http.StatusBadRequest)
			return
		}
		id := r.FormValue("device_id")
		status := r.FormValue("status")
		speed, err := strconv.ParseFloat(r.FormValue("speed"), 64)
		if id == "" {
			http.Error(w, "device_id 不能为空", http.StatusBadRequest)
			return
		}
		if status != "online" && status != "offline" {
			http.Error(w, "status 只能是 online 或 offline", http.StatusBadRequest)
			return
		}
		if err != nil || speed < 0 || speed > 300 {
			http.Error(w, "speed 必须是 0~300 的数字", http.StatusBadRequest)
			return
		}
		s.mu.Lock()
		s.items[id] = Device{ID: id, Status: status, Speed: speed}
		s.mu.Unlock()
		http.Redirect(w, r, "/devices", http.StatusSeeOther) // 303 回列表页（PRG 模式防重复提交）
	}
}
