// 来源：07-stdlib.md 第 6 章示例 3 —— HTTP API server（net/http + json 响应 + 路由）
// 一句话说明：内存设备表 + 精确/前缀路由 + json.NewEncoder 响应 + 显式 Read/Write 超时。
// 验证环境：Go 1.22.2（darwin/arm64）
// 运行：
//
//	go run .
//	curl http://127.0.0.1:8080/devices/car-001
//
// 验证状态：已验证（Go 1.22.2）
package main

import (
	"encoding/json"
	"log"
	"net/http"
	"time"
)

type Device struct {
	ID     string  `json:"id"`
	Status string  `json:"status"`
	Speed  float64 `json:"speed"`
}

func main() {
	devices := map[string]Device{ // 内存数据（真实项目用数据库，见 ph10）
		"car-001": {ID: "car-001", Status: "online", Speed: 60.5},
	}
	http.HandleFunc("/devices", func(w http.ResponseWriter, r *http.Request) { // 全部设备
		list := make([]Device, 0, len(devices))
		for _, d := range devices {
			list = append(list, d)
		}
		writeJSON(w, http.StatusOK, list)
	})
	http.HandleFunc("/devices/", func(w http.ResponseWriter, r *http.Request) { // 单个设备
		id := r.URL.Path[len("/devices/"):]
		if d, ok := devices[id]; ok {
			writeJSON(w, http.StatusOK, d)
			return
		}
		writeJSON(w, http.StatusNotFound, map[string]string{"error": "device not found"})
	})
	srv := &http.Server{Addr: "127.0.0.1:8080", ReadTimeout: 5 * time.Second, WriteTimeout: 10 * time.Second}
	log.Println("API 服务启动: http://127.0.0.1:8080")
	log.Fatal(srv.ListenAndServe())
}

// writeJSON 统一 JSON 响应：Content-Type 与状态码
func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Println("写入响应失败:", err)
	}
}
