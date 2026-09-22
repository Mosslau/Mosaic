// 来源：ph09-web-backend 练习 2 参考实现 —— 登录注册 + JWT（手写 HS256）
// 一句话说明：注册（409 查重）+ 登录（401 校验）+ 手写 JWT 签发/验签 + 鉴权中间件保护 /api/profile。
// 验证环境：go1.25.6（darwin/arm64），仅标准库
// 运行：
//
//	go test -v ./...
//	go run .          # 监听 127.0.0.1:18080
//	curl -s -X POST http://127.0.0.1:18080/register -d '{"username":"alice","password":"pw"}'
//	curl -s -X POST http://127.0.0.1:18080/login -d '{"username":"alice","password":"pw"}'
//
// 验证状态：已验证（go1.25.6）
package main

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/base64"
	"encoding/json"
	"errors"
	"log"
	"net/http"
	"strings"
	"sync"
	"time"
)

// userStore 内存用户表：注册写入、登录比对（演示用明文；生产存哈希 + 数据库，见 ph10）
type userStore struct {
	mu    sync.RWMutex
	users map[string]string
}

func newUserStore() *userStore {
	return &userStore{users: make(map[string]string)}
}

func (s *userStore) register(username, password string) error {
	s.mu.Lock()
	defer s.mu.Unlock()
	if _, exists := s.users[username]; exists {
		return errors.New("duplicate")
	}
	s.users[username] = password
	return nil
}

func (s *userStore) check(username, password string) bool {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.users[username] == password
}

// --- 手写 HS256 JWT（RFC 7519 最小实现） ---

var secret = []byte("exercise-secret-change-me") // 生产放环境变量并轮换

func signJWT(claims map[string]any, ttl time.Duration) (string, error) {
	withExp := make(map[string]any, len(claims)+1)
	for k, v := range claims {
		withExp[k] = v
	}
	withExp["exp"] = time.Now().Add(ttl).Unix()

	header, err := json.Marshal(map[string]string{"alg": "HS256", "typ": "JWT"})
	if err != nil {
		return "", err
	}
	payload, err := json.Marshal(withExp)
	if err != nil {
		return "", err
	}
	enc := base64.RawURLEncoding
	signing := enc.EncodeToString(header) + "." + enc.EncodeToString(payload)

	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(signing))
	return signing + "." + enc.EncodeToString(mac.Sum(nil)), nil
}

func verifyJWT(token string) (map[string]any, error) {
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		return nil, errors.New("token 格式错误")
	}
	enc := base64.RawURLEncoding
	signing := parts[0] + "." + parts[1]

	mac := hmac.New(sha256.New, secret)
	mac.Write([]byte(signing))
	// hmac.Equal 常数时间比较，防时序侧信道
	if !hmac.Equal([]byte(parts[2]), []byte(enc.EncodeToString(mac.Sum(nil)))) {
		return nil, errors.New("签名不匹配")
	}
	payload, err := enc.DecodeString(parts[1])
	if err != nil {
		return nil, errors.New("payload 解码失败")
	}
	var claims map[string]any
	if err := json.Unmarshal(payload, &claims); err != nil {
		return nil, errors.New("payload 不是合法 JSON")
	}
	exp, ok := claims["exp"].(float64)
	if !ok || time.Now().Unix() > int64(exp) {
		return nil, errors.New("token 已过期")
	}
	return claims, nil
}

func main() {
	addr := "127.0.0.1:18080"
	log.Printf("认证服务监听 http://%s", addr)
	if err := http.ListenAndServe(addr, newMux(newUserStore())); err != nil {
		log.Fatal(err)
	}
}

func newMux(users *userStore) http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /register", handleRegister(users))
	mux.HandleFunc("POST /login", handleLogin(users))
	api := http.NewServeMux()
	api.HandleFunc("GET /profile", handleProfile)
	mux.Handle("/api/", requireAuth(http.StripPrefix("/api", api))) // 子 mux + StripPrefix 分组
	return mux
}

func handleRegister(users *userStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var cred struct {
			Username string `json:"username"`
			Password string `json:"password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&cred); err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if cred.Username == "" || cred.Password == "" {
			writeError(w, http.StatusBadRequest, "INVALID_PARAM", "用户名和密码必填")
			return
		}
		if err := users.register(cred.Username, cred.Password); err != nil {
			writeError(w, http.StatusConflict, "DUPLICATE", "用户名已存在")
			return
		}
		token, err := signJWT(map[string]any{"username": cred.Username}, 2*time.Hour)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "INTERNAL", "签发 token 失败")
			return
		}
		writeJSON(w, http.StatusCreated, map[string]string{"token": token}) // 201
	}
}

func handleLogin(users *userStore) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		var cred struct {
			Username string `json:"username"`
			Password string `json:"password"`
		}
		if err := json.NewDecoder(r.Body).Decode(&cred); err != nil {
			writeError(w, http.StatusBadRequest, "INVALID_JSON", "请求体不是合法 JSON")
			return
		}
		if !users.check(cred.Username, cred.Password) {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "用户名或密码错误")
			return
		}
		token, err := signJWT(map[string]any{"username": cred.Username}, 2*time.Hour)
		if err != nil {
			writeError(w, http.StatusInternalServerError, "INTERNAL", "签发 token 失败")
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"token": token})
	}
}

// ctxKey 私有 context 键：同一包内读写 context 必须用同一个类型，否则取不到值
type ctxKey struct{}

// requireAuth 鉴权中间件：Bearer 解析 → 验签 → 用户名写入 context
func requireAuth(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		token, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if !ok {
			writeError(w, http.StatusUnauthorized, "UNAUTHORIZED", "缺少 Bearer token")
			return
		}
		claims, err := verifyJWT(token)
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
