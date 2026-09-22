// 来源：09-web-backend.md 第 6 章示例 4 —— JWT 认证（手写 HS256）
// 一句话说明：登录签发 JWT + 中间件验签鉴权（Bearer 解析 → 验签 → 用户名写入 context）。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go run .
//	curl -s -X POST http://127.0.0.1:18080/login -d '{"username":"admin","password":"123456"}'
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"context"
	"encoding/json"
	"log"
	"net/http"
	"strings"
	"time"
)

// 生产注意：secret 放环境变量并定期轮换；users 存数据库 + 密码哈希（ph10 内容），此处演示简化
var (
	secret = []byte("please-change-me-in-production")
	users  = map[string]string{"admin": "123456"} // username → 明文密码（仅演示）
)

// ctxKey 私有类型做 context 键，避免与其他包冲突（go vet 也建议不用基础类型做键）
type ctxKey struct{}

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("JWT 认证示例监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux()); err != nil {
		log.Fatal(err)
	}
}

func newMux() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /login", handleLogin)
	// 分组式保护：子 mux 挂上鉴权中间件，只有 /api 下的路由需要登录。
	// 子 mux 的模式不带 /api 前缀，必须用 http.StripPrefix 把前缀剥掉再交给它
	api := http.NewServeMux()
	api.HandleFunc("GET /profile", handleProfile)
	mux.Handle("/api/", requireAuth(http.StripPrefix("/api", api)))
	return mux
}

func handleLogin(w http.ResponseWriter, r *http.Request) {
	var cred struct {
		Username string `json:"username"`
		Password string `json:"password"`
	}
	if err := json.NewDecoder(r.Body).Decode(&cred); err != nil {
		writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
		return
	}
	if users[cred.Username] != cred.Password { // 演示简化：直接比对（生产用 bcrypt，ph10）
		writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "用户名或密码错误")
		return
	}
	token, err := signJWT(map[string]any{"username": cred.Username}, secret, 2*time.Hour)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "INTERNAL", "签发 token 失败")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"token": token})
}

// requireAuth 鉴权中间件：解析 Bearer → 验签 → 用户名写入 context → 放行
func requireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if !ok {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "缺少 Bearer token")
			return
		}
		claims, err := verifyJWT(token, secret)
		if err != nil {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", err.Error())
			return
		}
		ctx := context.WithValue(r.Context(), ctxKey{}, claims["username"])
		next.ServeHTTP(w, r.WithContext(ctx))
	})
}

func handleProfile(w http.ResponseWriter, r *http.Request) {
	username, _ := r.Context().Value(ctxKey{}).(string)
	writeJSON(w, http.StatusOK, map[string]string{"username": username})
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
