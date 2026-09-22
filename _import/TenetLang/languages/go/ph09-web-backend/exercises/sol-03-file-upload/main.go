// 来源：ph09-web-backend 练习 3 参考实现 —— 文件上传服务
// 一句话说明：multipart 上传（MaxBytesReader 10MB 限制）+ filepath.Base + 时间戳防穿越防重名
// + http.ServeFile 回看；上传目录做成变量便于测试注入 t.TempDir()。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./...
//	go run .          # 监听 127.0.0.1:18080
//	echo hello > /tmp/demo.txt && curl -s -F "file=@/tmp/demo.txt" http://127.0.0.1:18080/upload
//	# 返回的 url 可直接访问：curl -s http://127.0.0.1:18080/files/<name>
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

const maxUploadSize = 10 << 20 // 10MB

// uploadDir 上传目录：默认 ./uploads，测试注入 t.TempDir() 避免污染仓库
var uploadDir = "./uploads"

func main() {
	if err := os.MkdirAll(uploadDir, 0o755); err != nil {
		log.Fatal(err)
	}
	addr := "127.0.0.1:18080"
	log.Printf("上传服务监听 http://%s，上传目录 %s", addr, uploadDir)
	if err := http.ListenAndServe(addr, newMux()); err != nil {
		log.Fatal(err)
	}
}

func newMux() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /upload", handleUpload)
	mux.HandleFunc("GET /files/{name}", handleDownload)
	return mux
}

func handleUpload(w http.ResponseWriter, r *http.Request) {
	// 1. 大小限制：超过 10MB 立即截断并返回 413（必须在 FormFile 之前挂）
	r.Body = http.MaxBytesReader(w, r.Body, maxUploadSize)

	// 2. 取文件
	file, header, err := r.FormFile("file")
	if err != nil {
		var tooLarge *http.MaxBytesError
		if errors.As(err, &tooLarge) {
			writeError(w, http.StatusRequestEntityTooLarge, "FILE_TOO_LARGE", "文件超过 10MB 限制")
			return
		}
		writeError(w, http.StatusBadRequest, "INVALID_PARAM", "缺少 file 字段")
		return
	}
	defer file.Close()

	// 3. 命名：filepath.Base 剥掉路径成分防穿越（../../etc/passwd → passwd），
	//    时间戳前缀防重名覆盖
	name := fmt.Sprintf("%d-%s", time.Now().UnixNano(), filepath.Base(header.Filename))

	// 4. 落盘：Create 已隐含覆盖检查；写完后 Sync 可选（演示省略）
	dst, err := os.Create(filepath.Join(uploadDir, name))
	if err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL", "保存文件失败")
		return
	}
	defer dst.Close()
	if _, err := io.Copy(dst, file); err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL", "写入文件失败")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"name": name,
		"size": header.Size,
		"url":  "/files/" + name,
	})
}

// handleDownload 回看：http.ServeFile 按名取文件（路径已由 {name} 限定单段，天然无穿越）
func handleDownload(w http.ResponseWriter, r *http.Request) {
	path := filepath.Join(uploadDir, r.PathValue("name"))
	http.ServeFile(w, r, path)
}

func writeJSON(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	if err := json.NewEncoder(w).Encode(v); err != nil {
		log.Printf("响应编码失败: %v", err)
	}
}

func writeError(w http.ResponseWriter, status int, code, msg string) {
	writeJSON(w, status, map[string]string{"code": code, "message": msg})
}
