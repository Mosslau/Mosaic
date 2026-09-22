// 来源：ph09-web-backend 练习 3 参考实现 —— 文件上传服务
// 一句话说明：httptest + multipart.Writer 构造上传请求：正常上传、穿越文件名清洗、
// 超限 413、缺字段 400、下载回看。上传目录注入 t.TempDir()，不污染仓库。
// 验证环境：go1.25.6（darwin/arm64）
// 运行：
//
//	go test -v ./...
//	go test -cover ./...
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"bytes"
	"encoding/json"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// withUploadDir 把上传目录切到临时目录并自动恢复
func withUploadDir(t *testing.T) string {
	t.Helper()
	old := uploadDir
	uploadDir = t.TempDir()
	t.Cleanup(func() { uploadDir = old })
	return uploadDir
}

// upload 辅助：构造 multipart 请求，返回 recorder
func upload(t *testing.T, h http.Handler, filename, content string) *httptest.ResponseRecorder {
	t.Helper()
	var buf bytes.Buffer
	mw := multipart.NewWriter(&buf)
	fw, err := mw.CreateFormFile("file", filename)
	if err != nil {
		t.Fatalf("构造 multipart 失败: %v", err)
	}
	fw.Write([]byte(content))
	mw.Close()

	req := httptest.NewRequest(http.MethodPost, "/upload", &buf)
	req.Header.Set("Content-Type", mw.FormDataContentType())
	rec := httptest.NewRecorder()
	h.ServeHTTP(rec, req)
	return rec
}

func TestUploadOK(t *testing.T) {
	dir := withUploadDir(t)
	rec := upload(t, newMux(), "report.txt", "hello world")

	if rec.Code != http.StatusOK {
		t.Fatalf("上传状态码 = %d, 期望 200, 响应: %s", rec.Code, rec.Body.String())
	}
	var resp struct {
		Name string `json:"name"`
		Size int64  `json:"size"`
		URL  string `json:"url"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("响应解析失败: %v", err)
	}
	if resp.Size != int64(len("hello world")) {
		t.Errorf("size = %d, 期望 %d", resp.Size, len("hello world"))
	}
	// 文件确实落盘且内容一致
	data, err := os.ReadFile(filepath.Join(dir, resp.Name))
	if err != nil {
		t.Fatalf("上传文件未落盘: %v", err)
	}
	if string(data) != "hello world" {
		t.Errorf("落盘内容 = %q, 期望 hello world", data)
	}
}

// TestUploadPathTraversal 穿越文件名被清洗：../../etc/passwd 只会得到 passwd
func TestUploadPathTraversal(t *testing.T) {
	dir := withUploadDir(t)
	rec := upload(t, newMux(), "../../etc/passwd", "pwned")

	var resp struct {
		Name string `json:"name"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("响应解析失败: %v", err)
	}
	if resp.Name == "" {
		t.Fatal("上传失败，无文件名返回")
	}
	if strings.Contains(resp.Name, "..") || strings.Contains(resp.Name, "/") {
		t.Errorf("文件名未清洗: %q", resp.Name)
	}
	if filepath.Base(resp.Name) != resp.Name {
		t.Errorf("文件名含路径成分: %q", resp.Name)
	}
	// 文件应落在上传目录内，而不是仓库根
	if _, err := os.Stat(filepath.Join(dir, resp.Name)); err != nil {
		t.Errorf("清洗后的文件未落盘到上传目录: %v", err)
	}
}

// TestUploadTooLarge 超 10MB：413（构造 10MB+1 的 body）
func TestUploadTooLarge(t *testing.T) {
	withUploadDir(t)
	rec := upload(t, newMux(), "big.bin", strings.Repeat("a", maxUploadSize+1))
	if rec.Code != http.StatusRequestEntityTooLarge {
		t.Errorf("超限上传状态码 = %d, 期望 413", rec.Code)
	}
}

// TestUploadMissingFile 无 file 字段：400
func TestUploadMissingFile(t *testing.T) {
	withUploadDir(t)
	req := httptest.NewRequest(http.MethodPost, "/upload", strings.NewReader("no file here"))
	req.Header.Set("Content-Type", "text/plain")
	rec := httptest.NewRecorder()
	newMux().ServeHTTP(rec, req)
	if rec.Code != http.StatusBadRequest {
		t.Errorf("缺 file 字段状态码 = %d, 期望 400", rec.Code)
	}
}

// TestDownload 上传后可经 /files/{name} 下载回看
func TestDownload(t *testing.T) {
	withUploadDir(t)
	rec := upload(t, newMux(), "report.txt", "hello world")

	var resp struct {
		Name string `json:"name"`
	}
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("响应解析失败: %v", err)
	}

	req := httptest.NewRequest(http.MethodGet, "/files/"+resp.Name, nil)
	drec := httptest.NewRecorder()
	newMux().ServeHTTP(drec, req)
	if drec.Code != http.StatusOK {
		t.Fatalf("下载状态码 = %d, 期望 200", drec.Code)
	}
	if drec.Body.String() != "hello world" {
		t.Errorf("下载内容 = %q, 期望 hello world", drec.Body.String())
	}
}
