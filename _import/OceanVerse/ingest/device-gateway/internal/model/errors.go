package model

import (
	"encoding/json"
	"net/http"
)

// ErrorCode 统一错误码(对外契约的一部分)
type ErrorCode string

const (
	CodeUnauthorized   ErrorCode = "UNAUTHORIZED" // 设备鉴权失败
	CodeRateLimited    ErrorCode = "RATE_LIMITED" // 触发限流
	CodeInvalidBody    ErrorCode = "INVALID_BODY" // 请求体非法(JSON 解析失败等)
	CodeInvalidData    ErrorCode = "INVALID_DATA" // 数据校验失败
	CodeMethodNotAllow ErrorCode = "METHOD_NOT_ALLOWED"
	CodeInternal       ErrorCode = "INTERNAL" // 服务端内部错误
)

// AppError 网关统一错误结构
type AppError struct {
	Code    ErrorCode `json:"code"`
	Message string    `json:"message"`
}

func (e *AppError) Error() string { return string(e.Code) + ": " + e.Message }

// HTTPStatus 错误码 → HTTP 状态码映射
func HTTPStatus(code ErrorCode) int {
	switch code {
	case CodeUnauthorized:
		return http.StatusUnauthorized
	case CodeRateLimited:
		return http.StatusTooManyRequests
	case CodeInvalidBody, CodeInvalidData:
		return http.StatusBadRequest
	case CodeMethodNotAllow:
		return http.StatusMethodNotAllowed
	default:
		return http.StatusInternalServerError
	}
}

// WriteError 以统一格式写出错误响应
func WriteError(w http.ResponseWriter, code ErrorCode, msg string) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(HTTPStatus(code))
	_ = json.NewEncoder(w).Encode(&AppError{Code: code, Message: msg})
}
