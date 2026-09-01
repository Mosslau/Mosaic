package main

import (
	"strings"
	"testing"
)

func TestLoadJSON(t *testing.T) {
	var c Config
	err := LoadJSON(&c, `{"port":8080,"host":"0.0.0.0","debug":true,"timeout_ms":1.5,"tags":["a"]}`)
	if err != nil {
		t.Fatalf("LoadJSON: %v", err)
	}
	if c.Port != 8080 || c.Host != "0.0.0.0" || !c.Debug || c.TimeoutMS != 1.5 {
		t.Errorf("填充错误: %+v", c)
	}
	if len(c.Tags) != 0 {
		t.Errorf("cfg:\"-\" 字段不应被反射填充: %v", c.Tags)
	}
}

func TestLoadJSONMissingKeys(t *testing.T) {
	var c Config
	if err := LoadJSON(&c, `{"port":1}`); err != nil {
		t.Fatalf("缺 key 不应报错: %v", err)
	}
	if c.Port != 1 || c.Host != "" || c.Debug {
		t.Errorf("未提供 key 保持零值: %+v", c)
	}
}

func TestLoadJSONInvalidJSON(t *testing.T) {
	var c Config
	if err := LoadJSON(&c, `{broken`); err == nil {
		t.Error("非法 JSON 应报错")
	}
}

func TestLoadJSONBadType(t *testing.T) {
	var c Config
	err := LoadJSON(&c, `{"port":"not-a-number"}`)
	if err == nil {
		t.Fatal("类型不匹配应报错")
	}
	if !strings.Contains(err.Error(), "port") {
		t.Errorf("错误应带字段名: %v", err)
	}
}

// TestLoadJSONOverflow：float64→int64 溢出必须在转换前预检（直接转换是静默的）。
func TestLoadJSONOverflow(t *testing.T) {
	var c Config
	err := LoadJSON(&c, `{"port":99999999999999999999}`)
	if err == nil {
		t.Fatal("溢出应报错")
	}
	if !strings.Contains(err.Error(), "超出 int64 范围") {
		t.Errorf("错误应说明溢出: %v", err)
	}
}

func TestLoadEnv(t *testing.T) {
	t.Setenv("APP_PORT", "9090")
	t.Setenv("APP_HOST", "127.0.0.1")
	t.Setenv("APP_DEBUG", "false")
	var c Config
	if err := LoadEnv(&c, "APP_"); err != nil {
		t.Fatalf("LoadEnv: %v", err)
	}
	if c.Port != 9090 || c.Host != "127.0.0.1" || c.Debug {
		t.Errorf("env 填充错误: %+v", c)
	}
}

func TestLoadEnvBadValue(t *testing.T) {
	t.Setenv("APP_PORT", "abc")
	var c Config
	if err := LoadEnv(&c, "APP_"); err == nil {
		t.Error("env 非法数字应报错")
	}
}

// TestLoadEnvOverridesJSON：env 优先于 json（生产语义：文件给默认值、env 覆盖）。
func TestLoadEnvOverridesJSON(t *testing.T) {
	t.Setenv("APP_PORT", "9090")
	var c Config
	err := Load(&c, `{"port":8080,"host":"0.0.0.0"}`, "APP_")
	if err != nil {
		t.Fatalf("Load: %v", err)
	}
	if c.Port != 9090 {
		t.Errorf("env 应覆盖 json: port=%d", c.Port)
	}
	if c.Host != "0.0.0.0" {
		t.Errorf("未覆盖的字段保留 json 值: host=%q", c.Host)
	}
}

// TestLoadJSONFloatAndBoolFromString：env 的 string 也要能转 float64/bool。
func TestLoadJSONFloatAndBoolFromString(t *testing.T) {
	t.Setenv("APP_TIMEOUT_MS", "2.5")
	t.Setenv("APP_DEBUG", "true")
	var c Config
	if err := LoadEnv(&c, "APP_"); err != nil {
		t.Fatalf("LoadEnv: %v", err)
	}
	if c.TimeoutMS != 2.5 || !c.Debug {
		t.Errorf("string→float/bool 转换错误: %+v", c)
	}
}
